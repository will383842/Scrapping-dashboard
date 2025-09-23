import os
import time
import logging
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s scheduler: %(message)s",
)

DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper"),
    user=os.getenv("POSTGRES_USER", "scraper"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper"),
)

POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "5"))

def get_db_conn():
    return psycopg2.connect(**DB, connect_timeout=5)

def boot_apply_env_limits(conn):
    try:
        limit = os.getenv("JS_PAGES_LIMIT")
        if limit and str(limit).isdigit():
            with conn.cursor() as q:
                q.execute(
                    "INSERT INTO settings(key,value) VALUES('js_pages_limit', %s) "
                    "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                    (str(limit),),
                )
                conn.commit()
            logging.info("Applied JS_PAGES_LIMIT=%s at boot.", limit)
        else:
            logging.info("No JS_PAGES_LIMIT provided or invalid; keeping DB value.")
    except Exception as e:
        logging.exception("boot_apply_env_limits error: %s", e)

def claim_one_job(conn):
    sql = """
    WITH picked AS (
      SELECT id, url, use_js
      FROM queue
      WHERE status = 'pending'
      ORDER BY priority DESC, id ASC
      FOR UPDATE SKIP LOCKED
      LIMIT 1
    )
    UPDATE queue q
    SET status = 'in_progress', updated_at = NOW()
    FROM picked
    WHERE q.id = picked.id
    RETURNING q.id, picked.url, picked.use_js;
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        row = cur.fetchone()
        conn.commit()
        return row

def set_job_status(conn, job_id, status, error_msg=None):
    with conn.cursor() as cur:
        if error_msg:
            cur.execute(
                "UPDATE queue SET status=%s, error=LEFT(%s, 500), updated_at=NOW() WHERE id=%s",
                (status, error_msg, job_id),
            )
        else:
            cur.execute(
                "UPDATE queue SET status=%s, updated_at=NOW() WHERE id=%s",
                (status, job_id),
            )
        conn.commit()

def run_spider(url, use_js):
    args = [
        "scrapy", "crawl", "single_url",
        "-a", f"url={url}",
        "-a", f"use_js={1 if use_js else 0}",
    ]
    res = subprocess.run(args, cwd="/app/scraper", capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

def main():
    logging.info("Scheduler starting...")
    conn = None
    while True:
        try:
            if conn is None or conn.closed:
                conn = get_db_conn()
                boot_apply_env_limits(conn)

            job = claim_one_job(conn)
            if not job:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            jid = job["id"]
            url = job["url"]
            use_js = bool(job["use_js"])
            logging.info("Picked job id=%s url=%s use_js=%s", jid, url, use_js)

            code, out, err = run_spider(url, use_js)
            if code == 0:
                set_job_status(conn, jid, "done")
                logging.info("Job %s done.", jid)
            else:
                set_job_status(conn, jid, "failed", error_msg=err or out or f"exit {code}")
                logging.error("Job %s failed (code=%s).", jid, code)

        except psycopg2.Error as db_err:
            logging.error("DB error: %s", db_err)
            time.sleep(3)
            try:
                if conn and not conn.closed:
                    conn.close()
            except Exception:
                pass
            conn = None
        except Exception as e:
            logging.exception("Unexpected error: %s", e)
            time.sleep(2)

if __name__ == "__main__":
    main()
