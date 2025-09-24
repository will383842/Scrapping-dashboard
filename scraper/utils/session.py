#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SESSION.PY - VERSION CORRIGÉE v2.1
Version: 2.1 Production-Ready Fixed
Description: Gestion sécurisée des sessions avec validation complète et imports corrigés
"""

import os
import json
import psycopg2
import logging
from datetime import datetime  # CORRIGÉ: Import ajouté
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List
from pathlib import Path

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
    'application_name': 'session_manager'  # CORRIGÉ: nom plus descriptif
}

# Répertoire racine autorisé pour les sessions (sécurité renforcée)
ALLOWED_BASE = os.path.abspath(os.getenv("SESSIONS_PATH", "/app/sessions"))
ALLOWED_EXTENSIONS = {'.json', '.txt', '.state'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # CORRIGÉ: 50MB max (augmenté pour Playwright)

def _validate_session_path(file_path: str) -> bool:
    """
    Validation complète d'un chemin de session avec sécurité renforcée
    Vérifications de sécurité multiples et robustes
    """
    if not file_path:
        logger.debug("Chemin de session vide")
        return False
    
    try:
        # Conversion en objet Path pour manipulation sécurisée
        path_obj = Path(file_path).resolve()
        allowed_base_obj = Path(ALLOWED_BASE).resolve()
        
        # Vérification 1: Le chemin doit être dans le répertoire autorisé
        try:
            path_obj.relative_to(allowed_base_obj)
        except ValueError:
            logger.warning(f"Tentative d'accès hors répertoire autorisé: {file_path}")
            return False
        
        # Vérification 2: Le fichier doit exister
        if not path_obj.exists():
            logger.debug(f"Fichier session inexistant: {file_path}")
            return False
        
        # Vérification 3: Doit être un fichier (pas un répertoire)
        if not path_obj.is_file():
            logger.warning(f"Chemin session n'est pas un fichier: {file_path}")
            return False
        
        # Vérification 4: Extension autorisée
        if path_obj.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.warning(f"Extension non autorisée pour session: {file_path} (extension: {path_obj.suffix})")
            return False
        
        # Vérification 5: Taille de fichier raisonnable
        file_size = path_obj.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"Fichier session trop volumineux: {file_path} ({file_size} bytes > {MAX_FILE_SIZE})")
            return False
        
        # Vérification 6: Permissions de lecture
        if not os.access(path_obj, os.R_OK):
            logger.warning(f"Fichier session non lisible: {file_path}")
            return False
        
        # NOUVEAU: Vérification 7: Pas de liens symboliques pour sécurité
        if path_obj.is_symlink():
            logger.warning(f"Liens symboliques non autorisés pour sessions: {file_path}")
            return False
        
        # NOUVEAU: Vérification 8: Nom de fichier sécurisé (pas de caractères dangereux)
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
        if any(char in str(path_obj.name) for char in dangerous_chars):
            logger.warning(f"Nom de fichier contient des caractères dangereux: {file_path}")
            return False
        
        return True
        
    except (ValueError, OSError, PermissionError) as e:
        logger.error(f"Erreur validation chemin session {file_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Erreur inattendue validation chemin session {file_path}: {e}")
        return False

def _safe_path(file_path: str) -> Optional[str]:
    """
    Confinement sécurisé du chemin avec validation complète
    Retourne le chemin absolu seulement s'il passe toutes les validations
    """
    if not _validate_session_path(file_path):
        return None
    
    try:
        return str(Path(file_path).resolve())
    except Exception as e:
        logger.error(f"Erreur résolution chemin session: {e}")
        return None

def get_db_connection() -> Optional[psycopg2.connection]:
    """
    Obtient une connexion à la base de données avec gestion d'erreur robuste
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.debug("Connexion DB session manager établie")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erreur connexion base de données session manager: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue connexion DB: {e}")
        return None

