import os
import psycopg2
import streamlit as st
from psycopg2.extras import RealDictCursor

DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper"),
    user=os.getenv("POSTGRES_USER", "scraper"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper"),
)

def db_cursor():
    conn = psycopg2.connect(**DB, connect_timeout=5)
    return conn, conn.cursor(cursor_factory=RealDictCursor)

def main():
    st.set_page_config(page_title="Scraper Dashboard", layout="wide")
    st.title("Dashboard OK")
    st.write("Si vous voyez cette page, Streamlit fonctionne.")

if __name__ == "__main__":
    main()
