import os, psycopg2
from psycopg2.extras import RealDictCursor
DB=dict(host=os.getenv("POSTGRES_HOST","db"), port=int(os.getenv("POSTGRES_PORT","5432")),
        dbname=os.getenv("POSTGRES_DB","scraper"), user=os.getenv("POSTGRES_USER","scraper"),
        password=os.getenv("POSTGRES_PASSWORD","scraper"))
def get_db_proxy():
    try:
        conn=psycopg2.connect(**DB); cur=conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT * FROM proxies WHERE active=true ORDER BY priority ASC, COALESCE(last_used_at,'1970-01-01') ASC LIMIT 1""")
        row=cur.fetchone()
        if row:
            cur.execute("UPDATE proxies SET last_used_at=now() WHERE id=%s",(row["id"],)); conn.commit()
        cur.close(); conn.close(); return row
    except Exception: return None
def playwright_proxy_kwargs():
    row=get_db_proxy()
    if row and row.get("host") and row.get("port"):
        cred=""
        if row.get("username") and row.get("password"):
            cred=f"{row['username']}:{row['password']}@"
        return {"server": f"{row.get('scheme','http')}://{cred}{row['host']}:{row['port']}"}
    server=os.getenv("PROXY_SERVER")
    if server:
        user=os.getenv("PROXY_USERNAME",""); pwd=os.getenv("PROXY_PASSWORD","")
        cred=f"{user}:{pwd}@" if user and pwd else ""
        return {"server": f"{server}" if "://" in server else f"http://{cred}{server}"}
    return None
