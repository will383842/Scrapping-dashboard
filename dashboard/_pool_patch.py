from psycopg2.pool import SimpleConnectionPool

# --- Pool de connexions global (mis en cache) ---
@st.cache_resource
def get_db_pool() -> SimpleConnectionPool:
    # bornes min/max du pool (adapte si besoin)
    minconn = int(os.getenv("DB_POOL_MIN", "1"))
    maxconn = int(os.getenv("DB_POOL_MAX", "10"))
    pool = SimpleConnectionPool(minconn, maxconn, **DB_CONFIG)
    return pool

def execute_query(query: str, params: tuple = None, fetch: str = "all"):
    """Exécute une requête via le pool (connexion rendue au pool ensuite)."""
    pool = get_db_pool()
    conn = None
    try:
        conn = pool.getconn()
        # lecture/écriture safe
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch == "all":
                rows = cur.fetchall()
            elif fetch == "one":
                rows = cur.fetchone()
            else:  # 'none'
                conn.commit()
                rows = True
        return rows
    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        st.error(f"Erreur requête: {e}")
        return None
    finally:
        if conn:
            pool.putconn(conn)