#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utilitaires de filtrage pour le scraper
Version simplifiée - support des mots-clés personnalisés
"""

import json
import os
import logging
from typing import Optional, Dict, Any

# Configuration du logging
logger = logging.getLogger(__name__)

# Configuration des langues - chargement sécurisé
LANGCFG = {}

def load_language_config():
    """
    Charge la configuration des langues de manière sécurisée
    """
    global LANGCFG
    
    try:
        config_path = os.path.join(os.getcwd(), 'config', 'languages.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                LANGCFG = json.load(f)
            logger.info(f"Configuration des langues chargée depuis {config_path}")
        else:
            # Configuration par défaut si le fichier n'existe pas
            LANGCFG = {
                "language_markers": {
                    "fr": ["le ", "la ", "les ", "et ", "ou ", "avec ", "dans ", "pour ", "sur ", "par "],
                    "en": ["the ", "and ", "or ", "with ", "in ", "for ", "on ", "at ", "by ", "this "],
                    "es": ["el ", "la ", "los ", "las ", "y ", "o ", "con ", "en ", "para ", "por "],
                    "de": ["der ", "die ", "das ", "und ", "oder ", "mit ", "in ", "für ", "von ", "zu "],
                    "it": ["il ", "la ", "lo ", "gli ", "le ", "e ", "o ", "con ", "in ", "per "]
                }
            }
            logger.warning(f"Fichier de configuration non trouvé, utilisation de la configuration par défaut")
            
    except Exception as e:
        logger.error(f"Erreur lors du chargement de la configuration des langues: {e}")
        # Configuration minimale de secours
        LANGCFG = {
            "language_markers": {
                "fr": ["le ", "la ", "les ", "et "],
                "en": ["the ", "and ", "or ", "with "]
            }
        }

# Charger la configuration au démarrage du module
load_language_config()

def page_lang_from_text(text: str) -> Optional[str]:
    """
    Détecte la langue d'un texte basé sur des marqueurs linguistiques
    
    Args:
        text: Le texte à analyser
        
    Returns:
        Code de langue (ex: 'fr', 'en') ou None si indéterminé
    """
    if not text or not isinstance(text, str):
        return None
    
    # Normaliser le texte pour la recherche
    text_lower = text.lower()
    
    # Compter les occurrences de marqueurs par langue
    language_scores = {}
    
    try:
        language_markers = LANGCFG.get("language_markers", {})
        
        for lang_code, markers in language_markers.items():
            score = 0
            for marker in markers:
                if isinstance(marker, str):
                    # Compter les occurrences du marqueur
                    score += text_lower.count(marker.lower())
            
            if score > 0:
                language_scores[lang_code] = score
        
        # Retourner la langue avec le score le plus élevé
        if language_scores:
            detected_lang = max(language_scores, key=language_scores.get)
            logger.debug(f"Langue détectée: {detected_lang} (score: {language_scores[detected_lang]})")
            return detected_lang
        
    except Exception as e:
        logger.error(f"Erreur lors de la détection de langue: {e}")
    
    return None

def get_language_markers() -> Dict[str, Any]:
    """
    Retourne les marqueurs de langue configurés
    
    Returns:
        Dictionnaire des marqueurs par langue
    """
    return LANGCFG.get("language_markers", {})

def is_language_supported(lang_code: str) -> bool:
    """
    Vérifie si une langue est supportée
    
    Args:
        lang_code: Code de langue à vérifier
        
    Returns:
        True si la langue est supportée
    """
    return lang_code in LANGCFG.get("language_markers", {})

def reload_language_config():
    """
    Recharge la configuration des langues
    Utile pour les mises à jour à chaud
    """
    global LANGCFG
    LANGCFG = {}
    load_language_config()
    logger.info("Configuration des langues rechargée")

# FONCTION SUPPRIMÉE: matches_keywords()
# Cette fonction n'est plus nécessaire car maintenant on utilise
# des mots-clés personnalisés directement dans le spider via
# la fonction matches_custom_keywords() du spider single_url.py

# Fonctions utilitaires additionnelles pour la détection de contenu

def detect_contact_context(text: str) -> Dict[str, bool]:
    """
    Détecte des contextes favorables pour l'extraction de contacts
    
    Args:
        text: Texte à analyser
        
    Returns:
        Dict avec des indicateurs de contexte
    """
    if not text:
        return {"has_contact_context": False}
    
    text_lower = text.lower()
    
    # Indicateurs de contexte contact
    contact_indicators = {
        "contact_page": any(word in text_lower for word in [
            "contact", "nous contacter", "contact us", "get in touch", 
            "contactez-nous", "coordonnées"
        ]),
        "team_page": any(word in text_lower for word in [
            "équipe", "team", "staff", "notre équipe", "our team",
            "collaborateurs", "membres"
        ]),
        "about_page": any(word in text_lower for word in [
            "à propos", "about", "about us", "qui sommes nous",
            "présentation", "notre société"
        ]),
        "professional_context": any(word in text_lower for word in [
            "avocat", "lawyer", "médecin", "doctor", "consultant",
            "expert", "professionnel", "professional", "cabinet", "clinic"
        ])
    }
    
    # Score global de contexte
    context_score = sum(contact_indicators.values())
    contact_indicators["has_contact_context"] = context_score > 0
    contact_indicators["context_score"] = context_score
    
    return contact_indicators

def clean_extracted_text(text: str) -> str:
    """
    Nettoie le texte extrait pour l'analyse
    
    Args:
        text: Texte brut à nettoyer
        
    Returns:
        Texte nettoyé
    """
    if not text:
        return ""
    
    import re
    
    # Supprimer les balises HTML résiduelles
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Supprimer les caractères de contrôle et espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # Supprimer les caractères non imprimables
    text = re.sub(r'[^\x20-\x7E\u00A0-\uFFFF]', '', text)
    
    return text.strip()

# Export des fonctions principales
__all__ = [
    'page_lang_from_text',
    'get_language_markers', 
    'is_language_supported',
    'reload_language_config',
    'detect_contact_context',
    'clean_extracted_text'
]