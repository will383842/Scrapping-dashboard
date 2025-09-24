#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIPELINES.PY - VERSION CORRIGÉE v2.1
Version: 2.1 Production-Ready Fixed
Description: Pipeline PostgreSQL avec pool de connexions, gestion d'erreur robuste et configuration cohérente
"""

import os
import re
import logging
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional, Dict, Any
from datetime import datetime

# Configuration logging
logger = logging.getLogger(__name__)

# Configuration base de données CORRIGÉE pour cohérence totale
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),  # CORRIGÉ: cohérent avec docker-compose
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),  # CORRIGÉ: cohérent
    'password': os.getenv("POSTGRES_PASSWORD"),  # CORRIGÉ: pas de valeur par défaut hardcodée
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "30")),
    'application_name': 'scrapy_pipeline'  # CORRIGÉ: nom plus spécifique
}

# Pool de connexions global avec gestion d'erreur améliorée
_db_pool = None
_pool_lock = False  # Simple protection contre les accès concurrents

def get_db_pool():
    """Obtient le pool de connexions global avec gestion d'erreur robuste"""
    global _db_pool, _pool_lock
    
    if _db_pool is None and not _pool_lock:
        _pool_lock = True
        try:
            # Vérifier que le password est défini
            if not DB_CONFIG['password']:
                logger.error("POSTGRES_PASSWORD non défini dans les variables d'environnement")
                return None
                
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=int(os.getenv("DB_POOL_MIN", "1")),
                maxconn=int(os.getenv("CONNECTION_POOL_SIZE", "20")),  # Augmenté pour performance
                **DB_CONFIG
            )
            logger.info(f"Pool de connexions DB pipeline initialisé (min={os.getenv('DB_POOL_MIN', '1')}, "
                       f"max={os.getenv('CONNECTION_POOL_SIZE', '20')})")
        except psycopg2.Error as e:
            logger.error(f"Erreur PostgreSQL création pool pipeline: {e}")
            _db_pool = None
        except Exception as e:
            logger.error(f"Impossible de créer pool DB pipeline: {e}")
            _db_pool = None
        finally:
            _pool_lock = False
    
    return _db_pool

@contextmanager
def get_db_connection():
    """Context manager pour connexions DB avec pool et gestion d'erreur robuste"""
    pool = get_db_pool()
    if not pool:
        raise Exception("Pool DB non disponible")
    
    conn = None
    try:
        # Timeout pour obtenir une connexion du pool
        conn = pool.getconn(key=None)  # Le pool gère lui-même les timeouts
        if conn:
            # Vérifier que la connexion est valide
            if conn.closed:
                logger.warning("Connexion fermée récupérée du pool, tentative de reconnexion")
                pool.putconn(conn, close=True)
                conn = pool.getconn(key=None)
                
            if conn and not conn.closed:
                yield conn
            else:
                raise Exception("Impossible d'obtenir connexion valide du pool")
        else:
            raise Exception("Impossible d'obtenir connexion du pool")
            
    except psycopg2.Error as e:
        logger.error(f"Erreur PostgreSQL dans pipeline: {e}")
        if conn and not conn.closed:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.warning(f"Erreur rollback pipeline: {rollback_error}")
        raise e
    except Exception as e:
        logger.error(f"Erreur pipeline: {e}")
        if conn and not conn.closed:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.warning(f"Erreur rollback pipeline: {rollback_error}")
        raise e
    finally:
        if conn and pool:
            try:
                # Vérifier l'état de la connexion avant de la remettre dans le pool
                if conn.closed:
                    pool.putconn(conn, close=True)  # Forcer la fermeture
                else:
                    pool.putconn(conn)
            except Exception as putconn_error:
                logger.warning(f"Erreur retour connexion au pool: {putconn_error}")

def derive_name_from_email(email: str) -> Optional[str]:
    """Dérive un nom à partir d'un email avec validation renforcée"""
    if not email or '@' not in email:
        return None
    
    try:
        local = email.split('@')[0]
        
        # Nettoyage et formatage amélioré
        # Remplacer les séparateurs communs par des espaces
        candidate = re.sub(r'[._+-]+', ' ', local)
        candidate = re.sub(r'[0-9]+', '', candidate)  # Supprimer les chiffres
        candidate = candidate.strip()
        
        # Validation plus stricte
        if len(candidate) >= 2 and candidate.replace(' ', '').isalpha():
            # Capitaliser chaque mot
            formatted_name = ' '.join(word.capitalize() for word in candidate.split() if len(word) > 1)
            
            # Validation finale
            if len(formatted_name) >= 3 and ' ' in formatted_name:
                logger.debug(f"Nom dérivé de {email}: {formatted_name}")
                return formatted_name
        
        logger.debug(f"Impossible de dériver nom valide depuis email {email}")
        return None
        
    except Exception as e:
        logger.warning(f"Erreur dérivation nom depuis email {email}: {e}")
        return None

