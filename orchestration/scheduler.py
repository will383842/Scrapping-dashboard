from scraper.utils.error_categorizer import categorize
from scraper.utils.circuit_breaker import open_cb

import os
import time
import logging
import subprocess
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

# ======================================================================
# Configuration logging avancée
# ======================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/scheduler.log', mode='a')
        if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================
# Configuration base de données
# ======================================================================
DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper_pro"),
    user=os.getenv("POSTGRES_USER", "scraper_admin"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper"),
    connect_timeout=10,
    application_name='scraper_scheduler'
)

# ======================================================================
# Configuration avancée
# ======================================================================
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))
JOB_TIMEOUT_SEC = int(os.getenv("JOB_TIMEOUT_SEC", "1800"))  # 30 minutes
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))  # 1 minute


class DatabaseError(Exception):
    """Exception pour erreurs base de données"""
    pass


class JobExecutionError(Exception):
    """Exception pour erreurs d'exécution de job"""
    pass


class DatabaseManager:
    """Gestionnaire de connexions DB robuste pour le scheduler"""

    def __init__(self, config: dict):
        self.config = config
        self._connection: Optional[PgConnection] = None
        self.last_connection_attempt: Optional[datetime] = None
        self.connection_failures = 0

    def get_connection(self) -> Optional[PgConnection]:
        """Obtient une connexion active, avec reconnection si nécessaire"""
        # Éviter les tentatives de reconnection trop fréquentes
        now = datetime.now()
        if (
            self.last_connection_attempt
            and (now - self.last_connection_attempt).total_seconds() < 5
            and self.connection_failures > 0
        ):
            return None

        if self._connection is None or getattr(self._connection, "closed", True):
            try:
                self._connection = psycopg2.connect(**self.config)
                self.connection_failures = 0
                logger.info("Nouvelle connexion DB établie")
            except psycopg2.Error as e:
                self.last_connection_attempt = now
                self.connection_failures += 1
                logger.error(f"Erreur connexion DB (tentative {self.connection_failures}): {e}")
                return None

        # Test de la connexion existante
        try:
            with self._connection.cursor() as cur:
                cur.execute("SELECT 1")
            return self._connection
        except psycopg2.Error as e:
            logger.warning(f"Connexion DB interrompue ({e}), tentative de reconnection...")
            try:
                if self._connection:
                    self._connection.close()
                self._connection = psycopg2.connect(**self.config)
                self.connection_failures = 0
                logger.info("Reconnection DB réussie")
                return self._connection
            except psycopg2.Error as reconnect_error:
                self.last_connection_attempt = now
                self.connection_failures += 1
                logger.error(f"Échec de reconnection DB: {reconnect_error}")
                self._connection = None
                return None

    def execute_query(self, query: str, params: tuple = None, fetch: str = 'all'):
        """Exécution sécurisée de requêtes avec rollback et commit"""
        conn = self.get_connection()
        if not conn:
            raise DatabaseError("Connexion DB non disponible")

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())

                if fetch == 'all':
                    result = cur.fetchall()
                elif fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'none':
                    result = True
                else:
                    result = cur.fetchall()

                conn.commit()
                return result

        except psycopg2.Error as e:
            logger.error(f"Erreur requête DB: {e}")
            try:
                if conn and not getattr(conn, "closed", True):
                    conn.rollback()
            except Exception:
                pass

            # Force reconnection pour la prochaine fois
            self._connection = None
            raise DatabaseError(f"Erreur DB: {e}")

    def close(self):
        """Ferme la connexion proprement"""
        if self._connection and not getattr(self._connection, "closed", True):
            try:
                self._connection.close()
            except Exception:
                pass
        self._connection = None


