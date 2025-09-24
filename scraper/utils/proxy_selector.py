#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROXY_SELECTOR.PY - VERSION CORRIGÉE v2.1
Version: 2.1 Production-Ready Fixed
Description: Sélecteur de proxies avec configuration DB cohérente et gestion d'erreur robuste
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

# Configuration base de données CORRIGÉE pour cohérence
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),  # CORRIGÉ: cohérent avec docker-compose
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),  # CORRIGÉ: cohérent
    'password': os.getenv("POSTGRES_PASSWORD"),  # CORRIGÉ: pas de valeur par défaut hardcodée
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "30")),
    'application_name': 'proxy_selector'  # CORRIGÉ: nom plus spécifique
}

def load_config() -> Dict[str, Any]:
    """Charge la configuration des proxies avec valeurs par défaut robustes"""
    default_config = {
        "rotation_mode": os.getenv("PROXY_ROTATION_DEFAULT_MODE", "weighted_random"),
        "weights": {"default": 1.0},
        "sticky_ttl_seconds": int(os.getenv("PROXY_STICKY_TTL_DEFAULT", "300")),
        "cooldown_seconds": int(os.getenv("PROXY_COOLDOWN_SECONDS", "120")),
        "max_consecutive_failures": int(os.getenv("PROXY_MAX_FAILURES", "3")),
        "circuit_breaker_failures": int(os.getenv("PROXY_CIRCUIT_BREAKER_THRESHOLD", "5")),
        "circuit_breaker_cooldown_seconds": int(os.getenv("PROXY_CIRCUIT_BREAKER_COOLDOWN", "600"))
    }
    
    try:
        cfg_path = Path(os.getenv("PROXY_CONFIG_PATH", "config/proxy_config.json"))
        if cfg_path.exists():
            with open(cfg_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # Fusion avec les valeurs par défaut (les env vars ont priorité)
                for key, value in loaded_config.items():
                    if key not in ["rotation_mode", "sticky_ttl_seconds", "cooldown_seconds", "max_consecutive_failures", "circuit_breaker_failures", "circuit_breaker_cooldown_seconds"]:
                        default_config[key] = value
                        
                logger.debug(f"Configuration proxy chargée depuis {cfg_path}")
        else:
            logger.info(f"Fichier config proxy non trouvé ({cfg_path}), utilisation valeurs par défaut")
    except Exception as e:
        logger.warning(f"Erreur chargement config proxy: {e}, utilisation valeurs par défaut")
    
    logger.debug(f"Configuration proxy finale: rotation_mode={default_config['rotation_mode']}")
    return default_config

def get_db_connection() -> Optional[psycopg2.connection]:
    """
    Obtient une connexion à la base de données avec gestion d'erreur robuste
    """
    try:
        # Vérifier que le password est défini
        if not DB_CONFIG['password']:
            logger.error("POSTGRES_PASSWORD non défini dans les variables d'environnement")
            return None
            
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug("Connexion DB proxy selector établie")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erreur PostgreSQL lors connexion proxy selector: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue connexion DB proxy: {e}")
        return None

def fetch_active_proxies() -> List[Dict[str, Any]]:
    """Récupère la liste des proxies actifs avec gestion d'erreur robuste"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Impossible de se connecter à la base de données")
            return []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Requête optimisée avec plus d'informations
            cur.execute("""
                SELECT 
                    id, scheme, host, port, username, password, priority, 
                    success_rate, response_time_ms, last_used_at, active,
                    consecutive_failures, cooldown_until, weight,
                    total_requests, successful_requests, failed_requests,
                    last_success_at, last_failure_at, average_latency_ms,
                    circuit_breaker_status, circuit_breaker_failures,
                    circuit_breaker_last_failure, circuit_breaker_next_attempt,
                    country_code, provider, label
                FROM proxies
                WHERE active = true 
                  AND (cooldown_until IS NULL OR cooldown_until < NOW())
                  AND (circuit_breaker_status != 'open' OR circuit_breaker_next_attempt < NOW())
                ORDER BY 
                    CASE WHEN circuit_breaker_status = 'closed' THEN 1
                         WHEN circuit_breaker_status = 'half_open' THEN 2
                         ELSE 3 END,
                    priority ASC, 
                    COALESCE(success_rate, 1.0) DESC,
                    COALESCE(average_latency_ms, response_time_ms, 1000) ASC,
                    COALESCE(last_used_at, '1970-01-01') ASC
            """)
            
            rows = cur.fetchall()
            proxies = [dict(row) for row in rows]
        
        conn.close()
        
        logger.debug(f"Récupéré {len(proxies)} proxies actifs depuis la base de données")
        
        # Log détaillé en mode verbose
        if logger.isEnabledFor(logging.DEBUG):
            for proxy in proxies[:3]:  # Afficher les 3 premiers
                logger.debug(f"Proxy {proxy['id']}: {proxy['host']}:{proxy['port']} "
                           f"(success_rate={proxy.get('success_rate', 'N/A')}, "
                           f"latency={proxy.get('average_latency_ms', 'N/A')}ms)")
        
        return proxies
        
    except psycopg2.Error as e:
        logger.error(f"Erreur PostgreSQL lors récupération proxies: {e}")
        return []
    except Exception as e:
        logger.error(f"Erreur lors récupération proxies: {e}")
        return []

def select_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Sélectionne un proxy pour un job donné avec failover automatique et logging détaillé
    
    Args:
        job_id: ID du job (optionnel, pour sticky sessions)
    
    Returns:
        Dictionnaire du proxy sélectionné ou None
    """
    try:
        # Charger configuration avec variables d'environnement
        config = load_config()
        
        # Récupérer proxies actifs
        all_proxies = fetch_active_proxies()
        if not all_proxies:
            logger.warning("Aucun proxy actif disponible dans la base de données")
            return None
        
        logger.debug(f"Évaluation de {len(all_proxies)} proxies pour sélection")
        
        # Filtrer proxies utilisables (circuit breaker, cooldown, etc.)
        usable_proxies = []
        for proxy in all_proxies:
            try:
                if can_use(proxy):
                    usable_proxies.append(proxy)
                    logger.debug(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) utilisable")
                else:
                    logger.debug(f"Proxy {proxy['id']} ({proxy['host']}:{proxy['port']}) non utilisable "
                               f"(circuit breaker ou failover)")
            except Exception as e:
                logger.warning(f"Erreur évaluation proxy {proxy.get('id', 'unknown')}: {e}")
                continue
        
        if not usable_proxies:
            logger.warning(f"Aucun proxy utilisable après filtrage failover. "
                         f"Total évalués: {len(all_proxies)}")
            
            # Log des raisons pourquoi les proxies ne sont pas utilisables
            for proxy in all_proxies[:5]:  # Log les 5 premiers pour debug
                logger.debug(f"Proxy {proxy['id']}: cooldown_until={proxy.get('cooldown_until')}, "
                           f"circuit_breaker_status={proxy.get('circuit_breaker_status')}, "
                           f"consecutive_failures={proxy.get('consecutive_failures')}")
            return None
        
        logger.debug(f"Proxies utilisables après filtrage: {len(usable_proxies)}")
        
        # Sélection selon la stratégie configurée
        rotation_mode = config.get("rotation_mode", "weighted_random")
        logger.debug(f"Mode de rotation: {rotation_mode}")
        
        selected_proxy = choose(
            proxies=usable_proxies,
            mode=rotation_mode,
            weights=config.get("weights", {}),
            job_id=job_id,
            sticky_ttl=config.get("sticky_ttl_seconds", 300)
        )
        
        if selected_proxy:
            # Log détaillé du proxy sélectionné
            logger.info(f"Proxy sélectionné: {selected_proxy['host']}:{selected_proxy['port']} "
                       f"(ID: {selected_proxy['id']}, mode: {rotation_mode}, "
                       f"priority: {selected_proxy.get('priority', 'N/A')}, "
                       f"success_rate: {selected_proxy.get('success_rate', 'N/A')})")
            
            # Mise à jour de la dernière utilisation
            try:
                update_proxy_usage(selected_proxy['id'])
            except Exception as e:
                logger.warning(f"Impossible de mettre à jour usage proxy {selected_proxy['id']}: {e}")
                # Continue même si la mise à jour échoue
        else:
            logger.warning("Aucun proxy sélectionné par l'algorithme de choix")
        
        return selected_proxy
        
    except Exception as e:
        logger.error(f"Erreur lors sélection proxy: {e}", exc_info=True)
        return None

def update_proxy_usage(proxy_id: int):
    """Met à jour les statistiques d'usage d'un proxy avec gestion d'erreur robuste"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.warning(f"Impossible de se connecter pour mise à jour proxy {proxy_id}")
            return
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE proxies SET
                    last_used_at = NOW(),
                    total_requests = COALESCE(total_requests, 0) + 1,
                    updated_at = NOW()
                WHERE id = %s
            """, (proxy_id,))
            
            if cur.rowcount == 0:
                logger.warning(f"Aucun proxy trouvé avec ID {proxy_id} pour mise à jour")
            else:
                logger.debug(f"Usage proxy {proxy_id} mis à jour")
                
        conn.commit()
        conn.close()
        
    except psycopg2.Error as e:
        logger.warning(f"Erreur PostgreSQL mise à jour usage proxy {proxy_id}: {e}")
    except Exception as e:
        logger.warning(f"Erreur mise à jour usage proxy {proxy_id}: {e}")

