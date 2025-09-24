#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROXY.PY - GESTION DES PROXIES (VERSION CORRIGÉE)
Version: 2.0 Production-Ready Fixed
Description: Gestion des proxies sans dépendances problématiques
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration logging
logger = logging.getLogger(__name__)

# Configuration base de données
DB_CONFIG = dict(
    host=os.getenv("POSTGRES_HOST", "db"), 
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper_pro"), 
    user=os.getenv("POSTGRES_USER", "scraper_admin"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper_admin")
)

# ======================================================================
# CONFIGURATION DES PROXIES (SIMPLIFIÉE)
# ======================================================================

def load_config() -> Dict[str, Any]:
    """Charge la configuration des proxies avec valeurs par défaut"""
    default_config = {
        "rotation_mode": "weighted_random",
        "weights": {"default": 1.0},
        "sticky_ttl_seconds": 300,
        "cooldown_seconds": 120,
        "max_consecutive_failures": 3,
        "circuit_breaker_failures": 5,
        "circuit_breaker_cooldown_seconds": 600
    }
    
    try:
        cfg_path = Path(os.getenv("PROXY_CONFIG_PATH", "config/proxy_config.json"))
        if cfg_path.exists():
            with open(cfg_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # Fusion avec les valeurs par défaut
                default_config.update(loaded_config)
                logger.debug(f"Configuration proxy chargée depuis {cfg_path}")
        else:
            logger.info(f"Fichier config proxy non trouvé ({cfg_path}), utilisation valeurs par défaut")
    except Exception as e:
        logger.warning(f"Erreur chargement config proxy: {e}, utilisation valeurs par défaut")
    
    return default_config

# ======================================================================
# SÉLECTION ET GESTION DES PROXIES
# ======================================================================

def fetch_active_proxies() -> List[Dict[str, Any]]:
    """Récupère la liste des proxies actifs depuis la base de données"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=10)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, scheme, host, port, username, password, priority,
                       success_rate, response_time_ms, last_used_at, active,
                       consecutive_failures, cooldown_until
                FROM proxies
                WHERE active = true 
                  AND (cooldown_until IS NULL OR cooldown_until < NOW())
                ORDER BY 
                    priority ASC, 
                    COALESCE(success_rate, 1.0) DESC,
                    COALESCE(response_time_ms, 0) ASC,
                    COALESCE(last_used_at, '1970-01-01') ASC
            """)
            
            rows = cur.fetchall()
            proxies = [dict(row) for row in rows]
            
        conn.close()
        
        logger.debug(f"Récupéré {len(proxies)} proxies actifs")
        return proxies
        
    except Exception as e:
        logger.error(f"Erreur récupération proxies: {e}")
        return []

def can_use_proxy(proxy: Dict[str, Any]) -> bool:
    """Vérifie si un proxy peut être utilisé (circuit breaker simple)"""
    try:
        # Vérification simple basée sur les échecs consécutifs
        max_failures = int(os.getenv("PROXY_MAX_FAILURES", "5"))
        consecutive_failures = proxy.get("consecutive_failures", 0)
        
        if consecutive_failures >= max_failures:
            logger.debug(f"Proxy {proxy['host']}:{proxy['port']} bloqué (trop d'échecs: {consecutive_failures})")
            return False
            
        return True
        
    except Exception as e:
        logger.warning(f"Erreur vérification proxy: {e}")
        return True  # En cas d'erreur, on autorise l'utilisation

def select_proxy_simple(proxies: List[Dict[str, Any]], mode: str = "round_robin") -> Optional[Dict[str, Any]]:
    """Sélection simple de proxy sans dépendances Redis"""
    if not proxies:
        return None
    
    # Filtrer les proxies utilisables
    usable_proxies = [p for p in proxies if can_use_proxy(p)]
    
    if not usable_proxies:
        logger.warning("Aucun proxy utilisable trouvé")
        return None
    
    # Sélection selon le mode (simplifié)
    if mode == "best_performance":
        # Sélection du meilleur proxy basé sur success_rate et response_time
        best_proxy = max(usable_proxies, key=lambda p: (
            p.get('success_rate', 0.5),
            -p.get('response_time_ms', 1000)
        ))
        return best_proxy
    elif mode == "random":
        import random
        return random.choice(usable_proxies)
    else:
        # Mode par défaut: premier proxy disponible (round-robin simplifié)
        return usable_proxies[0]

def select_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Sélection d'un proxy pour un job donné"""
    try:
        config = load_config()
        proxies = fetch_active_proxies()
        
        if not proxies:
            logger.warning("Aucun proxy actif disponible")
            return None
        
        # Sélection selon la configuration
        mode = config.get("rotation_mode", "round_robin")
        selected_proxy = select_proxy_simple(proxies, mode)
        
        if selected_proxy:
            logger.info(f"Proxy sélectionné: {selected_proxy['host']}:{selected_proxy['port']}")
            # Mise à jour de la dernière utilisation
            try:
                update_proxy_usage(selected_proxy['id'])
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour l'usage du proxy: {e}")
        
        return selected_proxy
        
    except Exception as e:
        logger.error(f"Erreur sélection proxy: {e}")
        return None

def update_proxy_usage(proxy_id: int):
    """Met à jour les statistiques d'usage d'un proxy"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE proxies SET
                    last_used_at = NOW(),
                    total_requests = COALESCE(total_requests, 0) + 1
                WHERE id = %s
            """, (proxy_id,))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.warning(f"Erreur mise à jour usage proxy {proxy_id}: {e}")

