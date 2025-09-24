import os
import scrapy
import hashlib
import urllib.parse
from scrapy_playwright.page import PageMethod
from scraper.items import ContactItem
from scraper.utils.filters import page_lang_from_text, matches_keywords
from scraper.utils.parsing import find_emails, find_phones, absolutize, get_domain, guess_name_from_text

# Fonctions utilitaires directement dans le fichier pour éviter les imports manquants
def content_hash(text: str) -> str:
    """Génère un hash SHA256 du contenu"""
    if text is None:
        text = ""
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()

def normalize_url(url: str) -> str:
    """Normalise une URL"""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower() or "http"
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        query = urllib.parse.urlencode(sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)))
        return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))
    except:
        return url

# Cache simple pour éviter les doublons (en mémoire pour cette session)
_seen_urls = set()

def is_seen(url: str, job_id=None) -> bool:
    """Vérifie si l'URL a déjà été vue"""
    norm = normalize_url(url)
    return norm in _seen_urls

def mark_seen(url: str, job_id=None):
    """Marque l'URL comme vue"""
    norm = normalize_url(url)
    _seen_urls.add(norm)

def get_storage_state_path(session_id):
    """Récupère le chemin du storage state (simplifié)"""
    if not session_id:
        return None
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        DB = dict(
            host=os.getenv("POSTGRES_HOST", "db"), 
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "scraper_pro"), 
            user=os.getenv("POSTGRES_USER", "scraper_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "scraper")
        )
        
        conn = psycopg2.connect(**DB)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT file_path FROM sessions 
                WHERE id = %s AND active = true AND deleted_at IS NULL
            """, (session_id,))
            
            result = cur.fetchone()
            if result and result['file_path']:
                file_path = result['file_path']
                # Vérification sécurisée du chemin
                if file_path.startswith('/app/sessions') and os.path.exists(file_path):
                    return file_path
        
        conn.close()
    except Exception as e:
        print(f"Erreur récupération session {session_id}: {e}")
    
    return None

def playwright_proxy_kwargs():
    """Récupère la configuration proxy pour Playwright (simplifié)"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        DB = dict(
            host=os.getenv("POSTGRES_HOST", "db"), 
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "scraper_pro"), 
            user=os.getenv("POSTGRES_USER", "scraper_admin"),
            password=os.getenv("POSTGRES_PASSWORD", "scraper")
        )
        
        conn = psycopg2.connect(**DB)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT scheme, host, port, username, password 
                FROM proxies 
                WHERE active = true 
                ORDER BY priority ASC, RANDOM() 
                LIMIT 1
            """)
            
            proxy = cur.fetchone()
            if proxy:
                proxy_config = {
                    "server": f"{proxy['scheme']}://{proxy['host']}:{proxy['port']}"
                }
                if proxy['username']:
                    proxy_config["username"] = proxy['username']
                    proxy_config["password"] = proxy['password'] or ""
                
                return proxy_config
        
        conn.close()
    except Exception as e:
        print(f"Erreur récupération proxy: {e}")
    
    return None

BLOCK_TYPES = ["image", "media", "font", "stylesheet", "other"]

def matches_custom(text, custom_keywords):
    """Vérifie si le texte contient des mots-clés personnalisés"""
    if not custom_keywords:
        return False
    
    t = (text or "").lower()
    for k in custom_keywords:
        if k.lower() in t:
            return True
    return False

class SingleURLSpider(scrapy.Spider):
    name = "single_url"
    custom_settings = {"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000}
    
    def __init__(self, url, theme="lawyers", lang_filter=None, country_filter=None,
                 query_id=None, use_js="0", max_pages_per_domain="15", 
                 target_remaining="0", logic_mode="or", session_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.start_url = url
        self.theme = theme
        self.lang_filter = lang_filter
        self.country_filter = country_filter
        self.query_id = int(query_id) if query_id else None
        self.use_js = (str(use_js) == "1")
        self.max_pages = int(max_pages_per_domain or 15)
        self.to_collect = int(target_remaining or 0)
        self.logic_mode = (logic_mode or 'or').lower()
        self.session_id = int(session_id) if session_id else None
        
        self.collected = 0
        self.visited = {}
        self.px = playwright_proxy_kwargs()
        
        # Mots-clés personnalisés depuis l'environnement
        raw = os.environ.get("DASHBOARD_KEYWORDS", "")
        self.custom_keywords = [s.strip() for s in raw.splitlines() if s.strip()]
    
    def start_requests(self):
        meta = {"seed_url": self.start_url, "country": self.country_filter}
        
        if self.use_js:
            methods = [
                PageMethod("route", "**/*", 
                          lambda route, req: route.abort() if req.resource_type in BLOCK_TYPES else route.continue_()),
                PageMethod("wait_for_load_state", "networkidle")
            ]
            meta.update({"playwright": True, "playwright_page_methods": methods})
            
            ctx = {}
            if self.px:
                ctx["proxy"] = self.px
            
            sspath = get_storage_state_path(self.session_id)
            if sspath:
                ctx["storage_state"] = sspath
            
            if ctx:
                meta["playwright_context_kwargs"] = ctx
        
        yield scrapy.Request(self.start_url, meta=meta, callback=self.parse_page)
    
    def parse_page(self, response):
        if self.to_collect and self.collected >= self.to_collect:
            return
        
        host = response.url.split('/')[2]
        self.visited[host] = self.visited.get(host, 0) + 1
        
        if self.visited[host] > self.max_pages:
            return
        
        text = " ".join(response.css("body ::text").getall())
        page_lang = page_lang_from_text(text) or (self.lang_filter or "en")
        
        emails = find_emails(text)
        phones = find_phones(text)
        
        # Vérification des critères de correspondance
        ok_lang = matches_keywords(text, page_lang, self.theme) or \
                 matches_keywords(text, (self.lang_filter or "en"), self.theme)
        ok_custom = matches_custom(text, self.custom_keywords) if self.custom_keywords else False
        
        ok_logic = (ok_lang and ok_custom) if self.logic_mode == 'and' else \
                  (ok_lang or ok_custom or (not self.custom_keywords))
        
        if emails and ok_logic:
            # Extraction des informations de contact
            name = response.css("h1::text,h2::text,.title::text,.author::text,.name::text").get()
            org = response.css(".org::text,.organization::text,.company::text,.firm::text,.law-firm::text, .site-title::text, .navbar-brand::text").get() or get_domain(response.url)
            
            if not name:
                name = guess_name_from_text(text)
            
            item = ContactItem(
                name=name,
                org=org,
                email=emails[0],
                languages=page_lang,
                phone=phones[0] if phones else None,
                country=response.meta.get("country"),
                url=response.url,
                theme=self.theme,
                source="Dashboard",
                page_lang=page_lang,
                raw_text=None,
                query_id=self.query_id,
                seed_url=response.meta.get("seed_url")
            )
            
            self.collected += 1
            yield item
            
            if self.to_collect and self.collected >= self.to_collect:
                return
        
        # Suivi des liens
        for href in response.css("a::attr(href)").getall()[:80]:
            u = absolutize(response.url, href)
            nu = normalize_url(u)
            
            if is_seen(nu, job_id=self.query_id):
                continue
            
            mark_seen(nu, job_id=self.query_id)
            
            if self.to_collect and self.collected >= self.to_collect:
                break
            
            if u.startswith("http") and (u.split('/')[2] == host):
                yield scrapy.Request(u, meta=response.meta, callback=self.parse_page)