def get_storage_state_path(session_id: int) -> Optional[str]:
    """
    Récupère le chemin du fichier storage state de manière sécurisée
    
    Args:
        session_id: ID de la session en base de données
    
    Returns:
        Chemin sécurisé vers le fichier storage state ou None
    """
    if not session_id or not isinstance(session_id, int) or session_id <= 0:
        logger.debug(f"ID session invalide: {session_id}")
        return None
    
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return None
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Requête sécurisée avec paramètres
            cur.execute("""
                SELECT 
                    file_path, 
                    active, 
                    type, 
                    validation_status,
                    expires_at,
                    domain,
                    last_used_at,
                    usage_count
                FROM sessions 
                WHERE id = %s 
                  AND deleted_at IS NULL
            """, (session_id,))
            
            row = cur.fetchone()
            
            if not row:
                logger.debug(f"Session {session_id} non trouvée")
                return None
            
            # Vérifications business logic renforcées
            if not row.get("active", False):
                logger.debug(f"Session {session_id} inactive")
                return None
            
            session_type = row.get("type", "storage_state")
            if session_type != "storage_state":
                logger.debug(f"Session {session_id} n'est pas de type storage_state: {session_type}")
                return None
            
            # Vérification expiration avec gestion timezone
            expires_at = row.get("expires_at")
            if expires_at:
                # S'assurer que expires_at est timezone-aware
                if expires_at.tzinfo is None:
                    # Assumer UTC si pas de timezone
                    import pytz
                    expires_at = pytz.UTC.localize(expires_at)
                    
                current_time = datetime.now(pytz.UTC)
                if expires_at < current_time:
                    logger.warning(f"Session {session_id} expirée: {expires_at}")
                    return None
            
            # Vérification status validation
            validation_status = row.get("validation_status")
            if validation_status == "invalid":
                logger.warning(f"Session {session_id} marquée comme invalide")
                return None
            
            file_path = row.get("file_path")
            if not file_path:
                logger.warning(f"Session {session_id} sans chemin de fichier")
                return None
            
            # Application du confinement sécurisé
            safe_path_result = _safe_path(file_path)
            
            if safe_path_result:
                logger.info(f"Session {session_id} récupérée avec succès: domaine={row.get('domain')}")
                
                # Mise à jour de la dernière utilisation (meilleure gestion d'erreurs)
                try:
                    cur.execute("""
                        UPDATE sessions 
                        SET last_used_at = NOW(), 
                            usage_count = COALESCE(usage_count, 0) + 1,
                            updated_at = NOW()
                        WHERE id = %s
                    """, (session_id,))
                    conn.commit()
                    logger.debug(f"Usage session {session_id} mis à jour")
                except psycopg2.Error as e:
                    logger.warning(f"Impossible de mettre à jour usage session {session_id}: {e}")
                    # Continue même si la mise à jour échoue
                except Exception as e:
                    logger.warning(f"Erreur inattendue mise à jour session {session_id}: {e}")
            else:
                logger.warning(f"Session {session_id} a échoué la validation de sécurité")
            
            return safe_path_result
        
    except psycopg2.Error as e:
        logger.error(f"Erreur base de données lors récupération session {session_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue récupération session {session_id}: {type(e).__name__}: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Connexion DB session fermée")
            except Exception as e:
                logger.debug(f"Erreur fermeture connexion session: {e}")

def list_available_sessions() -> List[Dict[str, Any]]:
    """
    Liste toutes les sessions actives disponibles avec informations enrichies
    
    Returns:
        Liste des sessions avec leurs métadonnées
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return []
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id,
                    domain,
                    type,
                    validation_status,
                    expires_at,
                    usage_count,
                    last_used_at,
                    last_validated_at,
                    created_at,
                    notes,
                    file_path,
                    browser_type,
                    user_agent
                FROM sessions 
                WHERE active = true 
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY 
                    CASE validation_status 
                        WHEN 'valid' THEN 1 
                        WHEN NULL THEN 2 
                        ELSE 3 
                    END,
                    last_used_at DESC NULLS LAST, 
                    created_at DESC
            """)
            
            sessions = cur.fetchall()
            
            # Vérification que les fichiers existent réellement et enrichissement
            valid_sessions = []
            for session in sessions:
                session_dict = dict(session)
                
                # Vérifier que le fichier existe encore
                if session['file_path']:
                    file_path = _safe_path(session['file_path'])
                    if file_path:
                        session_dict['file_exists'] = True
                        session_dict['file_size'] = Path(file_path).stat().st_size
                        session_dict['file_modified'] = datetime.fromtimestamp(Path(file_path).stat().st_mtime)
                        
                        # NOUVEAU: Validation du contenu du fichier si c'est du JSON
                        if file_path.endswith('.json'):
                            session_dict['content_valid'] = validate_session_file_content(file_path)
                        else:
                            session_dict['content_valid'] = True
                            
                        valid_sessions.append(session_dict)
                    else:
                        session_dict['file_exists'] = False
                        session_dict['file_size'] = None
                        # Optionnel: marquer la session comme inactive si le fichier n'existe pas
                        logger.warning(f"Session {session['id']} référence un fichier inexistant: {session['file_path']}")
                else:
                    session_dict['file_exists'] = False
                    session_dict['file_size'] = None
            
            logger.info(f"Sessions disponibles: {len(valid_sessions)}/{len(sessions)} valides")
            return valid_sessions
        
    except Exception as e:
        logger.error(f"Erreur lors de la liste des sessions: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Erreur fermeture connexion: {e}")

