import psycopg2, os, logging, re
from psycopg2.extras import RealDictCursor
DB = dict(host=os.getenv("POSTGRES_HOST","db"), port=int(os.getenv("POSTGRES_PORT","5432")),
          dbname=os.getenv("POSTGRES_DB","scraper"), user=os.getenv("POSTGRES_USER","scraper"),
          password=os.getenv("POSTGRES_PASSWORD","scraper"))
def derive_name_from_email(email: str):
    if not email: return None
    local = email.split('@')[0]
    candidate = re.sub(r'[._+-]+', ' ', local).strip()
    if len(candidate) >= 2:
        return candidate.title()
    return None
class PostgresPipeline:
    def open_spider(self, spider):
        self.conn = psycopg2.connect(**DB); self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
    def close_spider(self, spider):
        self.conn.commit(); self.cur.close(); self.conn.close()
    def process_item(self, item, spider):
        email = (item.get("email") or "").strip()
        name = (item.get("name") or "").strip()
        if not email:
            return item
        if not name:
            name = derive_name_from_email(email) or None
            item["name"] = name
        if not name:
            return item
        fields=["name","org","email","languages","phone","country","url","theme","source","page_lang","raw_text","query_id","seed_url"]
        vals=[item.get(f) for f in fields]
        try:
            self.cur.execute("""
                INSERT INTO contacts(name,org,email,languages,phone,country,url,theme,source,page_lang,raw_text,query_id,seed_url)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(email) DO UPDATE SET
                    name=COALESCE(EXCLUDED.name, contacts.name),
                    org=COALESCE(EXCLUDED.org, contacts.org),
                    languages=COALESCE(EXCLUDED.languages, contacts.languages),
                    phone=COALESCE(EXCLUDED.phone, contacts.phone),
                    country=COALESCE(EXCLUDED.country, contacts.country),
                    url=COALESCE(EXCLUDED.url, contacts.url),
                    theme=COALESCE(EXCLUDED.theme, contacts.theme),
                    source=COALESCE(EXCLUDED.source, contacts.source),
                    page_lang=COALESCE(EXCLUDED.page_lang, contacts.page_lang),
                    raw_text=COALESCE(EXCLUDED.raw_text, contacts.raw_text),
                    updated_at=now(),
                    query_id=COALESCE(EXCLUDED.query_id, contacts.query_id),
                    seed_url=COALESCE(EXCLUDED.seed_url, contacts.seed_url)
            """, vals)
            self.conn.commit()
        except Exception as e:
            logging.exception("DB insert failed: %s", e)
        return item
