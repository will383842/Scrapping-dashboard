#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIPELINES.PY - CORRECTED VERSION
Version: 2.1 Production-Ready Fixed
Description: Pipeline PostgreSQL avec pool de connexions et gestion d'erreur robuste
"""

import os
import re
import logging
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional

# Configuration logging
logger = logging.getLogger(__name__)

# Configuration base de données CORRIGÉE
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),  # CORRIGÉ: cohérent avec .env
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),  # CORRIGÉ: cohérent
    'password': os.getenv("POSTGRES_PASSWORD", "scraper_admin"),
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "30")),
    'application_name': 'scraper_pipeline'
}

# Pool de connexions global
_db_pool = None

def get_db_pool():
    """Obtient le pool de connexions global"""
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=int(os.getenv("CONNECTION_POOL_SIZE", "10")),
                **DB_CONFIG
            )
            logger.info("Pool de connexions DB pipeline initialisé")
        except Exception as e:
            logger.error(f"Impossible de créer pool DB pipeline: {e}")
            return None
    return _db_pool

@contextmanager
def get_db_connection():
    """Context manager pour connexions DB avec pool"""
    pool = get_db_pool()
    if not pool:
        raise Exception("Pool DB non disponible")
    
    conn = None
    try:
        conn = pool.getconn()
        if conn:
            yield conn
        else:
            raise Exception("Impossible d'obtenir connexion du pool")
    except psycopg2.Error as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if conn and pool:
            try:
                pool.putconn(conn)
            except:
                pass

def derive_name_from_email(email: str) -> Optional[str]:
    """Dérive un nom à partir d'un email"""
    if not email:
        return None
    
    try:
        local = email.split('@')[0]
        # Nettoyage et formatage
        candidate = re.sub(r'[._+-]+', ' ', local).strip()
        
        # Validation basique
        if len(candidate) >= 2 and candidate.replace(' ', '').isalpha():
            return candidate.title()
        
    except Exception as e:
        logger.debug(f"Erreur dérivation nom depuis email {email}: {e}")
    
    return None

class PostgresPipeline:
    """Pipeline PostgreSQL avec gestion d'erreur robuste"""
    
    def open_spider(self, spider):
        """Initialisation du spider"""
        self.spider_name = spider.name
        logger.info(f"Pipeline PostgreSQL initialisé pour spider: {self.spider_name}")
        
        # Test de la connexion
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    logger.info("Connexion DB pipeline validée")
        except Exception as e:
            logger.error(f"Erreur test connexion pipeline: {e}")
            raise

    def close_spider(self, spider):
        """Finalisation du spider"""
        logger.info(f"Pipeline fermé pour spider: {self.spider_name}")
        
        # Statistiques finales
        try:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT COUNT(*) as total_contacts 
                        FROM contacts 
                        WHERE created_at >= NOW() - INTERVAL '1 hour'
                    """)
                    result = cur.fetchone()
                    if result:
                        logger.info(f"Contacts ajoutés dernière heure: {result['total_contacts']}")
        except Exception as e:
            logger.warning(f"Impossible de récupérer stats finales: {e}")

    def process_item(self, item, spider):
        """Traitement d'un item avec gestion d'erreur robuste"""
        try:
            # Validation de l'email
            email = (item.get("email") or "").strip()
            if not email or '@' not in email:
                logger.debug("Item ignoré: email manquant ou invalide")
                return item
            
            # Validation/dérivation du nom
            name = (item.get("name") or "").strip()
            if not name:
                name = derive_name_from_email(email)
                if name:
                    item["name"] = name
            
            # Si toujours pas de nom, ignorer
            if not name:
                logger.debug(f"Item ignoré: impossible de dériver nom pour {email}")
                return item
            
            # Préparation des données
            fields = [
                "name", "org", "email", "languages", "phone", "country", 
                "url", "theme", "source", "page_lang", "raw_text", 
                "query_id", "seed_url"
            ]
            
            values = []
            for field in fields:
                value = item.get(field)
                # Nettoyage des chaînes
                if isinstance(value, str):
                    value = value.strip() or None
                values.append(value)
            
            # Insertion en base avec upsert
            self._insert_contact(values)
            
            logger.debug(f"Contact traité: {email}")
            return item
            
        except Exception as e:
            logger.error(f"Erreur traitement item: {e}")
            # Ne pas bloquer le pipeline pour une erreur
            return item

    def _insert_contact(self, values):
        """Insertion d'un contact avec gestion d'erreur et upsert"""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Requête d'upsert optimisée
                    cur.execute("""
                        INSERT INTO contacts (
                            name, org, email, languages, phone, country, 
                            url, theme, source, page_lang, raw_text, 
                            query_id, seed_url, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                            NOW(), NOW()
                        )
                        ON CONFLICT (email) DO UPDATE SET
                            name = COALESCE(EXCLUDED.name, contacts.name),
                            org = COALESCE(EXCLUDED.org, contacts.org),
                            languages = COALESCE(EXCLUDED.languages, contacts.languages),
                            phone = COALESCE(EXCLUDED.phone, contacts.phone),
                            country = COALESCE(EXCLUDED.country, contacts.country),
                            url = COALESCE(EXCLUDED.url, contacts.url),
                            theme = COALESCE(EXCLUDED.theme, contacts.theme),
                            source = COALESCE(EXCLUDED.source, contacts.source),
                            page_lang = COALESCE(EXCLUDED.page_lang, contacts.page_lang),
                            raw_text = COALESCE(EXCLUDED.raw_text, contacts.raw_text),
                            query_id = COALESCE(EXCLUDED.query_id, contacts.query_id),
                            seed_url = COALESCE(EXCLUDED.seed_url, contacts.seed_url),
                            updated_at = NOW()
                    """, values)
                    
                    # Commit automatique via context manager
                conn.commit()
                
        except psycopg2.IntegrityError as e:
            logger.warning(f"Violation contrainte lors insertion contact: {e}")
            # Les doublons sont normaux, ne pas lever d'exception
            
        except psycopg2.Error as e:
            logger.error(f"Erreur PostgreSQL lors insertion: {e}")
            raise
            
        except Exception as e:
            logger.error(f"Erreur inattendue lors insertion: {e}")
            raise