import os
import time
import logging
import subprocess
import psycopg2
import json
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any

# Configuration logging avancée
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s:%(lineno)d] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/scheduler.log', mode='a') if os.path.exists('/app/logs') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration base de données
DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper"),
    user=os.getenv("POSTGRES_USER", "scraper"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper"),
)

# Configuration avancée
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

class ScrapingScheduler:
    def __init__(self):
        self.conn: Optional[psycopg2.connection] = None
        self.last_health_check = datetime.now()
        self.stats = {
            'jobs_processed': 0,
            'jobs_failed': 0,
            'jobs_retried': 0,
            'start_time': datetime.now()
        }
        
    def get_db_connection(self) -> psycopg2.connection:
        """Connexion DB robuste avec reconnection automatique"""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**DB, connect_timeout=10)
                self.conn.autocommit = False
                logger.info("Connexion base de données établie")
            return self.conn
        except psycopg2.Error as e:
            logger.error(f"Erreur connexion DB: {e}")
            raise DatabaseError(f"Impossible de se connecter à la DB: {e}")

    def apply_env_limits(self):
        """Application des limites d'environnement au démarrage"""
        try:
            conn = self.get_db_connection()
            limit = os.getenv("JS_PAGES_LIMIT")
            if limit and limit.isdigit():
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO settings(key, value) VALUES('js_pages_limit', %s)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """, (str(limit),))
                    conn.commit()
                logger.info(f"JS_PAGES_LIMIT appliquée: {limit}")
        except Exception as e:
            logger.exception(f"Erreur application limites env: {e}")

    def is_scheduler_paused(self) -> bool:
        """Vérification si le scheduler est en pause"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM settings WHERE key = 'scheduler_paused'")
                result = cur.fetchone()
                return result and result[0].lower() == 'true'
        except Exception as e:
            logger.warning(f"Impossible de vérifier pause status: {e}")
            return False

    def claim_next_job(self) -> Optional[Dict[str, Any]]:
        """Récupération du prochain job avec verrouillage optimiste"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Récupération avec priorité et retry_count
                sql = """
                WITH available_jobs AS (
                    SELECT id, url, use_js, theme, country_filter, lang_filter, 
                           max_pages_per_domain, session_id, retry_count,
                           COALESCE(priority, 10) as priority
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
                cur.execute(sql, (MAX_RETRIES,))
                job = cur.fetchone()
                conn.commit()
                
                if job:
                    logger.info(f"Job récupéré: ID={job['id']}, URL={job['url']}, Retry={job.get('retry_count', 0)}")
                return dict(job) if job else None
                
        except psycopg2.Error as e:
            logger.error(f"Erreur récupération job: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass
            raise DatabaseError(f"Erreur claim job: {e}")

    def update_job_status(self, job_id: int, status: str, error_msg: str = None, retry_count: int = None):
        """Mise à jour du statut d'un job avec gestion d'erreurs"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                if status == 'failed' and retry_count is not None and retry_count < MAX_RETRIES:
                    # Planifier un retry avec backoff exponentiel
                    next_retry = datetime.now() + timedelta(seconds=int(RETRY_BACKOFF_BASE ** retry_count * 60))
                    cur.execute("""
                        UPDATE queue SET 
                            status = 'pending',
                            last_error = LEFT(%s, 1000),
                            retry_count = %s,
                            next_retry_at = %s,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (error_msg, retry_count + 1, next_retry, job_id))
                    logger.info(f"Job {job_id} programmé pour retry #{retry_count + 1} à {next_retry}")
                else:
                    # Statut final
                    cur.execute("""
                        UPDATE queue SET 
                            status = %s,
                            last_error = LEFT(%s, 1000),
                            updated_at = NOW(),
                            last_run_at = CASE WHEN %s = 'done' THEN NOW() ELSE last_run_at END
                        WHERE id = %s
                    """, (status, error_msg, status, job_id))
                    
                conn.commit()
                
        except psycopg2.Error as e:
            logger.error(f"Erreur mise à jour job {job_id}: {e}")
            if self.conn:
                try:
                    self.conn.rollback()
                except:
                    pass

    def execute_spider(self, job: Dict[str, Any]) -> tuple[int, str, str]:
        """Exécution sécurisée d'un spider avec timeout"""
        args = [
            "scrapy", "crawl", "single_url",
            "-a", f"url={job['url']}",
            "-a", f"use_js={1 if job.get('use_js') else 0}",
        ]
        
        # Ajout paramètres optionnels
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
        retry_count = job.get('retry_count', 0)
        
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
            
            if retry_count < MAX_RETRIES:
                self.update_job_status(job_id, 'failed', error_msg, retry_count)
                self.stats['jobs_retried'] += 1
            else:
                self.update_job_status(job_id, 'failed', f"Max retries exceeded: {error_msg}")
                self.stats['jobs_failed'] += 1
            
            return False

    def perform_health_check(self):
        """Vérifications de santé système"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                # Test connectivité DB
                cur.execute("SELECT 1")
                
                # Mise à jour statistiques
                cur.execute("""
                    INSERT INTO settings (key, value) VALUES ('scheduler_last_heartbeat', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (datetime.now().isoformat(),))
                
                # Stats performance
                uptime = datetime.now() - self.stats['start_time']
                stats_json = json.dumps({
                    'jobs_processed': self.stats['jobs_processed'],
                    'jobs_failed': self.stats['jobs_failed'], 
                    'jobs_retried': self.stats['jobs_retried'],
                    'uptime_minutes': int(uptime.total_seconds() / 60)
                })
                
                cur.execute("""
                    INSERT INTO settings (key, value) VALUES ('scheduler_stats', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """, (stats_json,))
                
                conn.commit()
                
            logger.debug("Health check OK")
            
        except Exception as e:
            logger.warning(f"Health check échoué: {e}")

    def cleanup_old_jobs(self):
        """Nettoyage des anciens jobs terminés"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                # Suppression des jobs terminés depuis plus de 7 jours
                cur.execute("""
                    DELETE FROM queue 
                    WHERE status IN ('done', 'failed') 
                      AND retry_count >= %s
                      AND updated_at < NOW() - INTERVAL '7 days'
                """, (MAX_RETRIES,))
                
                deleted = cur.rowcount
                if deleted > 0:
                    logger.info(f"Nettoyage: {deleted} anciens jobs supprimés")
                    
                conn.commit()
                
        except Exception as e:
            logger.warning(f"Erreur nettoyage: {e}")

    def run(self):
        """Boucle principale du scheduler"""
        logger.info("🚀 Scraping Scheduler démarré")
        logger.info(f"Configuration: MAX_RETRIES={MAX_RETRIES}, POLL_INTERVAL={POLL_INTERVAL_SEC}s, TIMEOUT={JOB_TIMEOUT_SEC}s")
        
        self.apply_env_limits()
        consecutive_errors = 0
        
        while True:
            try:
                # Vérification pause
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
                
                # Récupération du prochain job
                job = self.claim_next_job()
                
                if job is None:
                    # Pas de job disponible
                    time.sleep(POLL_INTERVAL_SEC)
                    consecutive_errors = 0  # Reset compteur erreurs
                    continue
                
                # Traitement du job
                success = self.process_job(job)
                consecutive_errors = 0  # Reset en cas de succès
                
                # Petit délai entre jobs pour éviter la surcharge
                time.sleep(0.5)
                
            except DatabaseError as e:
                consecutive_errors += 1
                logger.error(f"Erreur DB (tentative {consecutive_errors}): {e}")
                
                # Reconnection progressive
                wait_time = min(consecutive_errors * 2, 30)
                logger.info(f"Attente {wait_time}s avant reconnection...")
                time.sleep(wait_time)
                
                # Fermeture connexion pour forcer reconnection
                if self.conn and not self.conn.closed:
                    try:
                        self.conn.close()
                    except:
                        pass
                self.conn = None
                
                # Arrêt si trop d'erreurs consécutives
                if consecutive_errors >= 10:
                    logger.critical("Trop d'erreurs DB consécutives, arrêt du scheduler")
                    break
                    
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Erreur inattendue (tentative {consecutive_errors}): {e}")
                
                # Pause progressive en cas d'erreurs
                wait_time = min(consecutive_errors, 10)
                time.sleep(wait_time)
                
                # Arrêt si trop d'erreurs consécutives  
                if consecutive_errors >= 20:
                    logger.critical("Trop d'erreurs consécutives, arrêt du scheduler")
                    break

        logger.info("🛑 Scheduler arrêté")

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