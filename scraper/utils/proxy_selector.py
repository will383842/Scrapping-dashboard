#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROXY_SELECTOR.PY - CORRECTED VERSION
Version: 2.1 Production-Ready Fixed
Description: Sélecteur de proxies avec configuration DB cohérente
"""

import os
import json
import logging
import psycopg2
from typing import List, Dict, Any, Optional
from psycopg2.extras import RealDictCursor
from pathlib import Path

# Imports des modules proxy
from .proxy_rotation import choose
from .proxy_failover import can_use
from .redis_coordination import _ns

# Configuration logging
logger = logging.getLogger(__name__)

# Configuration base de données CORRIGÉE
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),  # CORRIGÉ: cohérent
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),  # CORRIGÉ: cohérent
    'password': os.getenv("POSTGRES_PASSWORD", "scraper_admin"),  # CORRIGÉ: cohérent
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10"))
}

def load_config() -> Dict[str, Any]:
    """Charge la configuration des proxies avec valeurs par défaut robustes"""
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

def fetch_active_proxies() -> List[Dict[str, Any]]:
    """Récupère la liste des proxies actifs avec gestion d'erreur robuste"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id, scheme, host, port, username, password, priority, 
                    success_rate, response_time_ms, last_used_at, active,
                    consecutive_failures, cooldown_until, weight
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
        
    except psycopg2.Error as e:
        logger.error(f"Erreur PostgreSQL lors récupération proxies: {e}")
        return []
    except Exception as e:
        logger.error(f"Erreur lors récupération proxies: {e}")
        return []

def select_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Sélectionne un proxy pour un job donné avec failover automatique
    
    Args:
        job_id: ID du job (optionnel, pour sticky sessions)
    
    Returns:
        Dictionnaire du proxy sélectionné ou None
    """
    try:
        # Charger configuration
        config = load_config()
        
        # Récupérer proxies actifs
        all_proxies = fetch_active_proxies()
        if not all_proxies:
            logger.warning("Aucun proxy actif disponible")
            return None
        
        # Filtrer proxies utilisables (circuit breaker, cooldown, etc.)
        usable_proxies = []
        for proxy in all_proxies:
            if can_use(proxy):
                usable_proxies.append(proxy)
            else:
                logger.debug(f"Proxy {proxy['host']}:{proxy['port']} non utilisable (circuit breaker ou cooldown)")
        
        if not usable_proxies:
            logger.warning("Aucun proxy utilisable après filtrage failover")
            return None
        
        # Sélection selon la stratégie configurée
        selected_proxy = choose(
            proxies=usable_proxies,
            mode=config.get("rotation_mode", "weighted_random"),
            weights=config.get("weights"),
            job_id=job_id,
            sticky_ttl=config.get("sticky_ttl_seconds", 300)
        )
        
        if selected_proxy:
            logger.info(f"Proxy sélectionné: {selected_proxy['host']}:{selected_proxy['port']} "
                       f"(mode: {config.get('rotation_mode')})")
            
            # Mise à jour de la dernière utilisation
            try:
                update_proxy_usage(selected_proxy['id'])
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour usage proxy {selected_proxy['id']}: {e}")
        else:
            logger.warning("Aucun proxy sélectionné par l'algorithme de choix")
        
        return selected_proxy
        
    except Exception as e:
        logger.error(f"Erreur lors sélection proxy: {e}")
        return None

def update_proxy_usage(proxy_id: int):
    """Met à jour les statistiques d'usage d'un proxy"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE proxies SET
                    last_used_at = NOW(),
                    total_requests = COALESCE(total_requests, 0) + 1,
                    updated_at = NOW()
                WHERE id = %s
            """, (proxy_id,))
            
        conn.commit()
        conn.close()
        
        logger.debug(f"Usage proxy {proxy_id} mis à jour")
        
    except psycopg2.Error as e:
        logger.warning(f"Erreur PostgreSQL mise à jour usage proxy {proxy_id}: {e}")
    except Exception as e:
        logger.warning(f"Erreur mise à jour usage proxy {proxy_id}: {e}")

def get_proxy_stats() -> Dict[str, Any]:
    """Récupère les statistiques globales des proxies"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_proxies,
                    COUNT(*) FILTER (WHERE active = true) as active_proxies,
                    COUNT(*) FILTER (WHERE active = true AND (cooldown_until IS NULL OR cooldown_until < NOW())) as usable_proxies,
                    COUNT(*) FILTER (WHERE consecutive_failures >= 5) as blocked_proxies,
                    ROUND(AVG(success_rate) FILTER (WHERE active = true), 3) as avg_success_rate,
                    ROUND(AVG(response_time_ms) FILTER (WHERE active = true AND response_time_ms > 0), 1) as avg_response_time,
                    COUNT(*) FILTER (WHERE last_used_at >= NOW() - INTERVAL '1 hour') as recently_used
                FROM proxies
            """)
            
            result = cur.fetchone()
        
        conn.close()
        
        return dict(result) if result else {}
        
    except Exception as e:
        logger.error(f"Erreur récupération stats proxies: {e}")
        return {}

def health_check() -> Dict[str, Any]:
    """Vérification de santé du système de proxies"""
    try:
        config = load_config()
        stats = get_proxy_stats()
        
        # Critères de santé
        min_usable_proxies = int(os.getenv("MIN_USABLE_PROXIES", "3"))
        min_success_rate = float(os.getenv("MIN_SUCCESS_RATE", "0.7"))
        max_response_time = int(os.getenv("MAX_RESPONSE_TIME", "5000"))
        
        health_status = {
            "status": "healthy",
            "config": config,
            "stats": stats,
            "checks": {}
        }
        
        # Vérifications
        if stats.get("usable_proxies", 0) < min_usable_proxies:
            health_status["status"] = "warning"
            health_status["checks"]["usable_proxies"] = f"Seulement {stats.get('usable_proxies', 0)} proxies utilisables (minimum: {min_usable_proxies})"
        
        if stats.get("avg_success_rate", 0) < min_success_rate:
            health_status["status"] = "warning"
            health_status["checks"]["success_rate"] = f"Taux succès moyen: {stats.get('avg_success_rate', 0)} (minimum: {min_success_rate})"
        
        if stats.get("avg_response_time", 0) > max_response_time:
            health_status["status"] = "warning" 
            health_status["checks"]["response_time"] = f"Temps réponse moyen: {stats.get('avg_response_time', 0)}ms (maximum: {max_response_time}ms)"
        
        return health_status
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "stats": {},
            "checks": {}
        }

# Fonction de compatibilité (alias)
def acquire_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Alias pour select_proxy pour compatibilité"""
    return select_proxy(job_id)