def validate_email(email: str) -> bool:
    """Validation d'email robuste"""
    if not email or not isinstance(email, str):
        return False
    
    # Pattern regex plus strict pour emails
    email_pattern = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # Vérifications supplémentaires
    if not email_pattern.match(email.strip()):
        return False
    
    # Éviter les emails suspects
    suspicious_patterns = [
        r'noreply', r'no-reply', r'donotreply', r'test', r'example',
        r'admin@admin', r'user@user', r'contact@localhost'
    ]
    
    email_lower = email.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, email_lower):
            logger.debug(f"Email suspect filtré: {email}")
            return False
    
    return True

def clean_text_field(text: str, max_length: int = 255) -> Optional[str]:
    """Nettoie et valide un champ texte"""
    if not text or not isinstance(text, str):
        return None
    
    # Nettoyage
    cleaned = text.strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Normaliser les espaces
    cleaned = re.sub(r'[^\w\s@.-]', '', cleaned)  # Supprimer caractères spéciaux dangereux
    
    # Validation longueur
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip()
    
    return cleaned if len(cleaned) >= 2 else None

class PostgresPipeline:
    """Pipeline PostgreSQL avec gestion d'erreur robuste et métriques"""
    
    def __init__(self):
        self.spider_name = None
        self.items_processed = 0
        self.items_saved = 0
        self.items_duplicates = 0
        self.items_invalid = 0
        self.start_time = datetime.now()
        
    def open_spider(self, spider):
        """Initialisation du spider avec validation complète"""
        self.spider_name = spider.name
        logger.info(f"Pipeline PostgreSQL initialisé pour spider: {self.spider_name}")
        
        # Test de la connexion avec retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version()")
                        version = cur.fetchone()[0]
                        logger.info(f"Connexion DB pipeline validée - {version}")
                        break
            except Exception as e:
                logger.warning(f"Test connexion pipeline échoué (tentative {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error("Impossible de valider la connexion DB pipeline après plusieurs tentatives")
                    raise
                import time
                time.sleep(2)  # Attendre avant retry
        
        # Initialiser les statistiques
        self.start_time = datetime.now()
        self.items_processed = 0
        self.items_saved = 0
        self.items_duplicates = 0
        self.items_invalid = 0

    def close_spider(self, spider):
        """Finalisation du spider avec statistiques complètes"""
        duration = datetime.now() - self.start_time
        
        logger.info(f"Pipeline fermé pour spider: {self.spider_name}")
        logger.info(f"Statistiques pipeline:")
        logger.info(f"  - Durée d'exécution: {duration}")
        logger.info(f"  - Items traités: {self.items_processed}")
        logger.info(f"  - Items sauvegardés: {self.items_saved}")
        logger.info(f"  - Doublons ignorés: {self.items_duplicates}")
        logger.info(f"  - Items invalides: {self.items_invalid}")
        
        if self.items_processed > 0:
            success_rate = (self.items_saved / self.items_processed) * 100
            logger.info(f"  - Taux de succès: {success_rate:.1f}%")
        
        # Statistiques finales en base
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT COUNT(*) as total_contacts 
                        FROM contacts 
                        WHERE created_at >= %s
                          AND deleted_at IS NULL
                    """, (self.start_time,))
                    
                    result = cur.fetchone()
                    if result:
                        logger.info(f"  - Nouveaux contacts en base depuis le démarrage: {result['total_contacts']}")
                        
        except Exception as e:
            logger.warning(f"Impossible de récupérer stats finales: {e}")
        
        # Log des métriques pour monitoring externe
        logger.info(f"METRICS: spider={self.spider_name} processed={self.items_processed} "
                   f"saved={self.items_saved} duplicates={self.items_duplicates} "
                   f"invalid={self.items_invalid} duration_seconds={duration.total_seconds()}")

    def process_item(self, item, spider):
        """Traitement d'un item avec validation complète et gestion d'erreur robuste"""
        self.items_processed += 1
        
        try:
            # Validation de l'email (critique)
            email = item.get("email", "").strip()
            if not validate_email(email):
                self.items_invalid += 1
                logger.debug(f"Item ignoré: email invalide ou manquant ({email})")
                return item
            
            # Nettoyage et validation du nom
            name = clean_text_field(item.get("name", ""))
            if not name:
                # Tentative de dérivation depuis l'email
                name = derive_name_from_email(email)
                if name:
                    item["name"] = name
                    logger.debug(f"Nom dérivé pour {email}: {name}")
            
            # Si toujours pas de nom valide, ignorer
            if not name:
                self.items_invalid += 1
                logger.debug(f"Item ignoré: impossible de déterminer nom pour {email}")
                return item
            
            # Nettoyage des autres champs
            cleaned_item = {
                "name": name,
                "org": clean_text_field(item.get("org", ""), 200),
                "email": email.lower(),  # Normaliser en minuscules
                "languages": clean_text_field(item.get("languages", ""), 50),
                "phone": clean_text_field(item.get("phone", ""), 30),
                "country": clean_text_field(item.get("country", ""), 100),
                "url": item.get("url", "").strip()[:500] if item.get("url") else None,
                "theme": clean_text_field(item.get("theme", ""), 50),
                "source": clean_text_field(item.get("source", "Scraper"), 50),
                "page_lang": clean_text_field(item.get("page_lang", ""), 10),
                "raw_text": None,  # Pas de stockage du raw_text pour économiser l'espace
                "query_id": item.get("query_id"),
                "seed_url": item.get("seed_url", "").strip()[:500] if item.get("seed_url") else None
            }
            
            # Validation URL si présente
            if cleaned_item["url"]:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(cleaned_item["url"])
                    if not parsed.scheme or not parsed.netloc:
                        cleaned_item["url"] = None
                except Exception:
                    cleaned_item["url"] = None
            
            # Insertion en base avec gestion des doublons
            if self._insert_contact(cleaned_item):
                self.items_saved += 1
                logger.debug(f"Contact sauvegardé: {email}")
            else:
                self.items_duplicates += 1
                logger.debug(f"Doublon ignoré: {email}")
            
            return item
            
        except Exception as e:
            self.items_invalid += 1
            logger.error(f"Erreur traitement item {self.items_processed}: {e}", exc_info=True)
            # Ne pas bloquer le pipeline pour une erreur
            return item

    def _insert_contact(self, cleaned_item: Dict[str, Any]) -> bool:
        """
        Insertion d'un contact avec gestion d'erreur robuste et upsert intelligent
        
        Returns:
            True si nouveau contact inséré, False si doublon
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Requête d'upsert optimisée avec gestion intelligente des doublons
                    cur.execute("""
                        INSERT INTO contacts (
                            name, org, email, languages, phone, country, 
                            url, theme, source, page_lang, raw_text, 
                            query_id, seed_url, created_at, updated_at
                        ) VALUES (
                            %(name)s, %(org)s, %(email)s, %(languages)s, %(phone)s, %(country)s,
                            %(url)s, %(theme)s, %(source)s, %(page_lang)s, %(raw_text)s,
                            %(query_id)s, %(seed_url)s, NOW(), NOW()
                        )
                        ON CONFLICT (email) DO UPDATE SET
                            -- Mise à jour intelligente: garder la meilleure information
                            name = CASE 
                                WHEN LENGTH(COALESCE(EXCLUDED.name, '')) > LENGTH(COALESCE(contacts.name, ''))
                                THEN EXCLUDED.name 
                                ELSE contacts.name 
                            END,
                            org = CASE 
                                WHEN EXCLUDED.org IS NOT NULL AND LENGTH(EXCLUDED.org) > 0
                                THEN EXCLUDED.org 
                                ELSE COALESCE(contacts.org, EXCLUDED.org)
                            END,
                            phone = CASE 
                                WHEN EXCLUDED.phone IS NOT NULL AND LENGTH(EXCLUDED.phone) > 0
                                THEN EXCLUDED.phone 
                                ELSE COALESCE(contacts.phone, EXCLUDED.phone)
                            END,
                            country = COALESCE(EXCLUDED.country, contacts.country),
                            url = CASE 
                                WHEN EXCLUDED.url IS NOT NULL AND LENGTH(EXCLUDED.url) > 0
                                THEN EXCLUDED.url 
                                ELSE COALESCE(contacts.url, EXCLUDED.url)
                            END,
                            languages = COALESCE(EXCLUDED.languages, contacts.languages),
                            theme = COALESCE(EXCLUDED.theme, contacts.theme),
                            query_id = COALESCE(EXCLUDED.query_id, contacts.query_id),
                            seed_url = COALESCE(EXCLUDED.seed_url, contacts.seed_url),
                            updated_at = NOW()
                        RETURNING (xmax = 0) AS is_new_record
                    """, cleaned_item)
                    
                    result = cur.fetchone()
                    is_new_record = result[0] if result else False
                    
                    # Commit automatique via context manager
                conn.commit()
                
                return is_new_record
                
        except psycopg2.IntegrityError as e:
            # Gestion spécifique des violations de contraintes
            logger.debug(f"Violation contrainte lors insertion contact {cleaned_item.get('email')}: {e}")
            return False  # Considérer comme doublon
            
        except psycopg2.Error as e:
            logger.error(f"Erreur PostgreSQL lors insertion contact {cleaned_item.get('email')}: {e}")
            raise  # Re-raise pour gestion par le niveau supérieur
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors insertion contact {cleaned_item.get('email')}: {e}")
            raise
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques actuelles du pipeline"""
        duration = datetime.now() - self.start_time
        
        return {
            "spider_name": self.spider_name,
            "start_time": self.start_time.isoformat(),
            "duration_seconds": duration.total_seconds(),
            "items_processed": self.items_processed,
            "items_saved": self.items_saved,
            "items_duplicates": self.items_duplicates,
            "items_invalid": self.items_invalid,
            "success_rate": (self.items_saved / max(1, self.items_processed)) * 100,
            "processing_rate": self.items_processed / max(1, duration.total_seconds())
        }