class ScrapingScheduler:
    def __init__(self):
        self.db_manager = DatabaseManager(DB)
        self.last_health_check = datetime.now()
        self.stats = {
            'jobs_processed': 0,
            'jobs_failed': 0,
            'jobs_retried': 0,
            'start_time': datetime.now()
        }

    def apply_env_limits(self):
        """Application des limites d'environnement au démarrage"""
        try:
            limit = os.getenv("JS_PAGES_LIMIT")
            if limit and str(limit).isdigit():
                self.db_manager.execute_query(
                    """
                    INSERT INTO settings(key, value) VALUES('js_pages_limit', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    (str(limit),),
                    fetch='none'
                )
                logger.info(f"JS_PAGES_LIMIT appliquée: {limit}")
        except Exception as e:
            logger.exception(f"Erreur application limites env: {e}")

    def is_scheduler_paused(self) -> bool:
        """Vérification si le scheduler est en pause"""
        try:
            result = self.db_manager.execute_query(
                "SELECT value FROM settings WHERE key = 'scheduler_paused'",
                fetch='one'
            )
            return bool(result and str(result['value']).lower() == 'true')
        except Exception as e:
            logger.warning(f"Impossible de vérifier pause status: {e}")
            return False

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        """Récupération du prochain job avec verrouillage optimiste"""
        try:
            sql = """
            WITH available_jobs AS (
                SELECT id, url, use_js, theme, country_filter, lang_filter,
                       max_pages_per_domain, session_id, retry_count,
                       COALESCE(priority, 10) AS priority
                FROM queue
                WHERE status = 'pending'
                  AND (retry_count IS NULL OR retry_count < %s)
                  AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                ORDER BY priority DESC, retry_count ASC, id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE queue q SET
                status = 'in_progress',
                updated_at = NOW(),
                retry_count = COALESCE(retry_count, 0)
            FROM available_jobs aj
            WHERE q.id = aj.id
            RETURNING q.id, aj.url, aj.use_js, aj.theme, aj.country_filter,
                     aj.lang_filter, aj.max_pages_per_domain, aj.session_id, aj.retry_count;
            """

            job = self.db_manager.execute_query(sql, (MAX_RETRIES,), fetch='one')

            if job:
                logger.info(
                    f"Job récupéré: ID={job['id']}, URL={job['url']}, Retry={job.get('retry_count', 0)}"
                )
            return dict(job) if job else None

        except DatabaseError as e:
            logger.error(f"Erreur récupération job: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur inattendue récupération job: {e}")
            raise DatabaseError(f"Erreur claim job: {e}")

    def update_job_status(self, job_id: int, status: str,
                          error_msg: Optional[str] = None,
                          retry_count: Optional[int] = None):
        """Mise à jour du statut d'un job avec gestion d'erreurs"""
        try:
            if status == 'failed' and retry_count is not None and retry_count < MAX_RETRIES:
                # Planifier un retry avec backoff exponentiel (minutes)
                next_retry = datetime.now() + timedelta(
                    seconds=int((RETRY_BACKOFF_BASE ** retry_count) * 60)
                )
                self.db_manager.execute_query(
                    """
                    UPDATE queue SET
                        status = 'pending',
                        last_error = LEFT(%s, 1000),
                        retry_count = %s,
                        next_retry_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (error_msg, retry_count + 1, next_retry, job_id),
                    fetch='none'
                )
                logger.info(f"Job {job_id} programmé pour retry #{retry_count + 1} à {next_retry}")
            else:
                # Statut final
                self.db_manager.execute_query(
                    """
                    UPDATE queue SET
                        status = %s,
                        last_error = LEFT(%s, 1000),
                        updated_at = NOW(),
                        last_run_at = CASE WHEN %s = 'done' THEN NOW() ELSE last_run_at END
                    WHERE id = %s
                    """,
                    (status, error_msg, status, job_id),
                    fetch='none'
                )

        except DatabaseError as e:
            logger.error(f"Erreur mise à jour job {job_id}: {e}")
            raise

    def execute_spider(self, job: Dict[str, Any]) -> tuple[int, str, str]:
        """Exécution sécurisée d'un spider avec timeout"""
        args = [
            "scrapy", "crawl", "single_url",
            "-a", f"url={job['url']}",
            "-a", f"use_js={1 if job.get('use_js') else 0}",
        ]

        # Paramètres optionnels
        if job.get('theme'):
            args.extend(["-a", f"theme={job['theme']}"])
        if job.get('country_filter'):
            args.extend(["-a", f"country_filter={job['country_filter']}"])
        if job.get('lang_filter'):
            args.extend(["-a", f"lang_filter={job['lang_filter']}"])
        if job.get('max_pages_per_domain'):
            args.extend(["-a", f"max_pages_per_domain={job['max_pages_per_domain']}"])
        if job.get('session_id'):
            args.extend(["-a", f"session_id={job['session_id']}"])
        if job.get('id'):
            args.extend(["-a", f"query_id={job['id']}"])

        logger.info(f"Exécution spider: {' '.join(args)}")

        try:
            result = subprocess.run(
                args,
                cwd="/app/scraper",
                capture_output=True,
                text=True,
                timeout=JOB_TIMEOUT_SEC
            )
            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            error_msg = f"Job timeout après {JOB_TIMEOUT_SEC}s"
            logger.error(error_msg)
            return 1, "", error_msg
        except Exception as e:
            error_msg = f"Erreur exécution spider: {e}"
            logger.exception(error_msg)
            return 1, "", error_msg

    def process_job(self, job: Dict[str, Any]) -> bool:
        """Traitement complet d'un job avec retry automatique"""
        job_id = job['id']
        retry_count = int(job.get('retry_count') or 0)

        try:
            logger.info(f"Traitement job {job_id} (tentative {retry_count + 1}/{MAX_RETRIES + 1})")

            # Exécution du spider
            exit_code, stdout, stderr = self.execute_spider(job)

            if exit_code == 0:
                self.update_job_status(job_id, 'done')
                self.stats['jobs_processed'] += 1
                logger.info(f"✅ Job {job_id} terminé avec succès")
                return True
            else:
                error_msg = stderr or stdout or f"Exit code: {exit_code}"

                if retry_count < MAX_RETRIES:
                    self.update_job_status(job_id, 'failed', error_msg, retry_count)
                    self.stats['jobs_retried'] += 1
                    logger.warning(f"⚠️ Job {job_id} échoué, retry programmé: {error_msg[:200]}")
                else:
                    self.update_job_status(job_id, 'failed', f"Max retries exceeded: {error_msg}")
                    self.stats['jobs_failed'] += 1
                    logger.error(f"❌ Job {job_id} échoué définitivement: {error_msg[:200]}")

                return False

        except Exception as e:
            error_msg = f"Erreur traitement job: {e}"
            logger.exception(error_msg)

            try:
                if retry_count < MAX_RETRIES:
                    self.update_job_status(job_id, 'failed', error_msg, retry_count)
                    self.stats['jobs_retried'] += 1
                else:
                    self.update_job_status(job_id, 'failed', f"Max retries exceeded: {error_msg}")
                    self.stats['jobs_failed'] += 1
            except Exception as update_error:
                logger.error(f"Impossible de mettre à jour le statut du job {job_id}: {update_error}")

            return False

    def perform_health_check(self):
        """Vérifications de santé système"""
        try:
            # Heartbeat
            self.db_manager.execute_query(
                """
                INSERT INTO settings (key, value) VALUES ('scheduler_last_heartbeat', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (datetime.now().isoformat(),),
                fetch='none'
            )

            # Stats
            uptime = datetime.now() - self.stats['start_time']
            stats_json = json.dumps({
                'jobs_processed': self.stats['jobs_processed'],
                'jobs_failed': self.stats['jobs_failed'],
                'jobs_retried': self.stats['jobs_retried'],
                'uptime_minutes': int(uptime.total_seconds() / 60)
            })

            self.db_manager.execute_query(
                """
                INSERT INTO settings (key, value) VALUES ('scheduler_stats', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (stats_json,),
                fetch='none'
            )

            logger.debug("Health check OK")

        except Exception as e:
            logger.warning(f"Health check échoué: {e}")

    def cleanup_old_jobs(self):
        """Nettoyage des anciens jobs terminés"""
        try:
            self.db_manager.execute_query(
                """
                UPDATE queue SET deleted_at = NOW()
                WHERE status IN ('done', 'failed')
                  AND retry_count >= %s
                  AND updated_at < NOW() - INTERVAL '7 days'
                  AND deleted_at IS NULL
                """,
                (MAX_RETRIES,),
                fetch='none'
            )
            logger.info("Nettoyage des anciens jobs effectué")
        except Exception as e:
            logger.warning(f"Erreur nettoyage: {e}")

    def run(self):
        """Boucle principale du scheduler avec gestion d'erreur robuste"""
        logger.info("🚀 Scraping Scheduler démarré")
        logger.info(f"Configuration: MAX_RETRIES={MAX_RETRIES}, POLL_INTERVAL={POLL_INTERVAL_SEC}s, TIMEOUT={JOB_TIMEOUT_SEC}s")

        self.apply_env_limits()
        consecutive_db_errors = 0
        max_consecutive_errors = 10

        while True:
            try:
                # Pause
                if self.is_scheduler_paused():
                    logger.info("⏸️ Scheduler en pause, attente...")
                    time.sleep(POLL_INTERVAL_SEC * 2)
                    continue

                # Health check périodique
                if (datetime.now() - self.last_health_check).seconds >= HEALTH_CHECK_INTERVAL:
                    self.perform_health_check()
                    self.last_health_check = datetime.now()

                    # Nettoyage périodique (toutes les heures)
                    if self.last_health_check.minute == 0:
                        self.cleanup_old_jobs()

                # Récupération job
                job = self.claim_next_job()

                if job is None:
                    # Pas de job disponible
                    time.sleep(POLL_INTERVAL_SEC)
                    consecutive_db_errors = 0
                    continue

                # Traitement du job
                success = self.process_job(job)
                consecutive_db_errors = 0  # reset en cas de succès

                # Petit délai entre jobs pour éviter la surcharge
                time.sleep(0.5)

            except DatabaseError as e:
                consecutive_db_errors += 1
                logger.error(f"Erreur DB (tentative {consecutive_db_errors}): {e}")

                # Reconnection progressive
                wait_time = min(consecutive_db_errors * 2, 30)
                logger.info(f"Attente {wait_time}s avant reconnection...")
                time.sleep(wait_time)

                # Force fermeture connexion pour reconnection propre
                self.db_manager.close()

                # Arrêt si trop d'erreurs consécutives
                if consecutive_db_errors >= max_consecutive_errors:
                    logger.critical("Trop d'erreurs DB consécutives, arrêt du scheduler")
                    break

            except Exception as e:
                logger.exception(f"Erreur inattendue: {e}")

                # Pause progressive en cas d'erreurs
                time.sleep(min(5, POLL_INTERVAL_SEC))

                # Force fermeture connexion en cas d'erreur grave
                try:
                    self.db_manager.close()
                except Exception:
                    pass

        logger.info("🛑 Scheduler arrêté")

        # Nettoyage final
        try:
            self.db_manager.close()
        except Exception:
            pass


def handle_error(ex: Exception, context: dict = None):
    """
    Gestion d'erreur transversale : catégorise et ouvre un circuit breaker sur proxy si pertinent.
    """
    context = context or {}
    cat = categorize(ex, context.get("status_code"), str(ex))

    # open circuit on persistent proxy failures
    proxy = context.get("proxy")
    if proxy and cat in ("network", "proxy", "timeout"):
        key = f"proxy:{proxy.get('id') or proxy.get('host')}"
        open_cb(key, context.get("cooldown", 300))

    # TODO: persister dans error_events (DB) si souhaité
    return cat


def main():
    """Point d'entrée principal"""
    try:
        scheduler = ScrapingScheduler()
        scheduler.run()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.critical(f"Erreur fatale: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()