# ======================================================================
# CONVERSION ET FORMATAGE
# ======================================================================

def to_scrapy_proxy_uri(proxy: Dict[str, Any]) -> str:
    """Convertit un proxy en URI Scrapy"""
    try:
        scheme = proxy.get("scheme", "http")
        host = proxy["host"]
        port = proxy["port"]
        username = proxy.get("username")
        password = proxy.get("password")
        
        if username:
            auth = f"{username}:{password or ''}"
            return f"{scheme}://{auth}@{host}:{port}"
        else:
            return f"{scheme}://{host}:{port}"
            
    except Exception as e:
        logger.error(f"Erreur formatage URI proxy: {e}")
        return ""

def to_playwright_config(proxy: Dict[str, Any]) -> Dict[str, Any]:
    """Convertit un proxy en configuration Playwright"""
    try:
        config = {
            "server": f"{proxy.get('scheme', 'http')}://{proxy['host']}:{proxy['port']}"
        }
        
        if proxy.get("username"):
            config["username"] = proxy["username"]
            config["password"] = proxy.get("password", "")
        
        return config
        
    except Exception as e:
        logger.error(f"Erreur conversion Playwright: {e}")
        return {}

# ======================================================================
# GESTION DES RÉSULTATS ET FEEDBACK
# ======================================================================

def report_proxy_result(proxy: Dict[str, Any], success: bool, response_time_ms: int = None):
    """Signale le résultat d'utilisation d'un proxy"""
    try:
        proxy_id = proxy.get("id")
        if not proxy_id:
            return
        
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
        with conn.cursor() as cur:
            if success:
                # Succès: réinitialiser les échecs consécutifs
                cur.execute("""
                    UPDATE proxies SET
                        successful_requests = COALESCE(successful_requests, 0) + 1,
                        consecutive_failures = 0,
                        last_success_at = NOW(),
                        response_time_ms = CASE 
                            WHEN %s IS NOT NULL THEN %s 
                            ELSE response_time_ms 
                        END,
                        success_rate = CASE 
                            WHEN total_requests > 0 THEN 
                                successful_requests::float / total_requests 
                            ELSE 1.0 
                        END
                    WHERE id = %s
                """, (response_time_ms, response_time_ms, proxy_id))
            else:
                # Échec: incrémenter les échecs
                cur.execute("""
                    UPDATE proxies SET
                        failed_requests = COALESCE(failed_requests, 0) + 1,
                        consecutive_failures = COALESCE(consecutive_failures, 0) + 1,
                        last_failure_at = NOW(),
                        success_rate = CASE 
                            WHEN total_requests > 0 THEN 
                                COALESCE(successful_requests, 0)::float / total_requests 
                            ELSE 0.5 
                        END,
                        cooldown_until = CASE 
                            WHEN consecutive_failures >= %s THEN 
                                NOW() + INTERVAL '%s seconds'
                            ELSE cooldown_until
                        END
                    WHERE id = %s
                """, (
                    int(os.getenv("PROXY_MAX_FAILURES", "5")),
                    int(os.getenv("PROXY_COOLDOWN_SECONDS", "300")),
                    proxy_id
                ))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Résultat proxy {proxy_id} signalé: {'succès' if success else 'échec'}")
        
    except Exception as e:
        logger.warning(f"Erreur signalement résultat proxy: {e}")

