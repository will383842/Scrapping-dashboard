import os
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
from pathlib import Path

# Configuration logging
logger = logging.getLogger(__name__)

# Configuration base de données
DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"), 
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper"), 
    user=os.getenv("POSTGRES_USER", "scraper"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper")
)

# Répertoire racine autorisé pour les sessions (sécurité)
ALLOWED_BASE = os.path.abspath("/app/sessions")
ALLOWED_EXTENSIONS = {'.json', '.txt', '.state'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max

def _validate_session_path(file_path: str) -> bool:
    """
    Validation complète d'un chemin de session
    Vérifications de sécurité multiples
    """
    if not file_path:
        return False
    
    try:
        # Conversion en objet Path pour manipulation sécurisée
        path_obj = Path(file_path).resolve()
        allowed_base_obj = Path(ALLOWED_BASE).resolve()
        
        # Vérification 1: Le chemin doit être dans le répertoire autorisé
        if not str(path_obj).startswith(str(allowed_base_obj) + os.sep):
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
            logger.warning(f"Extension non autorisée pour session: {file_path}")
            return False
        
        # Vérification 5: Taille de fichier raisonnable
        if path_obj.stat().st_size > MAX_FILE_SIZE:
            logger.warning(f"Fichier session trop volumineux: {file_path}")
            return False
        
        # Vérification 6: Permissions de lecture
        if not os.access(path_obj, os.R_OK):
            logger.warning(f"Fichier session non lisible: {file_path}")
            return False
        
        return True
        
    except (ValueError, OSError, PermissionError) as e:
        logger.error(f"Erreur validation chemin session {file_path}: {e}")
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
    Obtient une connexion à la base de données avec gestion d'erreur
    """
    try:
        conn = psycopg2.connect(**DB, connect_timeout=10)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erreur connexion base de données: {e}")
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
                    domain
                FROM sessions 
                WHERE id = %s 
                  AND deleted_at IS NULL
            """, (session_id,))
            
            row = cur.fetchone()
            
            if not row:
                logger.debug(f"Session {session_id} non trouvée")
                return None
            
            # Vérifications business logic
            if not row.get("active", False):
                logger.debug(f"Session {session_id} inactive")
                return None
            
            session_type = row.get("type", "storage_state")
            if session_type != "storage_state":
                logger.debug(f"Session {session_id} n'est pas de type storage_state: {session_type}")
                return None
            
            # Vérification expiration
            expires_at = row.get("expires_at")
            if expires_at and expires_at < datetime.now():
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
                
                # Mise à jour de la dernière utilisation
                try:
                    cur.execute("""
                        UPDATE sessions 
                        SET last_used_at = NOW(), 
                            usage_count = COALESCE(usage_count, 0) + 1
                        WHERE id = %s
                    """, (session_id,))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"Impossible de mettre à jour usage session {session_id}: {e}")
            
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
            except Exception:
                pass

def list_available_sessions() -> List[Dict[str, Any]]:
    """
    Liste toutes les sessions actives disponibles
    
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
                    created_at,
                    notes
                FROM sessions 
                WHERE active = true 
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY last_used_at DESC NULLS LAST, created_at DESC
            """)
            
            sessions = cur.fetchall()
            
            # Vérification que les fichiers existent réellement
            valid_sessions = []
            for session in sessions:
                session_dict = dict(session)
                
                # Vérifier que le fichier existe encore
                file_path = get_storage_state_path(session['id'])
                if file_path:
                    session_dict['file_exists'] = True
                    session_dict['file_size'] = Path(file_path).stat().st_size
                    valid_sessions.append(session_dict)
                else:
                    session_dict['file_exists'] = False
                    # On pourrait marquer la session comme inactive ici
            
            return valid_sessions
        
    except Exception as e:
        logger.error(f"Erreur lors de la liste des sessions: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

def validate_session_file(session_id: int) -> bool:
    """
    Valide qu'un fichier de session est bien formé
    
    Args:
        session_id: ID de la session à valider
    
    Returns:
        True si le fichier est valide
    """
    file_path = get_storage_state_path(session_id)
    if not file_path:
        return False
    
    try:
        # Pour storage_state, on s'attend à du JSON
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Vérifications basiques du contenu storage_state
        if not isinstance(data, dict):
            return False
        
        # Playwright storage state doit avoir certaines clés
        expected_keys = {'cookies', 'origins'}
        if not any(key in data for key in expected_keys):
            logger.warning(f"Session {session_id}: format storage_state invalide")
            return False
        
        return True
        
    except (json.JSONDecodeError, UnicodeDecodeError, IOError) as e:
        logger.error(f"Session {session_id}: fichier invalide - {e}")
        return False
    except Exception as e:
        logger.error(f"Erreur validation session {session_id}: {e}")
        return False

# Import datetime for expiration check
from datetime import datetime