def validate_session_file_content(file_path: str) -> bool:
    """
    Valide le contenu d'un fichier de session
    
    Args:
        file_path: Chemin vers le fichier à valider
    
    Returns:
        True si le contenu est valide
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Vérifications basiques du contenu
        if not isinstance(data, dict):
            logger.warning(f"Session file {file_path}: contenu n'est pas un objet JSON")
            return False
        
        # Pour Playwright storage state, vérifier les clés essentielles
        if file_path.endswith('.json'):
            # Playwright storage state doit avoir certaines clés
            expected_keys = {'cookies', 'origins'}
            if not any(key in data for key in expected_keys):
                logger.warning(f"Session {file_path}: format storage_state Playwright invalide")
                return False
            
            # Vérification structure cookies
            if 'cookies' in data:
                if not isinstance(data['cookies'], list):
                    logger.warning(f"Session {file_path}: format cookies invalide")
                    return False
        
        return True
        
    except json.JSONDecodeError as e:
        logger.error(f"Session {file_path}: JSON invalide - {e}")
        return False
    except UnicodeDecodeError as e:
        logger.error(f"Session {file_path}: encodage invalide - {e}")
        return False
    except IOError as e:
        logger.error(f"Session {file_path}: erreur lecture fichier - {e}")
        return False
    except Exception as e:
        logger.error(f"Erreur validation session {file_path}: {e}")
        return False

def validate_session_file(session_id: int) -> bool:
    """
    Valide qu'un fichier de session est bien formé (fonction publique)
    
    Args:
        session_id: ID de la session à valider
    
    Returns:
        True si le fichier est valide
    """
    file_path = get_storage_state_path(session_id)
    if not file_path:
        return False
    
    return validate_session_file_content(file_path)

def create_session_backup(session_id: int) -> Optional[str]:
    """
    NOUVEAU: Crée une sauvegarde d'une session
    
    Args:
        session_id: ID de la session à sauvegarder
    
    Returns:
        Chemin vers la sauvegarde ou None
    """
    try:
        file_path = get_storage_state_path(session_id)
        if not file_path:
            return None
        
        # Créer le dossier de backup s'il n'existe pas
        backup_dir = Path(ALLOWED_BASE) / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        # Nom du fichier de backup avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"session_{session_id}_backup_{timestamp}.json"
        backup_path = backup_dir / backup_filename
        
        # Copier le fichier
        import shutil
        shutil.copy2(file_path, backup_path)
        
        logger.info(f"Backup session {session_id} créé: {backup_path}")
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"Erreur création backup session {session_id}: {e}")
        return None

def cleanup_expired_sessions() -> int:
    """
    NOUVEAU: Nettoie les sessions expirées
    
    Returns:
        Nombre de sessions nettoyées
    """
    conn = None
    cleaned_count = 0
    
    try:
        conn = get_db_connection()
        if not conn:
            return 0
        
        with conn.cursor() as cur:
            # Marquer les sessions expirées comme inactives
            cur.execute("""
                UPDATE sessions 
                SET active = false, 
                    updated_at = NOW(),
                    notes = COALESCE(notes, '') || ' [Auto-désactivée: expirée]'
                WHERE expires_at IS NOT NULL 
                  AND expires_at < NOW() 
                  AND active = true
                  AND deleted_at IS NULL
            """)
            
            cleaned_count = cur.rowcount
            conn.commit()
            
            logger.info(f"Sessions expirées nettoyées: {cleaned_count}")
            
    except Exception as e:
        logger.error(f"Erreur nettoyage sessions expirées: {e}")
        
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.debug(f"Erreur fermeture connexion cleanup: {e}")
    
    return cleaned_count

# NOUVEAU: Fonctions d'administration
def get_session_statistics() -> Dict[str, Any]:
    """
    NOUVEAU: Récupère des statistiques sur les sessions
    
    Returns:
        Dictionnaire avec les statistiques
    """
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            return {}
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_sessions,
                    COUNT(*) FILTER (WHERE active = true) as active_sessions,
                    COUNT(*) FILTER (WHERE validation_status = 'valid') as valid_sessions,
                    COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at < NOW()) as expired_sessions,
                    COUNT(DISTINCT domain) as unique_domains,
                    AVG(usage_count) as avg_usage_count,
                    MAX(last_used_at) as last_session_used,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as created_today
                FROM sessions 
                WHERE deleted_at IS NULL
            """)
            
            result = cur.fetchone()
            return dict(result) if result else {}
            
    except Exception as e:
        logger.error(f"Erreur récupération statistiques sessions: {e}")
        return {}
        
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass