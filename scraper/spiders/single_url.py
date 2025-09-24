import os, scrapy
from scrapy_playwright.page import PageMethod
from scraper.items import ContactItem
from scraper.utils.filters import page_lang_from_text, matches_keywords
from scraper.utils.parsing import find_emails, find_phones, absolutize, get_domain, guess_name_from_text
from scraper.utils.proxy import playwright_proxy_kwargs
from scraper.utils.session import get_storage_state_path

BLOCK_TYPES=["image","media","font","stylesheet","other"]

def matches_custom(text, custom_keywords):
    t=(text or "").lower()
    for k in custom_keywords:
        if k.lower() in t: return True
    return False

class SingleURLSpider(scrapy.Spider):
    name="single_url"
    custom_settings={"PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT":30000}
    def __init__(self, url, theme="lawyers", lang_filter=None, country_filter=None,
                 query_id=None, use_js="0", max_pages_per_domain="15", target_remaining="0", logic_mode="or", session_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_url=url; self.theme=theme; self.lang_filter=lang_filter; self.country_filter=country_filter
        self.query_id=int(query_id) if query_id else None
        self.use_js=(str(use_js)=="1"); self.max_pages=int(max_pages_per_domain or 15)
        self.to_collect=int(target_remaining or 0)
        self.logic_mode=(logic_mode or 'or').lower()
        self.session_id = int(session_id) if session_id else None
        self.collected=0
        self.visited={}; self.px=playwright_proxy_kwargs()
        raw=os.environ.get("DASHBOARD_KEYWORDS",""); self.custom_keywords=[s.strip() for s in raw.splitlines() if s.strip()]
    def start_requests(self):
        meta={"seed_url": self.start_url, "country": self.country_filter}
        if self.use_js:
            methods=[PageMethod("route","**/*", lambda route, req: route.abort() if req.resource_type in BLOCK_TYPES else route.continue_()),
                     PageMethod("wait_for_load_state","networkidle")]
            meta.update({"playwright": True, "playwright_page_methods": methods})
            ctx={}
            if self.px: ctx["proxy"]=self.px
            sspath = get_storage_state_path(self.session_id)
            if sspath: ctx["storage_state"]=sspath
            if ctx: meta["playwright_context_kwargs"]=ctx
        yield scrapy.Request(self.start_url, meta=meta, callback=self.parse_page)
    def parse_page(self, response):
        if self.to_collect and self.collected >= self.to_collect:
            return
        host=response.url.split('/')[2]; self.visited[host]=self.visited.get(host,0)+1
        if self.visited[host] > self.max_pages: return
        text=" ".join(response.css("body ::text").getall())
        page_lang=page_lang_from_text(text) or (self.lang_filter or "en")
        emails=find_emails(text); phones=find_phones(text)
        ok_lang = matches_keywords(text, page_lang, self.theme) or matches_keywords(text, (self.lang_filter or "en"), self.theme)
        ok_custom = matches_custom(text, self.custom_keywords) if self.custom_keywords else False
        ok_logic = (ok_lang and ok_custom) if self.logic_mode == 'and' else (ok_lang or ok_custom or (not self.custom_keywords))

        if emails and ok_logic:
            name = response.css("h1::text,h2::text,.title::text,.author::text,.name::text").get()
            org = response.css(".org::text,.organization::text,.company::text,.firm::text,.law-firm::text, .site-title::text, .navbar-brand::text").get() or get_domain(response.url)
            if not name:
                name = guess_name_from_text(text)
            item = ContactItem(name=name, org=org, email=emails[0], languages=page_lang,
                               phone=phones[0] if phones else None, country=response.meta.get("country"),
                               url=response.url, theme=self.theme, source="Dashboard", page_lang=page_lang,
                               raw_text=None, content_hash=content_hash(response.text), query_id=self.query_id, seed_url=response.meta.get("seed_url"))
            self.collected += 1
            yield item
            if self.to_collect and self.collected >= self.to_collect:
                return

        for href in response.css("a::attr(href)").getall()[:80]:
            nu = normalize(absolutize(response.url, href))
            if is_seen(nu, job_id=self.query_id):
                continue
            mark_seen(nu, job_id=self.query_id)
            if self.to_collect and self.collected >= self.to_collect:
                break
            u=absolutize(response.url, href)
            if u.startswith("http") and (u.split('/')[2]==host):
                yield scrapy.Request(u, meta=response.meta, callback=self.parse_page)
