#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scheduler pour l'orchestration des jobs de scraping
Version mise à jour avec support des mots-clés personnalisés
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import connection as PGConnection  # pour annotations sûres
import schedule

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/scheduler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class ScrapingScheduler:
    """
    Scheduler principal pour l'orchestration des jobs de scraping
    Gère l'exécution des spiders avec les nouveaux paramètres personnalisés
    """

    def __init__(self):
        """Initialize le scheduler avec la configuration base de données"""

        # Configuration base de données
        self.db_config = {
            'host': os.getenv("POSTGRES_HOST", "db"),
            'port': int(os.getenv("POSTGRES_PORT", "5432")),
            'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),
            'user': os.getenv("POSTGRES_USER", "scraper_admin"),
            'password': os.getenv("POSTGRES_PASSWORD", "scraper_admin"),
            'connect_timeout': 30
        }

        # Configuration scheduler
        self.max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
        self.job_timeout = int(os.getenv("JOB_TIMEOUT_MINUTES", "60"))
        self.retry_delay_minutes = int(os.getenv("RETRY_DELAY_MINUTES", "30"))

        # État du scheduler
        self.running_jobs: Dict[int, Dict[str, Any]] = {}
        self.is_running = False
        self.scheduler_paused = False

        logger.info("Scheduler initialisé")
        logger.info(f"Configuration: max_jobs={self.max_concurrent_jobs}, timeout={self.job_timeout}min")

    @contextmanager
    def get_db_connection(self):
        """Context manager pour les connexions base de données"""
        conn: Optional[PGConnection] = None
        try:
            conn = psycopg2.connect(**self.db_config)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Erreur base de données: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def execute_query(self, query: str, params: tuple = None, fetch: str = 'all'):
        """Exécute une requête de manière sécurisée"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, params or ())

                    if fetch == 'all':
                        result = cur.fetchall()
                    elif fetch == 'one':
                        result = cur.fetchone()
                    elif fetch == 'none':
                        conn.commit()
                        return True
                    else:
                        result = cur.fetchall()

                    conn.commit()
                    return result
        except Exception as e:
            logger.error(f"Erreur requête base de données: {e}")
            return None

    def get_pending_jobs(self) -> List[Dict]:
        """
        Récupère les jobs en attente de traitement
        MODIFIÉ: Inclut custom_keywords, match_mode, min_matches au lieu de theme
        """
        query = """
            SELECT 
                id, url, country_filter, lang_filter, 
                custom_keywords, match_mode, min_matches,
                use_js, max_pages_per_domain, priority, 
                retry_count, max_retries, next_retry_at,
                created_at, created_by
            FROM queue 
            WHERE status = 'pending' 
              AND deleted_at IS NULL
              AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY priority ASC, retry_count ASC, created_at ASC
            LIMIT %s
        """

        available_slots = self.max_concurrent_jobs - len(self.running_jobs)
        if available_slots <= 0:
            return []

        jobs = self.execute_query(query, (available_slots,))
        return jobs or []

    def update_job_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        execution_time: Optional[int] = None,
        contacts_count: Optional[int] = None
    ):
        """Met à jour le statut d'un job"""

        update_fields = ["status = %s", "updated_at = NOW()"]
        params: List[Any] = [status]

        if error_message:
            update_fields.append("last_error = %s")
            params.append(error_message)

        if execution_time is not None:
            update_fields.append("execution_time_seconds = %s")
            params.append(execution_time)

        if contacts_count is not None:
            update_fields.append("contacts_extracted = %s")
            params.append(contacts_count)

        # Gestion des retry
        if status == 'failed':
            update_fields.extend([
                "retry_count = retry_count + 1",
                "next_retry_at = NOW() + INTERVAL '%s minutes'"
            ])
            params.append(self.retry_delay_minutes)

        params.append(job_id)

        query = f"""
            UPDATE queue 
               SET {', '.join(update_fields)}
             WHERE id = %s
        """

        self.execute_query(query, tuple(params), fetch='none')

    def execute_spider(self, job: Dict) -> Dict[str, Any]:
        """
        Exécute un spider pour un job donné
        MODIFIÉ: Passe custom_keywords et match_mode au lieu de theme
        """
        job_id = job['id']
        start_time = time.time()

        try:
            logger.info(f"Démarrage job {job_id}: {job['url']}")

            # MODIFIÉ: Construction des arguments avec custom_keywords
            spider_args = {
                'url': job['url'],
                'query_id': job_id,
                'custom_keywords': json.dumps(job['custom_keywords']) if job.get('custom_keywords') else '[]',
                'match_mode': job.get('match_mode', 'any'),
                'min_matches': job.get('min_matches', 1),
                'country_filter': job.get('country_filter') or '',
                'lang_filter': job.get('lang_filter') or '',
                'use_js': str(job.get('use_js', False)),
                'max_pages_per_domain': job.get('max_pages_per_domain', 25)
            }

            # Log des paramètres pour debug
            keywords_count = len(job['custom_keywords']) if job.get('custom_keywords') else 0
            logger.info(f"Job {job_id} - Paramètres:")
            logger.info(f"  - Mots-clés: {keywords_count} keywords")
            logger.info(f"  - Mode: {spider_args['match_mode']}")
            logger.info(f"  - Min matches: {spider_args['min_matches']}")
            logger.info(f"  - JavaScript: {spider_args['use_js']}")

            # Construction de la commande Scrapy
            cmd = self._build_scrapy_command(spider_args)

            logger.info(f"Exécution commande: {' '.join(cmd[:5])}... (tronqué)")

            # Exécution du spider avec timeout
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.job_timeout * 60,
                cwd=os.path.join(os.path.dirname(__file__), '..', 'scraper')
            )

            execution_time = int(time.time() - start_time)

            # Analyser le résultat
            if process.returncode == 0:
                # Compter les contacts extraits
                contacts_count = self._count_extracted_contacts(job_id, process.stdout)

                logger.info(
                    f"Job {job_id} terminé avec succès - "
                    f"{contacts_count} contacts extraits en {execution_time}s"
                )

                return {
                    'success': True,
                    'execution_time': execution_time,
                    'contacts_count': contacts_count,
                    'output': process.stdout
                }
            else:
                error_msg = f"Erreur spider (code {process.returncode}): {process.stderr}"
                logger.error(f"Job {job_id} échoué: {error_msg}")

                return {
                    'success': False,
                    'execution_time': execution_time,
                    'error': error_msg,
                    'output': process.stdout,
                    'stderr': process.stderr
                }

        except subprocess.TimeoutExpired:
            error_msg = f"Timeout après {self.job_timeout} minutes"
            logger.error(f"Job {job_id} timeout: {error_msg}")

            return {
                'success': False,
                'execution_time': self.job_timeout * 60,
                'error': error_msg
            }

        except Exception as e:
            execution_time = int(time.time() - start_time)
            error_msg = f"Erreur inattendue: {str(e)}"
            logger.error(f"Job {job_id} erreur: {error_msg}")

            return {
                'success': False,
                'execution_time': execution_time,
                'error': error_msg
            }

    def _build_scrapy_command(self, args: Dict[str, Any]) -> List[str]:
        """
        Construit la commande Scrapy avec les arguments
        MODIFIÉ: Utilise custom_keywords au lieu de theme
        """
        cmd = [
            'scrapy', 'crawl', 'single_url',
            '-a', f"url={args['url']}",
            '-a', f"query_id={args['query_id']}",
            '-a', f"custom_keywords={args['custom_keywords']}",  # MODIFIÉ
            '-a', f"match_mode={args['match_mode']}",            # AJOUTÉ
            '-a', f"min_matches={args['min_matches']}",          # AJOUTÉ
            '-a', f"use_js={args['use_js']}",
            '-a', f"max_pages_per_domain={args['max_pages_per_domain']}"
        ]

        # Ajouter les filtres optionnels
        if args.get('country_filter'):
            cmd.extend(['-a', f"country_filter={args['country_filter']}"])

        if args.get('lang_filter'):
            cmd.extend(['-a', f"lang_filter={args['lang_filter']}"])

        return cmd

    def _count_extracted_contacts(self, job_id: int, spider_output: str) -> int:
        """
        Compte les contacts extraits pour un job
        """
        try:
            # Compter depuis la base de données (plus fiable)
            result = self.execute_query(
                "SELECT COUNT(*) as count FROM contacts WHERE query_id = %s",
                (job_id,),
                fetch='one'
            )
            return int(result['count']) if result and 'count' in result else 0

        except Exception as e:
            logger.error(f"Erreur comptage contacts pour job {job_id}: {e}")

            # Fallback: parser la sortie du spider
            try:
                import re
                matches = re.findall(r'scraped (\d+) items', spider_output, re.IGNORECASE)
                return int(matches[-1]) if matches else 0
            except Exception:
                return 0

    def process_jobs(self):
        """
        Traite les jobs en attente
        """
        if self.scheduler_paused:
            logger.debug("Scheduler en pause")
            return

        try:
            # Vérifier l'état du scheduler dans la base
            scheduler_status = self.execute_query(
                "SELECT value FROM settings WHERE key = 'scheduler_paused'",
                fetch='one'
            )

            if scheduler_status and str(scheduler_status['value']).lower() == 'true':
                if not self.scheduler_paused:
                    logger.info("Scheduler mis en pause via base de données")
                    self.scheduler_paused = True
                return
            else:
                if self.scheduler_paused:
                    logger.info("Scheduler réactivé via base de données")
                    self.scheduler_paused = False

            # Nettoyer les jobs expirés
            self._cleanup_expired_jobs()

            # Récupérer les jobs en attente
            pending_jobs = self.get_pending_jobs()

            if not pending_jobs:
                logger.debug("Aucun job en attente")
                return

            logger.info(f"Traitement de {len(pending_jobs)} job(s) en attente")

            # Lancer les jobs
            for job in pending_jobs:
                if len(self.running_jobs) >= self.max_concurrent_jobs:
                    break
                self._start_job_thread(job)

        except Exception as e:
            logger.error(f"Erreur lors du traitement des jobs: {e}")

    def _start_job_thread(self, job: Dict):
        """Lance un job dans un thread séparé"""
        job_id = job['id']

        # Marquer comme en cours
        self.update_job_status(job_id, 'in_progress')

        # Créer et lancer le thread
        thread = threading.Thread(
            target=self._job_worker,
            args=(job,),
            name=f"Job-{job_id}",
            daemon=True
        )

        self.running_jobs[job_id] = {
            'thread': thread,
            'job': job,
            'start_time': time.time()
        }

        thread.start()
        logger.info(f"Job {job_id} lancé en thread ({len(self.running_jobs)} jobs actifs)")

    def _job_worker(self, job: Dict):
        """Worker thread pour exécuter un job"""
        job_id = job['id']

        try:
            # Exécuter le spider
            result = self.execute_spider(job)

            # Mettre à jour le statut selon le résultat
            if result['success']:
                self.update_job_status(
                    job_id, 'done',
                    execution_time=result['execution_time'],
                    contacts_count=result.get('contacts_count', 0)
                )
            else:
                # Vérifier si on doit retry
                should_retry = (
                    job.get('retry_count', 0) < job.get('max_retries', 3) and
                    'timeout' not in str(result.get('error', '')).lower()
                )

                status = 'pending' if should_retry else 'failed'

                self.update_job_status(
                    job_id, status,
                    error_message=str(result.get('error', '')),
                    execution_time=result.get('execution_time')
                )

                if should_retry:
                    retry_count = job.get('retry_count', 0) + 1
                    logger.info(f"Job {job_id} sera retenté (tentative {retry_count})")
                else:
                    logger.error(f"Job {job_id} définitivement échoué")

        except Exception as e:
            logger.error(f"Erreur critique dans job worker {job_id}: {e}")
            self.update_job_status(job_id, 'failed', error_message=str(e))

        finally:
            # Nettoyer le job des jobs actifs
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]

            logger.info(f"Job {job_id} terminé ({len(self.running_jobs)} jobs actifs restants)")

    def _cleanup_expired_jobs(self):
        """Nettoie les jobs expirés ou bloqués"""
        current_time = time.time()
        expired_jobs: List[int] = []

        for job_id, job_info in list(self.running_jobs.items()):
            if current_time - job_info['start_time'] > self.job_timeout * 60:
                expired_jobs.append(job_id)

        for job_id in expired_jobs:
            logger.warning(f"Job {job_id} expiré, nettoyage forcé")

            # Note: Python ne permet pas de tuer un thread directement
            # Le timeout du subprocess devrait gérer cela

            # Marquer comme échoué
            self.update_job_status(job_id, 'failed',
                                   error_message="Job expiré par timeout scheduler")

            # Retirer des jobs actifs
            if job_id in self.running_jobs:
                del self.running_jobs[job_id]

    def get_system_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques système"""
        try:
            stats = self.execute_query("""
                SELECT 
                    (SELECT COUNT(*) FROM queue   WHERE status = 'pending'     AND deleted_at IS NULL)                                        AS pending_jobs,
                    (SELECT COUNT(*) FROM queue   WHERE status = 'in_progress'  AND deleted_at IS NULL)                                        AS active_jobs,
                    (SELECT COUNT(*) FROM queue   WHERE status = 'done'         AND DATE(updated_at) = CURRENT_DATE AND deleted_at IS NULL)   AS completed_today,
                    (SELECT COUNT(*) FROM queue   WHERE status = 'failed'       AND DATE(updated_at) = CURRENT_DATE AND deleted_at IS NULL)   AS failed_today,
                    (SELECT COUNT(*) FROM contacts WHERE DATE(created_at) = CURRENT_DATE AND deleted_at IS NULL)                               AS contacts_today
            """, fetch='one')

            if stats:
                stats = dict(stats)
                stats['running_jobs'] = len(self.running_jobs)
                stats['scheduler_status'] = 'paused' if self.scheduler_paused else 'running'
                stats['max_concurrent_jobs'] = self.max_concurrent_jobs
                return stats

        except Exception as e:
            logger.error(f"Erreur récupération stats: {e}")

        return {
            'pending_jobs': 0,
            'active_jobs': 0,
            'completed_today': 0,
            'failed_today': 0,
            'contacts_today': 0,
            'running_jobs': len(self.running_jobs),
            'scheduler_status': 'paused' if self.scheduler_paused else 'running',
            'max_concurrent_jobs': self.max_concurrent_jobs
        }

    def pause_scheduler(self):
        """Met en pause le scheduler"""
        self.scheduler_paused = True
        self.execute_query(
            "UPDATE settings SET value = 'true' WHERE key = 'scheduler_paused'",
            fetch='none'
        )
        logger.info("Scheduler mis en pause")

    def resume_scheduler(self):
        """Reprend le scheduler"""
        self.scheduler_paused = False
        self.execute_query(
            "UPDATE settings SET value = 'false' WHERE key = 'scheduler_paused'",
            fetch='none'
        )
        logger.info("Scheduler repris")

    def stop_all_jobs(self):
        """Arrête tous les jobs en cours"""
        logger.info(f"Arrêt de {len(self.running_jobs)} job(s) en cours")

        for job_id in list(self.running_jobs.keys()):
            self.update_job_status(job_id, 'failed',
                                   error_message="Arrêté par l'administrateur")

        self.running_jobs.clear()

    def run(self):
        """
        Boucle principale du scheduler
        """
        logger.info("Démarrage du scheduler")
        self.is_running = True

        # Programmer les tâches périodiques
        schedule.every(30).seconds.do(self.process_jobs)
        schedule.every(5).minutes.do(self._log_stats)
        schedule.every(1).hours.do(self._maintenance_cleanup)

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(10)  # Attendre 10 secondes

        except KeyboardInterrupt:
            logger.info("Arrêt du scheduler demandé")
        except Exception as e:
            logger.error(f"Erreur critique scheduler: {e}")
        finally:
            self._shutdown()

    def _log_stats(self):
        """Log les statistiques périodiquement"""
        stats = self.get_system_stats()
        logger.info(
            f"Stats: {stats['pending_jobs']} en attente, "
            f"{stats['running_jobs']}/{self.max_concurrent_jobs} actifs, "
            f"{stats['completed_today']} terminés aujourd'hui"
        )

    def _maintenance_cleanup(self):
        """Tâches de maintenance périodiques"""
        try:
            # Nettoyer les anciens logs (exemple)
            self.execute_query("""
                DELETE FROM system_logs 
                 WHERE timestamp < NOW() - INTERVAL '30 days'
            """, fetch='none')

            logger.debug("Maintenance périodique effectuée")

        except Exception as e:
            logger.error(f"Erreur maintenance: {e}")

    def _shutdown(self):
        """Arrêt propre du scheduler"""
        logger.info("Arrêt du scheduler en cours...")
        self.is_running = False

        # Attendre que les jobs se terminent (avec timeout)
        if self.running_jobs:
            logger.info(f"Attente de la fin de {len(self.running_jobs)} job(s)...")

            for _ in range(30):  # Attendre max 30 secondes
                if not self.running_jobs:
                    break
                time.sleep(1)

            # Forcer l'arrêt des jobs restants
            if self.running_jobs:
                logger.warning(f"Arrêt forcé de {len(self.running_jobs)} job(s)")
                self.stop_all_jobs()

        logger.info("Scheduler arrêté")


def main():
    """Point d'entrée principal"""

    # Créer les dossiers de logs
    os.makedirs('logs', exist_ok=True)

    # Initialiser et lancer le scheduler
    scheduler = ScrapingScheduler()

    try:
        scheduler.run()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
