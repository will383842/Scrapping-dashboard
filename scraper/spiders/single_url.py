#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
import logging
from typing import List, Dict, Optional, Set, Any
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime

import scrapy
from scrapy import Request
from scrapy.http import Response
from scrapy.utils.project import get_project_settings
from scrapy.exceptions import CloseSpider

# Configuration du logging
logger = logging.getLogger(__name__)

class SingleUrlSpider(scrapy.Spider):
    """
    Spider pour extraire les contacts depuis une URL unique avec mots-clés personnalisés
    Version mise à jour avec support des custom_keywords et match_mode
    """
    
    name = 'single_url'
    allowed_domains = []
    start_urls = []
    
    # Patterns de détection d'emails et téléphones
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'(?:\+?[\d\s\-\(\)\.]{8,20})')
    
    # Mots de liaison à ignorer dans la recherche de noms
    STOP_WORDS = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
        'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 
        'after', 'above', 'below', 'between', 'among', 'le', 'la', 'les', 'et', 
        'ou', 'mais', 'dans', 'sur', 'avec', 'par', 'pour', 'de', 'du', 'des'
    }

    def __init__(self, url=None, query_id=None, custom_keywords=None, 
                 match_mode='any', min_matches=1, country_filter=None, 
                 lang_filter=None, use_js=False, max_pages_per_domain=25, 
                 *args, **kwargs):
        """
        Constructeur modifié pour accepter custom_keywords et match_mode
        
        Args:
            url: URL à scraper
            query_id: ID de la requête dans la base
            custom_keywords: Liste des mots-clés personnalisés ou string JSON
            match_mode: Mode de correspondance ('any', 'multiple', 'all')
            min_matches: Nombre minimum de correspondances requis
            country_filter: Filtre par pays
            lang_filter: Filtre par langue
            use_js: Utiliser JavaScript pour le rendu
            max_pages_per_domain: Nombre max de pages par domaine
        """
        super().__init__(*args, **kwargs)
        
        # Validation et configuration de base
        if not url:
            raise CloseSpider("URL requise")
            
        self.start_urls = [url]
        self.allowed_domains = [urlparse(url).netloc]
        
        # Configuration des paramètres de scraping
        self.query_id = int(query_id) if query_id else None
        self.country_filter = country_filter
        self.lang_filter = lang_filter
        self.use_js = use_js == 'True' or use_js is True
        self.max_pages_per_domain = int(max_pages_per_domain)
        
        # MODIFIÉ: Configuration des mots-clés personnalisés
        self.custom_keywords = self._parse_custom_keywords(custom_keywords)
        self.match_mode = match_mode or 'any'
        self.min_matches = int(min_matches) if min_matches else 1
        
        # Validation du mode de correspondance
        if self.match_mode not in ['any', 'multiple', 'all']:
            logger.warning(f"Mode de correspondance invalide: {self.match_mode}, utilisation de 'any'")
            self.match_mode = 'any'
        
        # Statistiques et état
        self.pages_crawled = 0
        self.contacts_found = 0
        self.visited_urls = set()
        
        logger.info(f"Spider initialisé:")
        logger.info(f"  - URL: {url}")
        logger.info(f"  - Mots-clés: {len(self.custom_keywords)} keywords")
        logger.info(f"  - Mode correspondance: {self.match_mode}")
        logger.info(f"  - Min correspondances: {self.min_matches}")
        logger.info(f"  - Max pages: {self.max_pages_per_domain}")

    def _parse_custom_keywords(self, custom_keywords) -> List[str]:
        """
        Parse les mots-clés depuis différents formats d'entrée
        
        Args:
            custom_keywords: String JSON, liste, ou string séparé par virgules
            
        Returns:
            Liste des mots-clés normalisés
        """
        if not custom_keywords:
            return []
        
        keywords = []
        
        try:
            # Si c'est déjà une liste
            if isinstance(custom_keywords, list):
                keywords = custom_keywords
            # Si c'est du JSON
            elif isinstance(custom_keywords, str) and custom_keywords.startswith('['):
                keywords = json.loads(custom_keywords)
            # Si c'est une string séparée par virgules/retours à la ligne
            elif isinstance(custom_keywords, str):
                keywords = re.split(r'[,;\n]+', custom_keywords.strip())
            else:
                logger.warning(f"Format de mots-clés non reconnu: {type(custom_keywords)}")
                return []
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Erreur parsing mots-clés: {e}")
            return []
        
        # Nettoyer et normaliser les mots-clés
        cleaned_keywords = []
        for kw in keywords:
            if isinstance(kw, str):
                kw = kw.strip().lower()
                if kw and len(kw) > 1:  # Ignorer les mots trop courts
                    cleaned_keywords.append(kw)
        
        logger.info(f"Mots-clés parsés: {cleaned_keywords}")
        return cleaned_keywords

    def matches_custom_keywords(self, text: str) -> Dict[str, Any]:
        """
        NOUVELLE FONCTION: Vérifie si le texte correspond aux mots-clés personnalisés
        
        Args:
            text: Texte à analyser
            
        Returns:
            Dict avec 'matches' (bool), 'found_keywords' (list), 'match_count' (int)
        """
        if not self.custom_keywords or not text:
            return {'matches': False, 'found_keywords': [], 'match_count': 0}
        
        # Normaliser le texte pour la recherche
        text_lower = text.lower()
        found_keywords = []
        
        # Chercher chaque mot-clé dans le texte
        for keyword in self.custom_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        match_count = len(found_keywords)
        
        # Déterminer si ça correspond selon le mode
        matches = False
        
        if self.match_mode == 'any':
            # Au moins un mot-clé trouvé
            matches = match_count >= 1
            
        elif self.match_mode == 'multiple':
            # Au moins min_matches mots-clés trouvés
            matches = match_count >= self.min_matches
            
        elif self.match_mode == 'all':
            # Tous les mots-clés doivent être trouvés
            matches = match_count == len(self.custom_keywords)
        
        logger.debug(f"Analyse mots-clés - Mode: {self.match_mode}, "
                    f"Trouvés: {match_count}/{len(self.custom_keywords)}, "
                    f"Correspond: {matches}")
        
        return {
            'matches': matches,
            'found_keywords': found_keywords,
            'match_count': match_count
        }

    def start_requests(self):
        """Génère les requêtes initiales"""
        for url in self.start_urls:
            yield Request(
                url=url,
                callback=self.parse,
                errback=self.handle_error,
                meta={
                    'dont_cache': True,
                    'download_timeout': 30,
                    'is_start_url': True
                }
            )

    def parse(self, response: Response):
        """
        Parse principal - extrait contacts et suit les liens
        """
        if response.status != 200:
            logger.warning(f"Status {response.status} pour {response.url}")
            return
        
        self.pages_crawled += 1
        current_url = response.url
        
        logger.info(f"Parsing page {self.pages_crawled}/{self.max_pages_per_domain}: {current_url}")
        
        # Extraire le contenu textuel de la page
        page_text = self._extract_page_text(response)
        
        # MODIFIÉ: Utiliser la nouvelle fonction de correspondance
        keyword_analysis = self.matches_custom_keywords(page_text)
        
        if keyword_analysis['matches']:
            logger.info(f"Page correspond aux critères: {keyword_analysis['found_keywords']}")
            
            # Extraire les contacts de cette page
            contacts = self._extract_contacts_from_page(response, page_text, keyword_analysis)
            for contact in contacts:
                yield contact
        else:
            logger.debug(f"Page ne correspond pas aux critères - "
                        f"Mots-clés trouvés: {keyword_analysis['found_keywords']}")
        
        # Continuer l'exploration si sous la limite
        if self.pages_crawled < self.max_pages_per_domain:
            yield from self._follow_links(response)
        else:
            logger.info(f"Limite de pages atteinte: {self.max_pages_per_domain}")

    def _extract_page_text(self, response: Response) -> str:
        """
        Extrait le texte principal de la page pour l'analyse
        """
        try:
            # Extraire le texte des éléments principaux
            selectors = [
                '//text()[not(ancestor::script or ancestor::style or ancestor::noscript)]',
                '//title/text()',
                '//meta[@name="description"]/@content',
                '//meta[@name="keywords"]/@content'
            ]
            
            texts = []
            for selector in selectors:
                extracted = response.xpath(selector).getall()
                texts.extend(extracted)
            
            # Nettoyer et joindre le texte
            clean_text = ' '.join([
                text.strip() 
                for text in texts 
                if text and text.strip()
            ])
            
            return clean_text[:10000]  # Limiter la taille pour l'analyse
            
        except Exception as e:
            logger.error(f"Erreur extraction texte: {e}")
            return ""

    def _extract_contacts_from_page(self, response: Response, page_text: str, 
                                  keyword_analysis: Dict) -> List[Dict]:
        """
        Extrait les contacts d'une page qui correspond aux critères
        """
        contacts = []
        
        try:
            # Extraire emails
            emails = set(self.EMAIL_PATTERN.findall(page_text))
            
            # Extraire téléphones (simple)
            phones = set(self._clean_phone_numbers(
                self.PHONE_PATTERN.findall(page_text)
            ))
            
            # Chercher des noms/organisations près des emails
            for email in emails:
                contact_data = {
                    'email': email,
                    'url': response.url,
                    'query_id': self.query_id,
                    'seed_url': self.start_urls[0],
                    'page_lang': self._detect_language(page_text),
                    'raw_text': page_text[:1000],  # Échantillon du texte
                    'extraction_method': 'scrapy',
                    'confidence_score': self._calculate_confidence_score(
                        email, page_text, keyword_analysis
                    ),
                    'source': 'scraper',
                    'created_at': datetime.now().isoformat(),
                }
                
                # Chercher nom et organisation près de l'email
                name, org = self._extract_name_and_org_near_email(email, page_text)
                if name:
                    contact_data['name'] = name
                if org:
                    contact_data['org'] = org
                
                # Ajouter téléphone si trouvé dans la proximité
                nearby_phone = self._find_phone_near_email(email, page_text, phones)
                if nearby_phone:
                    contact_data['phone'] = nearby_phone
                
                # Filtres additionnels
                if self.country_filter:
                    contact_data['country'] = self.country_filter
                
                contacts.append(contact_data)
                self.contacts_found += 1
                
                logger.info(f"Contact extrait: {email} - {name or 'Sans nom'}")
        
        except Exception as e:
            logger.error(f"Erreur extraction contacts: {e}")
        
        return contacts

    def _calculate_confidence_score(self, email: str, page_text: str, 
                                  keyword_analysis: Dict) -> float:
        """
        Calcule un score de confiance pour le contact extrait
        """
        score = 0.5  # Score de base
        
        # Bonus pour correspondance mots-clés
        keyword_ratio = keyword_analysis['match_count'] / max(len(self.custom_keywords), 1)
        score += keyword_ratio * 0.3
        
        # Bonus pour domaine email cohérent avec URL
        if email:
            email_domain = email.split('@')[-1].lower()
            page_domain = urlparse(self.start_urls[0]).netloc.lower()
            if email_domain in page_domain or page_domain in email_domain:
                score += 0.2
        
        # Limiter entre 0 et 1
        return min(1.0, max(0.0, score))

    def _extract_name_and_org_near_email(self, email: str, text: str) -> tuple:
        """
        Cherche nom et organisation près d'un email dans le texte
        """
        # Chercher dans un rayon de 200 caractères autour de l'email
        email_pos = text.lower().find(email.lower())
        if email_pos == -1:
            return None, None
        
        start = max(0, email_pos - 200)
        end = min(len(text), email_pos + 200)
        context = text[start:end]
        
        # Patterns pour détecter noms et organisations
        name_patterns = [
            r'(?:M\.|Mme|Mr\.|Mrs\.|Dr\.|Prof\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s*[-,]\s*(?:avocat|lawyer|doctor|consultant))',
            r'Contact:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        ]
        
        org_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z&][a-z]*)*\s+(?:Cabinet|Law Firm|Clinic|Consulting))',
            r'((?:[A-Z][a-z]+\s*){1,3}(?:SARL|SAS|SA|LLC|Inc\.|Ltd\.))',
        ]
        
        name = None
        org = None
        
        # Chercher nom
        for pattern in name_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if self._is_valid_name(candidate):
                    name = candidate
                    break
        
        # Chercher organisation
        for pattern in org_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                if len(candidate) > 3:
                    org = candidate
                    break
        
        return name, org

    def _is_valid_name(self, candidate: str) -> bool:
        """
        Valide qu'une chaîne ressemble à un nom de personne
        """
        if not candidate or len(candidate) < 3:
            return False
        
        words = candidate.lower().split()
        
        # Rejeter si contient des mots de liaison
        if any(word in self.STOP_WORDS for word in words):
            return False
        
        # Rejeter si contient des chiffres
        if any(char.isdigit() for char in candidate):
            return False
        
        return True

    def _clean_phone_numbers(self, raw_phones: List[str]) -> List[str]:
        """
        Nettoie et valide les numéros de téléphone
        """
        cleaned = []
        for phone in raw_phones:
            # Garder seulement les chiffres et quelques caractères
            clean = re.sub(r'[^\d\+\-\(\)\s\.]', '', phone)
            # Compter les chiffres
            digit_count = len(re.findall(r'\d', clean))
            # Valider longueur raisonnable
            if 8 <= digit_count <= 15:
                cleaned.append(clean.strip())
        return cleaned

    def _find_phone_near_email(self, email: str, text: str, phones: Set[str]) -> Optional[str]:
        """
        Cherche un téléphone proche d'un email
        """
        email_pos = text.lower().find(email.lower())
        if email_pos == -1 or not phones:
            return None
        
        # Chercher dans un rayon de 300 caractères
        start = max(0, email_pos - 300)
        end = min(len(text), email_pos + 300)
        context = text[start:end]
        
        for phone in phones:
            if phone in context:
                return phone
        
        return None

    def _detect_language(self, text: str) -> Optional[str]:
        """
        Détection simple de langue basée sur des mots communs
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Mots indicateurs par langue
        lang_indicators = {
            'fr': ['le', 'la', 'les', 'et', 'ou', 'avec', 'dans', 'pour'],
            'en': ['the', 'and', 'or', 'with', 'in', 'for', 'this', 'that'],
            'es': ['el', 'la', 'los', 'las', 'y', 'o', 'con', 'en'],
            'de': ['der', 'die', 'das', 'und', 'oder', 'mit', 'in', 'für']
        }
        
        scores = {}
        for lang, words in lang_indicators.items():
            scores[lang] = sum(1 for word in words if f' {word} ' in text_lower)
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        return None

    def _follow_links(self, response: Response):
        """
        Suit les liens internes pour continuer l'exploration
        """
        # Sélecteurs pour les liens internes pertinents
        link_selectors = [
            '//a[contains(@href, "contact")]/@href',
            '//a[contains(@href, "about")]/@href', 
            '//a[contains(@href, "team")]/@href',
            '//a[contains(@href, "staff")]/@href',
            '//a[contains(text(), "Contact")]/@href',
            '//a[contains(text(), "About")]/@href',
            '//a/@href'  # Tous les autres liens en dernier
        ]
        
        links_found = 0
        max_links_per_page = 5
        
        for selector in link_selectors:
            if links_found >= max_links_per_page:
                break
                
            urls = response.xpath(selector).getall()
            for url in urls:
                if links_found >= max_links_per_page:
                    break
                
                absolute_url = urljoin(response.url, url)
                
                # Filtres pour les liens
                if (self._should_follow_link(absolute_url) and 
                    absolute_url not in self.visited_urls):
                    
                    self.visited_urls.add(absolute_url)
                    links_found += 1
                    
                    yield Request(
                        url=absolute_url,
                        callback=self.parse,
                        errback=self.handle_error,
                        meta={'dont_cache': True}
                    )

    def _should_follow_link(self, url: str) -> bool:
        """
        Détermine si un lien doit être suivi
        """
        try:
            parsed = urlparse(url)
            
            # Même domaine seulement
            if parsed.netloc not in self.allowed_domains:
                return False
            
            # Éviter certains types de fichiers
            ignored_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.png', '.gif', '.zip']
            if any(url.lower().endswith(ext) for ext in ignored_extensions):
                return False
            
            # Éviter certains patterns d'URL
            ignored_patterns = ['javascript:', 'mailto:', 'tel:', '#']
            if any(pattern in url.lower() for pattern in ignored_patterns):
                return False
            
            return True
            
        except Exception:
            return False

    def handle_error(self, failure):
        """
        Gestion des erreurs de requête
        """
        logger.error(f"Erreur requête {failure.request.url}: {failure.value}")

    def closed(self, reason):
        """
        Appelé à la fermeture du spider
        """
        logger.info(f"Spider fermé: {reason}")
        logger.info(f"Statistiques finales:")
        logger.info(f"  - Pages visitées: {self.pages_crawled}")
        logger.info(f"  - Contacts trouvés: {self.contacts_found}")
        logger.info(f"  - URLs visitées: {len(self.visited_urls)}")
        logger.info(f"  - Mots-clés utilisés: {len(self.custom_keywords)}")
        logger.info(f"  - Mode correspondance: {self.match_mode}")