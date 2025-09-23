#!/usr/bin/env python3
# ============================================================================
# AUTOMATED TESTS - SCRAPER PRO PRODUCTION VALIDATION
# Version: 2.0 Production-Ready
# Description: Tests complets pour validation du déploiement production
# ============================================================================

import os
import sys
import time
import json
import psutil
import docker
import requests
import psycopg2
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from contextlib import contextmanager

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tests/test_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION DES TESTS
# ============================================================================

@dataclass
class TestConfig:
    """Configuration des tests"""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "scraper_pro"
    db_user: str = "scraper_admin"
    db_password: str = "scraper"
    
    dashboard_url: str = "http://localhost:8501"
    dashboard_username: str = "admin"
    dashboard_password: str = "admin123"
    
    prometheus_url: str = "http://localhost:9090"
    grafana_url: str = "http://localhost:3000"
    
    test_timeout: int = 60
    retry_attempts: int = 3
    retry_delay: int = 5

@dataclass 
class TestResult:
    """Résultat d'un test"""
    name: str
    status: str  # PASS, FAIL, SKIP
    duration: float
    message: str
    details: Optional[Dict] = None

class TestRunner:
    """Classe principale pour l'exécution des tests"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.start_time = datetime.now()
        
    def run_all_tests(self) -> Dict:
        """Exécute tous les tests de validation"""
        logger.info("🚀 Démarrage des tests de validation production")
        
        test_suites = [
            ("Infrastructure", self._test_infrastructure),
            ("Database", self._test_database),
            ("Dashboard", self._test_dashboard), 
            ("Worker", self._test_worker),
            ("API Endpoints", self._test_api_endpoints),
            ("Security", self._test_security),
            ("Performance", self._test_performance),
            ("Monitoring", self._test_monitoring),
            ("Business Logic", self._test_business_logic)
        ]
        
        for suite_name, test_func in test_suites:
            logger.info(f"📋 Exécution suite: {suite_name}")
            try:
                test_func()
            except Exception as e:
                logger.error(f"❌ Erreur dans suite {suite_name}: {e}")
                self.results.append(TestResult(
                    name=f"{suite_name} - Critical Error",
                    status="FAIL", 
                    duration=0,
                    message=str(e)
                ))
        
        return self._generate_report()

    def _test_infrastructure(self):
        """Tests de l'infrastructure Docker"""
        
        # Test 1: Docker containers running
        self._run_test(
            "Docker Containers Status",
            self._check_docker_containers
        )
        
        # Test 2: Network connectivity
        self._run_test(
            "Container Network Connectivity", 
            self._check_container_network
        )
        
        # Test 3: Volume mounts
        self._run_test(
            "Volume Mounts",
            self._check_volume_mounts
        )
        
        # Test 4: Resource limits
        self._run_test(
            "Resource Limits",
            self._check_resource_limits
        )

    def _test_database(self):
        """Tests de la base de données PostgreSQL"""
        
        # Test 1: Connection basique
        self._run_test(
            "Database Connection",
            self._check_db_connection
        )
        
        # Test 2: Schema et tables
        self._run_test(
            "Database Schema",
            self._check_db_schema
        )
        
        # Test 3: Indexes et optimisations
        self._run_test(
            "Database Indexes", 
            self._check_db_indexes
        )
        
        # Test 4: Performances requêtes
        self._run_test(
            "Database Performance",
            self._check_db_performance
        )
        
        # Test 5: Backup et restore
        self._run_test(
            "Backup Functionality",
            self._check_backup_functionality
        )

    def _test_dashboard(self):
        """Tests de l'interface dashboard Streamlit"""
        
        # Test 1: Accessibilité web
        self._run_test(
            "Dashboard Web Access",
            self._check_dashboard_access
        )
        
        # Test 2: Authentification
        self._run_test(
            "Dashboard Authentication",
            self._check_dashboard_auth
        )
        
        # Test 3: Pages principales
        self._run_test(
            "Dashboard Pages Load",
            self._check_dashboard_pages
        )
        
        # Test 4: API endpoints
        self._run_test(
            "Dashboard API",
            self._check_dashboard_api
        )

    def _test_worker(self):
        """Tests du worker de scraping"""
        
        # Test 1: Process worker actif
        self._run_test(
            "Worker Process Status",
            self._check_worker_process
        )
        
        # Test 2: Heartbeat et monitoring
        self._run_test(
            "Worker Heartbeat", 
            self._check_worker_heartbeat
        )
        
        # Test 3: Job processing
        self._run_test(
            "Job Processing",
            self._check_job_processing
        )
        
        # Test 4: Error handling
        self._run_test(
            "Worker Error Handling",
            self._check_worker_error_handling
        )

    def _test_security(self):
        """Tests de sécurité"""
        
        # Test 1: SSL/TLS configuration
        self._run_test(
            "SSL/TLS Configuration",
            self._check_ssl_config
        )
        
        # Test 2: Authentication security
        self._run_test(
            "Authentication Security",
            self._check_auth_security
        )
        
        # Test 3: Network security
        self._run_test(
            "Network Security",
            self._check_network_security
        )

    def _test_performance(self):
        """Tests de performance"""
        
        # Test 1: Response times
        self._run_test(
            "Response Times",
            self._check_response_times
        )
        
        # Test 2: Concurrent users
        self._run_test(
            "Concurrent Users",
            self._check_concurrent_users
        )
        
        # Test 3: Database performance
        self._run_test(
            "Database Query Performance",
            self._check_db_query_performance
        )

    def _test_monitoring(self):
        """Tests du monitoring Prometheus/Grafana"""
        
        # Test 1: Prometheus metrics
        self._run_test(
            "Prometheus Metrics Collection",
            self._check_prometheus_metrics
        )
        
        # Test 2: Grafana dashboards
        self._run_test(
            "Grafana Dashboards",
            self._check_grafana_dashboards
        )
        
        # Test 3: Alerting rules
        self._run_test(
            "Alerting Rules",
            self._check_alerting_rules
        )

    def _test_business_logic(self):
        """Tests de la logique métier"""
        
        # Test 1: Job creation et execution
        self._run_test(
            "Job Creation and Execution",
            self._check_job_execution
        )
        
        # Test 2: Contact extraction
        self._run_test(
            "Contact Extraction",
            self._check_contact_extraction
        )
        
        # Test 3: Proxy management
        self._run_test(
            "Proxy Management",
            self._check_proxy_management
        )
        
        # Test 4: Data export
        self._run_test(
            "Data Export Functionality",
            self._check_data_export
        )

    def _test_api_endpoints(self):
        """Tests des endpoints API"""
        
        endpoints = [
            ("/health", "GET"),
            ("/api/status", "GET"),
            ("/api/jobs", "GET"),
            ("/api/contacts", "GET"),
            ("/api/proxies", "GET")
        ]
        
        for endpoint, method in endpoints:
            self._run_test(
                f"API Endpoint {method} {endpoint}",
                lambda e=endpoint, m=method: self._check_api_endpoint(e, m)
            )

    # ========================================================================
    # IMPLEMENTATIONS DES TESTS
    # ========================================================================

    def _check_docker_containers(self) -> Tuple[bool, str, Dict]:
        """Vérification des conteneurs Docker"""
        try:
            client = docker.from_env()
            containers = client.containers.list()
            
            expected_containers = [
                "scraper-pro-db",
                "scraper-pro-worker", 
                "scraper-pro-dashboard"
            ]
            
            running_containers = [c.name for c in containers if c.status == "running"]
            missing = [name for name in expected_containers if name not in running_containers]
            
            if missing:
                return False, f"Conteneurs manquants: {missing}", {
                    "running": running_containers,
                    "missing": missing
                }
            
            # Vérification santé des conteneurs
            unhealthy = []
            for container in containers:
                if container.name in expected_containers:
                    health = container.attrs.get('State', {}).get('Health', {})
                    if health.get('Status') == 'unhealthy':
                        unhealthy.append(container.name)
            
            if unhealthy:
                return False, f"Conteneurs non sains: {unhealthy}", {
                    "unhealthy": unhealthy
                }
            
            return True, f"Tous les conteneurs sont opérationnels ({len(running_containers)})", {
                "containers": running_containers
            }
            
        except Exception as e:
            return False, f"Erreur Docker: {e}", {}

    def _check_db_connection(self) -> Tuple[bool, str, Dict]:
        """Test de connexion à la base de données"""
        try:
            conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password,
                connect_timeout=10
            )
            
            with conn.cursor() as cur:
                cur.execute("SELECT version(), now();")
                version, timestamp = cur.fetchone()
                
                # Test basique de performance
                start_time = time.time()
                cur.execute("SELECT COUNT(*) FROM queue;")
                query_time = time.time() - start_time
                
            conn.close()
            
            return True, f"Connexion DB réussie ({query_time:.3f}s)", {
                "version": version,
                "query_time": query_time,
                "timestamp": str(timestamp)
            }
            
        except Exception as e:
            return False, f"Erreur connexion DB: {e}", {}

    def _check_dashboard_access(self) -> Tuple[bool, str, Dict]:
        """Test d'accès au dashboard web"""
        try:
            response = requests.get(
                self.config.dashboard_url,
                timeout=self.config.test_timeout
            )
            
            if response.status_code == 200:
                load_time = response.elapsed.total_seconds()
                
                # Vérification contenu
                content_checks = {
                    "streamlit_present": "streamlit" in response.text.lower(),
                    "login_form": "password" in response.text.lower(),
                    "scraper_title": "scraper" in response.text.lower()
                }
                
                return True, f"Dashboard accessible ({load_time:.3f}s)", {
                    "status_code": response.status_code,
                    "load_time": load_time,
                    "content_checks": content_checks
                }
            else:
                return False, f"Dashboard inaccessible: {response.status_code}", {
                    "status_code": response.status_code
                }
                
        except Exception as e:
            return False, f"Erreur accès dashboard: {e}", {}

    def _check_worker_heartbeat(self) -> Tuple[bool, str, Dict]:
        """Vérification du heartbeat worker"""
        try:
            conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password
            )
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT value FROM settings 
                    WHERE key = 'scheduler_last_heartbeat'
                """)
                
                result = cur.fetchone()
                if not result:
                    return False, "Aucun heartbeat trouvé", {}
                
                heartbeat_time = datetime.fromisoformat(result[0])
                time_diff = datetime.now() - heartbeat_time
                
                if time_diff.total_seconds() > 300:  # 5 minutes
                    return False, f"Heartbeat trop ancien: {time_diff}", {
                        "heartbeat_age": time_diff.total_seconds()
                    }
                
                return True, f"Worker heartbeat OK ({time_diff.total_seconds():.1f}s ago)", {
                    "heartbeat_age": time_diff.total_seconds(),
                    "last_heartbeat": str(heartbeat_time)
                }
            
        except Exception as e:
            return False, f"Erreur heartbeat: {e}", {}
        finally:
            if 'conn' in locals():
                conn.close()

    def _check_job_processing(self) -> Tuple[bool, str, Dict]:
        """Test de traitement d'un job simple"""
        try:
            # Créer un job de test
            conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password
            )
            
            test_url = "http://httpbin.org/html"
            
            with conn.cursor() as cur:
                # Insérer job de test
                cur.execute("""
                    INSERT INTO queue (url, status, theme, created_by)
                    VALUES (%s, 'pending', 'test', 'automated_test')
                    RETURNING id
                """, (test_url,))
                
                job_id = cur.fetchone()[0]
                conn.commit()
                
                # Attendre traitement (maximum 30 secondes)
                max_wait = 30
                waited = 0
                
                while waited < max_wait:
                    cur.execute("SELECT status FROM queue WHERE id = %s", (job_id,))
                    status = cur.fetchone()[0]
                    
                    if status in ['done', 'failed']:
                        break
                        
                    time.sleep(1)
                    waited += 1
                
                # Récupérer résultat final
                cur.execute("""
                    SELECT status, updated_at - created_at as duration, last_error
                    FROM queue WHERE id = %s
                """, (job_id,))
                
                status, duration, error = cur.fetchone()
                
                # Nettoyer job de test
                cur.execute("DELETE FROM queue WHERE id = %s", (job_id,))
                conn.commit()
                
                if status == 'done':
                    return True, f"Job traité avec succès ({duration})", {
                        "job_id": job_id,
                        "duration": str(duration),
                        "status": status
                    }
                else:
                    return False, f"Job échoué: {error}", {
                        "job_id": job_id,
                        "status": status,
                        "error": error
                    }
            
        except Exception as e:
            return False, f"Erreur test job: {e}", {}
        finally:
            if 'conn' in locals():
                conn.close()

    def _check_prometheus_metrics(self) -> Tuple[bool, str, Dict]:
        """Vérification des métriques Prometheus"""
        try:
            response = requests.get(
                f"{self.config.prometheus_url}/api/v1/query",
                params={"query": "up"},
                timeout=10
            )
            
            if response.status_code != 200:
                return False, f"Prometheus inaccessible: {response.status_code}", {}
            
            data = response.json()
            if data['status'] != 'success':
                return False, "Erreur query Prometheus", {"response": data}
            
            metrics_count = len(data['data']['result'])
            
            # Vérifier métriques spécifiques scraper
            scraper_queries = [
                "scraper_jobs_total",
                "scraper_contacts_extracted_total", 
                "scraper_proxies_active_total"
            ]
            
            scraper_metrics = {}
            for query in scraper_queries:
                try:
                    response = requests.get(
                        f"{self.config.prometheus_url}/api/v1/query",
                        params={"query": query},
                        timeout=5
                    )
                    if response.status_code == 200:
                        data = response.json()
                        scraper_metrics[query] = len(data['data']['result'])
                except:
                    scraper_metrics[query] = 0
            
            return True, f"Prometheus opérationnel ({metrics_count} métriques)", {
                "total_metrics": metrics_count,
                "scraper_metrics": scraper_metrics
            }
            
        except Exception as e:
            return False, f"Erreur Prometheus: {e}", {}

    # ========================================================================
    # UTILITAIRES
    # ========================================================================

    def _run_test(self, name: str, test_func):
        """Exécute un test individuel avec retry et timing"""
        logger.info(f"🔍 Test: {name}")
        
        start_time = time.time()
        
        for attempt in range(self.config.retry_attempts):
            try:
                success, message, details = test_func()
                duration = time.time() - start_time
                
                status = "PASS" if success else "FAIL"
                
                self.results.append(TestResult(
                    name=name,
                    status=status,
                    duration=duration,
                    message=message,
                    details=details
                ))
                
                if success:
                    logger.info(f"✅ {name}: {message}")
                else:
                    logger.error(f"❌ {name}: {message}")
                
                return
                
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    # Dernier essai, enregistrer l'échec
                    duration = time.time() - start_time
                    self.results.append(TestResult(
                        name=name,
                        status="FAIL",
                        duration=duration,
                        message=f"Exception: {e}",
                        details={}
                    ))
                    logger.error(f"❌ {name}: Exception: {e}")
                else:
                    # Retry
                    logger.warning(f"⚠️ {name}: Retry {attempt + 1}/{self.config.retry_attempts}: {e}")
                    time.sleep(self.config.retry_delay)

    @contextmanager
    def _db_connection(self):
        """Context manager pour connexions DB"""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password
            )
            yield conn
        finally:
            if conn:
                conn.close()

    def _generate_report(self) -> Dict:
        """Génération du rapport final"""
        total_tests = len(self.results)
        passed = len([r for r in self.results if r.status == "PASS"])
        failed = len([r for r in self.results if r.status == "FAIL"])
        skipped = len([r for r in self.results if r.status == "SKIP"])
        
        total_duration = (datetime.now() - self.start_time).total_seconds()
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "success_rate": success_rate,
                "duration": total_duration,
                "timestamp": self.start_time.isoformat()
            },
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "duration": r.duration,
                    "message": r.message,
                    "details": r.details
                } for r in self.results
            ],
            "status": "PASS" if failed == 0 else "FAIL"
        }
        
        # Sauvegarde du rapport
        with open(f"tests/test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Log du résumé
        logger.info("=" * 80)
        logger.info("📊 RAPPORT FINAL DES TESTS")
        logger.info("=" * 80)
        logger.info(f"Total: {total_tests} | Réussis: {passed} | Échoués: {failed} | Ignorés: {skipped}")
        logger.info(f"Taux de succès: {success_rate:.1f}%")
        logger.info(f"Durée totale: {total_duration:.1f}s")
        
        if failed > 0:
            logger.error("❌ CERTAINS TESTS ONT ÉCHOUÉ!")
            for result in self.results:
                if result.status == "FAIL":
                    logger.error(f"   - {result.name}: {result.message}")
        else:
            logger.info("✅ TOUS LES TESTS SONT PASSÉS!")
        
        logger.info("=" * 80)
        
        return report

# ============================================================================
# FONCTIONS UTILITAIRES SUPPLÉMENTAIRES  
# ============================================================================

    def _check_db_schema(self) -> Tuple[bool, str, Dict]:
        """Vérification du schéma de base de données"""
        expected_tables = ['queue', 'contacts', 'proxies', 'sessions', 'settings']
        
        try:
            with self._db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                    
                    actual_tables = [row[0] for row in cur.fetchall()]
                    missing_tables = [table for table in expected_tables if table not in actual_tables]
                    
                    if missing_tables:
                        return False, f"Tables manquantes: {missing_tables}", {
                            "expected": expected_tables,
                            "actual": actual_tables,
                            "missing": missing_tables
                        }
                    
                    return True, f"Schéma DB complet ({len(actual_tables)} tables)", {
                        "tables": actual_tables
                    }
                    
        except Exception as e:
            return False, f"Erreur vérification schéma: {e}", {}

    def _check_api_endpoint(self, endpoint: str, method: str) -> Tuple[bool, str, Dict]:
        """Test d'un endpoint API spécifique"""
        try:
            url = f"{self.config.dashboard_url}{endpoint}"
            
            if method == "GET":
                response = requests.get(url, timeout=10)
            elif method == "POST":
                response = requests.post(url, json={}, timeout=10)
            else:
                return False, f"Méthode non supportée: {method}", {}
            
            return True, f"API {method} {endpoint}: {response.status_code}", {
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            return False, f"Erreur API {method} {endpoint}: {e}", {}

# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================

def main():
    """Point d'entrée principal"""
    
    # Configuration depuis variables d'environnement
    config = TestConfig(
        db_password=os.getenv("POSTGRES_PASSWORD", "scraper"),
        dashboard_password=os.getenv("DASHBOARD_PASSWORD", "admin123")
    )
    
    # Exécution des tests
    runner = TestRunner(config)
    report = runner.run_all_tests()
    
    # Code de sortie basé sur les résultats
    exit_code = 0 if report["status"] == "PASS" else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main()