# ======================================================================
# FONCTIONS PRINCIPALES D'INTERFACE
# ======================================================================

def acquire_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Acquiert un proxy pour un job (fonction principale)"""
    try:
        return select_proxy(job_id)
    except Exception as e:
        logger.error(f"Erreur acquisition proxy: {e}")
        return None

def report_proxy_outcome(proxy: Dict[str, Any], success: bool, response_time_ms: int = None):
    """Signale l'outcome d'utilisation d'un proxy (fonction principale)"""
    try:
        report_proxy_result(proxy, success, response_time_ms)
    except Exception as e:
        logger.warning(f"Erreur signalement outcome: {e}")

def get_proxy_stats() -> Dict[str, Any]:
    """Récupère les statistiques globales des proxies"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=5)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_proxies,
                    COUNT(*) FILTER (WHERE active = true) as active_proxies,
                    COUNT(*) FILTER (WHERE consecutive_failures >= %s) as blocked_proxies,
                    AVG(success_rate) FILTER (WHERE active = true) as avg_success_rate,
                    AVG(response_time_ms) FILTER (WHERE active = true AND response_time_ms > 0) as avg_response_time
                FROM proxies
            """, (int(os.getenv("PROXY_MAX_FAILURES", "5")),))
            
            result = cur.fetchone()
            
        conn.close()
        
        return dict(result) if result else {}
        
    except Exception as e:
        logger.error(f"Erreur récupération stats proxies: {e}")
        return {}

# ======================================================================
# UTILITAIRES DE TEST
# ======================================================================

def test_proxy_connection(proxy: Dict[str, Any], timeout: int = 10) -> tuple[bool, str]:
    """Test simple de connexion à un proxy"""
    try:
        import requests
        
        proxy_url = to_scrapy_proxy_uri(proxy)
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # Test avec httpbin
        response = requests.get(
            'http://httpbin.org/ip',
            proxies=proxies,
            timeout=timeout
        )
        
        if response.status_code == 200:
            return True, f"Proxy fonctionnel (IP: {response.json().get('origin', 'unknown')})"
        else:
            return False, f"Réponse HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"Erreur connexion: {e}"

# ======================================================================
# POINT D'ENTRÉE POUR TESTS
# ======================================================================

if __name__ == "__main__":
    # Test simple
    logging.basicConfig(level=logging.DEBUG)
    
    print("Test du module proxy...")
    
    # Test récupération proxies
    proxies = fetch_active_proxies()
    print(f"Proxies actifs trouvés: {len(proxies)}")
    
    if proxies:
        # Test sélection
        proxy = select_proxy()
        if proxy:
            print(f"Proxy sélectionné: {proxy['host']}:{proxy['port']}")
            
            # Test conversion
            scrapy_uri = to_scrapy_proxy_uri(proxy)
            print(f"URI Scrapy: {scrapy_uri}")
            
            playwright_config = to_playwright_config(proxy)
            print(f"Config Playwright: {playwright_config}")
        else:
            print("Aucun proxy sélectionné")
    
    # Stats
    stats = get_proxy_stats()
    print(f"Stats: {stats}")
    
    print("Test terminé.")