def get_proxy_stats() -> Dict[str, Any]:
    """Récupère les statistiques globales des proxies avec informations enrichies"""
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_proxies,
                    COUNT(*) FILTER (WHERE active = true) as active_proxies,
                    COUNT(*) FILTER (WHERE active = true AND (cooldown_until IS NULL OR cooldown_until < NOW())) as usable_proxies,
                    COUNT(*) FILTER (WHERE consecutive_failures >= %s) as blocked_proxies,
                    COUNT(*) FILTER (WHERE circuit_breaker_status = 'open') as circuit_breaker_open,
                    COUNT(*) FILTER (WHERE circuit_breaker_status = 'half_open') as circuit_breaker_half_open,
                    ROUND(AVG(success_rate) FILTER (WHERE active = true AND success_rate IS NOT NULL), 3) as avg_success_rate,
                    ROUND(AVG(average_latency_ms) FILTER (WHERE active = true AND average_latency_ms > 0), 1) as avg_response_time,
                    COUNT(*) FILTER (WHERE last_used_at >= NOW() - INTERVAL '1 hour') as recently_used,
                    COUNT(*) FILTER (WHERE last_used_at >= NOW() - INTERVAL '24 hours') as used_today,
                    COUNT(DISTINCT country_code) FILTER (WHERE active = true AND country_code IS NOT NULL) as countries_available,
                    COUNT(DISTINCT provider) FILTER (WHERE active = true AND provider IS NOT NULL) as providers_available,
                    MAX(last_used_at) as last_proxy_used,
                    SUM(total_requests) FILTER (WHERE active = true) as total_requests_today
                FROM proxies
            """, (int(os.getenv("PROXY_MAX_FAILURES", "3")),))
            
            result = cur.fetchone()
        
        conn.close()
        
        stats = dict(result) if result else {}
        logger.debug(f"Statistiques proxies récupérées: {len(stats)} métriques")
        return stats
        
    except Exception as e:
        logger.error(f"Erreur récupération stats proxies: {e}")
        return {}

def health_check() -> Dict[str, Any]:
    """Vérification de santé du système de proxies avec diagnostic détaillé"""
    try:
        config = load_config()
        stats = get_proxy_stats()
        
        # Critères de santé configurables
        min_usable_proxies = int(os.getenv("MIN_USABLE_PROXIES", "3"))
        min_success_rate = float(os.getenv("MIN_SUCCESS_RATE", "0.7"))
        max_response_time = int(os.getenv("MAX_RESPONSE_TIME", "5000"))
        
        health_status = {
            "status": "healthy",
            "timestamp": str(datetime.now()),
            "config": {
                "rotation_mode": config.get("rotation_mode"),
                "sticky_ttl": config.get("sticky_ttl_seconds"),
                "max_failures": config.get("max_consecutive_failures"),
                "circuit_breaker_threshold": config.get("circuit_breaker_failures")
            },
            "stats": stats,
            "checks": {},
            "recommendations": []
        }
        
        # Vérifications avec recommandations
        usable_proxies = stats.get("usable_proxies", 0)
        if usable_proxies < min_usable_proxies:
            health_status["status"] = "warning"
            health_status["checks"]["usable_proxies"] = {
                "status": "warning",
                "message": f"Seulement {usable_proxies} proxies utilisables (minimum: {min_usable_proxies})",
                "current": usable_proxies,
                "threshold": min_usable_proxies
            }
            health_status["recommendations"].append("Ajouter plus de proxies ou vérifier la configuration des proxies existants")
        
        avg_success_rate = stats.get("avg_success_rate", 0)
        if avg_success_rate and avg_success_rate < min_success_rate:
            health_status["status"] = "warning"
            health_status["checks"]["success_rate"] = {
                "status": "warning", 
                "message": f"Taux succès moyen: {avg_success_rate} (minimum: {min_success_rate})",
                "current": avg_success_rate,
                "threshold": min_success_rate
            }
            health_status["recommendations"].append("Vérifier la qualité des proxies ou ajuster les paramètres de circuit breaker")
        
        avg_response_time = stats.get("avg_response_time", 0)
        if avg_response_time and avg_response_time > max_response_time:
            health_status["status"] = "warning"
            health_status["checks"]["response_time"] = {
                "status": "warning",
                "message": f"Temps réponse moyen: {avg_response_time}ms (maximum: {max_response_time}ms)",
                "current": avg_response_time,
                "threshold": max_response_time
            }
            health_status["recommendations"].append("Considérer l'utilisation de proxies plus rapides ou augmenter les timeouts")
        
        # Vérifications supplémentaires
        blocked_proxies = stats.get("blocked_proxies", 0)
        total_proxies = stats.get("total_proxies", 1)
        blocked_ratio = blocked_proxies / total_proxies if total_proxies > 0 else 0
        
        if blocked_ratio > 0.5:  # Plus de 50% bloqués
            health_status["status"] = "critical"
            health_status["checks"]["blocked_ratio"] = {
                "status": "critical",
                "message": f"Trop de proxies bloqués: {blocked_proxies}/{total_proxies} ({blocked_ratio:.1%})",
                "current": blocked_ratio,
                "threshold": 0.5
            }
            health_status["recommendations"].append("Réduire le taux de requêtes ou renouveler les proxies")
        
        # Circuit breakers ouverts
        cb_open = stats.get("circuit_breaker_open", 0)
        if cb_open > 0:
            health_status["checks"]["circuit_breakers"] = {
                "status": "info",
                "message": f"{cb_open} circuit breakers ouverts (protection active)",
                "current": cb_open
            }
        
        logger.debug(f"Health check proxy système: {health_status['status']}")
        return health_status
        
    except Exception as e:
        return {
            "status": "error",
            "timestamp": str(datetime.now()),
            "error": str(e),
            "stats": {},
            "checks": {},
            "recommendations": ["Vérifier les logs pour plus de détails sur l'erreur"]
        }

def get_proxy_performance_report() -> Dict[str, Any]:
    """
    NOUVEAU: Génère un rapport de performance détaillé des proxies
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Top performers
            cur.execute("""
                SELECT id, host, port, success_rate, average_latency_ms, total_requests,
                       last_used_at, country_code, provider
                FROM proxies 
                WHERE active = true AND success_rate IS NOT NULL
                ORDER BY success_rate DESC, average_latency_ms ASC
                LIMIT 10
            """)
            top_performers = [dict(row) for row in cur.fetchall()]
            
            # Problematic proxies
            cur.execute("""
                SELECT id, host, port, success_rate, consecutive_failures,
                       circuit_breaker_status, last_failure_at, country_code
                FROM proxies 
                WHERE active = true AND 
                      (consecutive_failures >= 3 OR circuit_breaker_status != 'closed')
                ORDER BY consecutive_failures DESC, last_failure_at DESC
                LIMIT 10
            """)
            problematic_proxies = [dict(row) for row in cur.fetchall()]
            
            # Usage statistics
            cur.execute("""
                SELECT 
                    DATE(last_used_at) as usage_date,
                    COUNT(*) as proxies_used,
                    AVG(success_rate) as avg_success_rate,
                    SUM(total_requests) as total_requests
                FROM proxies 
                WHERE last_used_at >= NOW() - INTERVAL '7 days'
                  AND active = true
                GROUP BY DATE(last_used_at)
                ORDER BY usage_date DESC
            """)
            usage_history = [dict(row) for row in cur.fetchall()]
        
        conn.close()
        
        return {
            "generated_at": str(datetime.now()),
            "top_performers": top_performers,
            "problematic_proxies": problematic_proxies,
            "usage_history": usage_history,
            "summary": {
                "total_active": len(top_performers) + len(problematic_proxies),
                "performance_issues": len(problematic_proxies),
                "health_score": max(0, min(100, (len(top_performers) / max(1, len(top_performers) + len(problematic_proxies))) * 100))
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur génération rapport performance: {e}")
        return {}

# Fonction de compatibilité (alias)
def acquire_proxy(job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Alias pour select_proxy pour compatibilité avec l'ancien code"""
    return select_proxy(job_id)

# Import datetime pour les fonctions qui en ont besoin
from datetime import datetime