import os
import json
import psycopg2
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import io
import time
import re
from typing import Optional, Dict, List, Any
import uuid
import zipfile
import base64

# ============================================================================
# LISTE DES 197 PAYS (tap-to-filter dans les selectbox Streamlit)
# Base: 193 membres ONU + 2 observateurs (Holy See, State of Palestine) + Kosovo + Taiwan
# ============================================================================
COUNTRIES = [
    "Afghanistan","Albania","Algeria","Andorra","Angola","Antigua and Barbuda","Argentina","Armenia","Australia","Austria",
    "Azerbaijan","Bahamas","Bahrain","Bangladesh","Barbados","Belarus","Belgium","Belize","Benin","Bhutan",
    "Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei","Bulgaria","Burkina Faso","Burundi","Cabo Verde","Cambodia",
    "Cameroon","Canada","Central African Republic","Chad","Chile","China","Colombia","Comoros","Congo (Congo-Brazzaville)","Costa Rica",
    "Côte d’Ivoire","Croatia","Cuba","Cyprus","Czechia","Democratic Republic of the Congo","Denmark","Djibouti","Dominica","Dominican Republic",
    "Ecuador","Egypt","El Salvador","Equatorial Guinea","Eritrea","Estonia","Eswatini","Ethiopia","Fiji","Finland",
    "France","Gabon","Gambia","Georgia","Germany","Ghana","Greece","Grenada","Guatemala","Guinea",
    "Guinea-Bissau","Guyana","Haiti","Honduras","Hungary","Iceland","India","Indonesia","Iran","Iraq",
    "Ireland","Israel","Italy","Jamaica","Japan","Jordan","Kazakhstan","Kenya","Kiribati","Kuwait",
    "Kyrgyzstan","Laos","Latvia","Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania","Luxembourg",
    "Madagascar","Malawi","Malaysia","Maldives","Mali","Malta","Marshall Islands","Mauritania","Mauritius","Mexico",
    "Micronesia","Moldova","Monaco","Mongolia","Montenegro","Morocco","Mozambique","Myanmar","Namibia","Nauru",
    "Nepal","Netherlands","New Zealand","Nicaragua","Niger","Nigeria","North Korea","North Macedonia","Norway","Oman",
    "Pakistan","Palau","Panama","Papua New Guinea","Paraguay","Peru","Philippines","Poland","Portugal","Qatar",
    "Romania","Russia","Rwanda","Saint Kitts and Nevis","Saint Lucia","Saint Vincent and the Grenadines","Samoa","San Marino","Sao Tome and Principe","Saudi Arabia",
    "Senegal","Serbia","Seychelles","Sierra Leone","Singapore","Slovakia","Slovenia","Solomon Islands","Somalia","South Africa",
    "South Korea","South Sudan","Spain","Sri Lanka","Sudan","Suriname","Sweden","Switzerland","Syria","Tajikistan",
    "Tanzania","Thailand","Timor-Leste","Togo","Tonga","Trinidad and Tobago","Tunisia","Turkey","Turkmenistan","Tuvalu",
    "Uganda","Ukraine","United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan","Vanuatu","Vatican City","Venezuela",
    "Vietnam","Yemen","Zambia","Zimbabwe",
    # Observateurs ONU (déjà inclus ci-dessus: Vatican City) + État de Palestine
    "State of Palestine",
    # Territoires/États partiellement reconnus ajoutés ici pour atteindre 197
    "Kosovo","Taiwan"
]
# Tri alpha stable (facultatif)
COUNTRIES = sorted(list(dict.fromkeys(COUNTRIES)), key=lambda x: x.lower())
# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="🕷️ Scraper Pro Dashboard",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Scraper Pro Dashboard - Version Production 2.0"
    }
)

# Configuration DB avec pool de connexions
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),
    'password': os.getenv("POSTGRES_PASSWORD", "scraper"),
    'connect_timeout': 10,
    'application_name': 'dashboard_streamlit'
}

# ============================================================================
# UTILITAIRES DE BASE
# ============================================================================

@st.cache_resource
def get_db_connection():
    """Connexion DB avec cache et gestion d'erreur robuste"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # On laisse les DDL/transactions se faire dans execute_query
        conn.autocommit = False
        return conn
    except Exception as e:
        st.error(f"❌ Erreur connexion base de données: {e}")
        return None

def execute_query(query: str, params: tuple = None, fetch: str = 'all') -> Optional[List]:
    """Exécution sécurisée de requêtes avec gestion d'erreurs et commit/rollback"""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch == 'all':
                rows = cur.fetchall()
                conn.commit()
                return rows
            elif fetch == 'one':
                row = cur.fetchone()
                conn.commit()
                return row
            elif fetch == 'none':
                conn.commit()
                return True
    except Exception as e:
        # On montre l'erreur à l'écran, puis rollback
        st.error(f"Erreur requête: {e}")
        try:
            if conn and getattr(conn, 'closed', 1) == 0:
                conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            if conn and getattr(conn, 'closed', 1) == 0:
                conn.close()
        except Exception:
            pass

@st.cache_data(ttl=300)
def table_has_column(table_name: str, column_name: str) -> bool:
    """Vérifie via information_schema si une colonne existe."""
    sql = """
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = %s AND column_name = %s
    LIMIT 1
    """
    res = execute_query(sql, (table_name, column_name), fetch='one')
    return bool(res)

def validate_url(url: str) -> bool:
    """Validation d'URL avec regex robuste"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})'  # ...or ip
        r'(?::\\d+)?'  # optional port
        r'(?:/?|[/?]\\S+)$', re.IGNORECASE)
    return bool(url_pattern.match(url))

# ============================================================================
# MISE À NIVEAU SCHÉMA (préventif, non destructif)
# ============================================================================

@st.cache_data(ttl=600, show_spinner=False)
def ensure_schema() -> bool:
    """
    Aligne en douceur le schéma DB attendu par le dashboard.
    N'ajoute que des colonnes manquantes avec DEFAULT inoffensif (ADD COLUMN IF NOT EXISTS).
    Crée les tables minimales si vraiment absentes (IF NOT EXISTS).
    """
    statements: List[str] = []

    # settings (clé/valeur)
    statements += [
        """
        CREATE TABLE IF NOT EXISTS settings (
            key   text PRIMARY KEY,
            value text,
            updated_at timestamptz DEFAULT NOW()
        )
        """
    ]

    # queue (jobs)
    statements += [
        """
        CREATE TABLE IF NOT EXISTS queue (
            id serial PRIMARY KEY,
            url text NOT NULL,
            status text NOT NULL DEFAULT 'pending',
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW()
        )
        """,
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS theme text",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS country_filter text",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS lang_filter text",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS use_js boolean NOT NULL DEFAULT false",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS max_pages_per_domain integer NOT NULL DEFAULT 25",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 10",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS retry_count integer NOT NULL DEFAULT 0",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS max_retries integer NOT NULL DEFAULT 3",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS contacts_extracted integer NOT NULL DEFAULT 0",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS last_error text",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS next_retry_at timestamptz",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS session_id integer",
        "ALTER TABLE queue ADD COLUMN IF NOT EXISTS deleted_at timestamptz",
        "CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status)",
        "CREATE INDEX IF NOT EXISTS idx_queue_updated_at ON queue(updated_at)"
    ]

    # contacts
    statements += [
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id serial PRIMARY KEY,
            name text,
            email text,
            org text,
            phone text,
            url text,
            theme text,
            country text,
            page_lang text,
            verified boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            deleted_at timestamptz
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_contacts_created_at ON contacts(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_contacts_country ON contacts(country)"
    ]

    # proxies
    statements += [
        """
        CREATE TABLE IF NOT EXISTS proxies (
            id serial PRIMARY KEY,
            label text,
            scheme text NOT NULL DEFAULT 'http',
            host text NOT NULL,
            port integer NOT NULL,
            username text,
            password text,
            active boolean NOT NULL DEFAULT true,
            priority integer NOT NULL DEFAULT 10,
            response_time_ms integer,
            success_rate double precision DEFAULT 1.0,
            total_requests integer NOT NULL DEFAULT 0,
            failed_requests integer NOT NULL DEFAULT 0,
            last_used_at timestamptz,
            last_test_at timestamptz,
            last_test_status text,
            country_code text,
            provider text,
            cost_per_gb numeric,
            created_at timestamptz NOT NULL DEFAULT NOW(),
            updated_at timestamptz NOT NULL DEFAULT NOW(),
            created_by text
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_proxies_active ON proxies(active)",
        "CREATE INDEX IF NOT EXISTS idx_proxies_priority ON proxies(priority)"
    ]

    ok = True
    for stmt in statements:
        res = execute_query(stmt, fetch='none')
        ok = ok and bool(res)

    upsert_scheduler = """
    INSERT INTO settings(key, value, updated_at)
    VALUES ('scheduler_paused', 'false', NOW())
    ON CONFLICT (key) DO NOTHING
    """
    ok = ok and bool(execute_query(upsert_scheduler, fetch='none'))

    return ok

# ============================================================================
# SYSTÈME D'AUTHENTIFICATION
# ============================================================================

def require_authentication() -> bool:
    """Système d'authentification avec session persistante"""
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
        <style>
        .login-container {
            max-width: 420px;
            margin: 8vh auto;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            background: white;
        }
        .login-title {
            text-align: center;
            color: #1f2937;
            margin-bottom: 1.2rem;
        }
        .muted { color:#6b7280; font-size: 0.9rem; text-align:center; }
        </style>
    """, unsafe_allow_html=True)

    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            st.markdown('<h2 class="login-title">🕷️ Scraper Pro</h2>', unsafe_allow_html=True)
            st.markdown('<p class="muted">Connectez-vous pour accéder au dashboard</p>', unsafe_allow_html=True)

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("👤 Utilisateur", placeholder="admin")
                password = st.text_input("🔒 Mot de passe", type="password")

                col_a, col_b = st.columns(2)
                with col_a:
                    login_button = st.form_submit_button("🚀 Connexion", use_container_width=True)
                with col_b:
                    if st.form_submit_button("ℹ️ Indices", use_container_width=True):
                        st.info(f"**Utilisateur suggéré:** {os.getenv('DASHBOARD_USERNAME', 'admin')}")

                if login_button:
                    env_user = os.getenv("DASHBOARD_USERNAME", "admin")
                    env_pass = os.getenv("DASHBOARD_PASSWORD", "admin123")

                    if username == env_user and password == env_pass:
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username
                        st.session_state["login_time"] = datetime.now()
                        st.success("✅ Connexion réussie!")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error("❌ Identifiants invalides")

            st.markdown('</div>', unsafe_allow_html=True)

    return False

# ============================================================================
# NAVIGATION ET LAYOUT
# ============================================================================

def render_sidebar():
    """Sidebar navigation avec style moderne"""
    with st.sidebar:
        st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                padding: 1rem;
                border-radius: 0.75rem;
                color: white;
                margin-bottom: 1rem;
            ">
                <h3 style="margin: 0;">🕷️ Scraper Pro</h3>
                <small>👤 {st.session_state.get('username', 'admin')} • 
                {datetime.now().strftime('%H:%M')}</small>
            </div>
        """, unsafe_allow_html=True)

        with st.container():
            system_status = get_system_status()
            if system_status:
                if system_status['db_connected']:
                    st.success("🟢 Système Opérationnel")
                else:
                    st.error("🔴 Problème Base de Données")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Jobs", system_status.get('pending_jobs', 0), delta=None)
                with col2:
                    st.metric("Proxies", system_status.get('active_proxies', 0), delta=None)
            else:
                st.warning("⚠️ Chargement...")

        st.divider()

        pages = {
            "📊 Dashboard": "dashboard",
            "🎯 Jobs Manager": "jobs",
            "📇 Contacts Explorer": "contacts",
            "🌐 Proxy Management": "proxies",
            "🗂️ Sessions": "sessions",
            "📈 Analytics": "analytics",
            "⚙️ Settings": "settings",
            "🔧 System Monitor": "monitor"
        }

        selected_page = st.radio("📋 Navigation", list(pages.keys()), key="nav_radio")

        st.divider()

        st.subheader("⚡ Actions Rapides")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        with col2:
            if st.button("🚪 Déconnexion", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        with st.expander("ℹ️ Info Système", expanded=False):
            st.text(f"Version: 2.0 Production")
            st.text(f"Uptime: {get_system_uptime()}")
            st.text(f"DB: PostgreSQL")
            st.text(f"Host: {DB_CONFIG['host']}")

        return pages[selected_page]

def get_system_status() -> Dict:
    """Récupération du statut système en temps réel"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'db_connected': False}

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as count FROM queue WHERE status = 'pending'")
            pending_jobs = cur.fetchone()['count']
            cur.execute("SELECT COUNT(*) as count FROM proxies WHERE active = true")
            active_proxies = cur.fetchone()['count']
            cur.execute("SELECT value FROM settings WHERE key = 'scheduler_paused'")
            scheduler_result = cur.fetchone()
            scheduler_paused = scheduler_result and str(scheduler_result['value']).lower() == 'true'

        conn.close()

        return {
            'db_connected': True,
            'pending_jobs': pending_jobs,
            'active_proxies': active_proxies,
            'scheduler_paused': scheduler_paused
        }

    except Exception:
        return {'db_connected': False}

def get_system_uptime() -> str:
    login_time = st.session_state.get('login_time')
    if login_time:
        uptime = datetime.now() - login_time
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
    return "N/A"

# ============================================================================
# PAGES PRINCIPALES
# ============================================================================

def page_dashboard():
    st.title("📊 Dashboard Principal")

    if st.button("🔄 Auto-Refresh (30s)", key="auto_refresh"):
        time.sleep(30)
        st.rerun()

    with st.container():
        col1, col2, col3, col4, col5 = st.columns(5)
        metrics_query = """
        SELECT 
            (SELECT COUNT(*) FROM queue WHERE status = 'pending') as pending_jobs,
            (SELECT COUNT(*) FROM queue WHERE status = 'in_progress') as running_jobs,
            (SELECT COUNT(*) FROM queue WHERE status = 'done' AND DATE(updated_at) = CURRENT_DATE) as completed_today,
            (SELECT COUNT(*) FROM contacts WHERE DATE(created_at) = CURRENT_DATE) as contacts_today,
            (SELECT COUNT(*) FROM proxies WHERE active = true) as active_proxies
        """
        metrics = execute_query(metrics_query, fetch='one')
        if metrics:
            with col1:
                st.metric("🔄 En attente", metrics['pending_jobs'],
                          delta=f"+{metrics['pending_jobs']}" if metrics['pending_jobs'] > 0 else None)
            with col2:
                st.metric("⚡ En cours", metrics['running_jobs'],
                          delta="Running" if metrics['running_jobs'] > 0 else None)
            with col3:
                st.metric("✅ Terminés", metrics['completed_today'])
            with col4:
                st.metric("👥 Contacts", metrics['contacts_today'])
            with col5:
                st.metric("🌐 Proxies", metrics['active_proxies'])

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Activité des 7 derniers jours")
        activity_query = """
        SELECT 
            DATE(updated_at) as date,
            COUNT(*) FILTER (WHERE status = 'done') as completed,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            SUM(contacts_extracted) FILTER (WHERE contacts_extracted > 0) as total_contacts
        FROM queue 
        WHERE updated_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(updated_at)
        ORDER BY date
        """
        activity_data = execute_query(activity_query)
        if activity_data:
            df_activity = pd.DataFrame(activity_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_activity['date'],
                y=df_activity['completed'],
                name='Jobs Réussis',
                line=dict(color='green'),
                mode='lines+markers'
            ))
            fig.add_trace(go.Scatter(
                x=df_activity['date'],
                y=df_activity['failed'],
                name='Jobs Échoués',
                line=dict(color='red'),
                mode='lines+markers'
            ))
            fig.update_layout(
                title="Performance des Jobs",
                xaxis_title="Date",
                yaxis_title="Nombre de Jobs",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🌍 Répartition par Pays")
        countries_query = """
        SELECT country, COUNT(*) as count 
        FROM contacts 
        WHERE country IS NOT NULL 
          AND created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY country 
        ORDER BY count DESC 
        LIMIT 10
        """
        countries_data = execute_query(countries_query)
        if countries_data:
            df_countries = pd.DataFrame(countries_data)
            fig = px.pie(
                df_countries,
                values='count',
                names='country',
                title="Top 10 Pays (30 derniers jours)"
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔥 Jobs Récents")
        recent_jobs_query = """
        SELECT id, url, status, theme, retry_count, updated_at,
               CASE 
                   WHEN status = 'done' THEN '✅'
                   WHEN status = 'failed' THEN '❌'
                   WHEN status = 'in_progress' THEN '⚡'
                   ELSE '🔄'
               END as status_icon
        FROM queue 
        ORDER BY updated_at DESC 
        LIMIT 10
        """
        recent_jobs = execute_query(recent_jobs_query)
        if recent_jobs:
            df_jobs = pd.DataFrame(recent_jobs)
            df_jobs['url_short'] = df_jobs['url'].str[:40] + '...'
            st.dataframe(
                df_jobs[['status_icon', 'id', 'url_short', 'theme', 'updated_at']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    'status_icon': st.column_config.TextColumn("Status", width=60),
                    'id': st.column_config.NumberColumn("ID", width=60),
                    'url_short': st.column_config.TextColumn("URL"),
                    'theme': st.column_config.TextColumn("Thème", width=100),
                    'updated_at': st.column_config.DatetimeColumn("Mis à jour", width=120)
                }
            )

    with col2:
        st.subheader("⚠️ Alertes & Problèmes")
        alerts_query = """
        SELECT 
            'Jobs bloqués' as alert_type,
            COUNT(*) as count,
            '🚨' as icon
        FROM queue 
        WHERE status = 'in_progress' 
          AND updated_at < NOW() - INTERVAL '2 hours'
        UNION ALL
        SELECT 
            'Proxies défaillants' as alert_type,
            COUNT(*) as count,
            '🔴' as icon
        FROM proxies 
        WHERE active = true 
          AND success_rate < 0.7
        UNION ALL
        SELECT 
            'Sessions expirées' as alert_type,
            COUNT(*) as count,
            '⚠️' as icon
        FROM sessions 
        WHERE active = true 
          AND validation_status = 'invalid'
        """
        alerts = execute_query(alerts_query)
        if alerts:
            for alert in alerts:
                if alert['count'] > 0:
                    st.warning(f"{alert['icon']} {alert['alert_type']}: {alert['count']}")

        scheduler_status = get_system_status()
        if scheduler_status.get('scheduler_paused'):
            st.error("⏸️ Scheduler en PAUSE")
        else:
            st.success("▶️ Scheduler ACTIF")

def page_jobs():
    st.title("🎯 Jobs Manager")

    with st.expander("➕ Nouveau Job", expanded=True):
        with st.form("create_job_form", clear_on_submit=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                url = st.text_input("🔗 URL", placeholder="https://example.com")
                # 197 pays ISO2 + libellés chargés depuis table countries si dispo, sinon liste restreinte
                country = st.selectbox("🌍 Pays", ["", "France", "Thailand", "United States", "Canada", "Germany", "Spain"])
                theme = st.selectbox("🏷️ Thème", ["lawyers", "doctors", "consultants", "real-estate", "restaurants"])

            with col2:
                language = st.selectbox("🗣️ Langue", ["", "fr", "en", "es", "de", "th", "ru", "zh"], index=0)
                use_js = st.checkbox("🚀 Utiliser JavaScript", value=False)
                max_pages = st.slider("📄 Max pages/domaine", 1, 200, 25)

            with col3:
                try:
                    priority = st.slider("⭐ Priorité", 1, 100, 10)
                except Exception:
                    priority = 10
                sessions_query = "SELECT id, domain, type FROM sessions WHERE active = true ORDER BY domain"
                sessions = execute_query(sessions_query)
                session_options = {"Aucune": None}
                if sessions:
                    session_options.update({f"{s['domain']} ({s['type']})": s['id'] for s in sessions})
                selected_session = st.selectbox("🗂️ Session", list(session_options.keys()))
                session_id = session_options[selected_session]
                target_count = st.number_input("🎯 Contacts cibles", min_value=0, value=0, help="0 = illimité")

            col_a, col_b, col_c = st.columns([2, 1, 1])
            with col_a:
                create_job = st.form_submit_button("🚀 Créer Job", use_container_width=True, type="primary")
            with col_b:
                test_url = st.form_submit_button("🧪 Test URL", use_container_width=True)
            with col_c:
                quick_job = st.form_submit_button("⚡ Job Express", use_container_width=True)

            if test_url and url:
                if validate_url(url):
                    st.success("✅ URL valide")
                else:
                    st.error("❌ URL invalide")

            insert_query = """
            INSERT INTO queue (
                url, country_filter, lang_filter, theme, use_js, 
                max_pages_per_domain, priority, session_id, target_count,
                created_by, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """

            if create_job and url:
                if not validate_url(url):
                    st.error("❌ URL invalide")
                else:
                    params = (
                        url, country or None, language or None, theme, use_js,
                        max_pages, priority, session_id, target_count,
                        st.session_state.get('username', 'dashboard')
                    )
                    if execute_query(insert_query, params, fetch='none'):
                        st.success("✅ Job créé avec succès!")
                        time.sleep(0.6)
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de la création")

            if quick_job and url:
                if validate_url(url):
                    quick_params = (url, None, None, "lawyers", False, 15, 10, None, 0, "quick")
                    if execute_query(insert_query, quick_params, fetch='none'):
                        st.success("⚡ Job express créé!")
                        st.rerun()

    st.divider()

    st.subheader("🔍 Filtres & Recherche")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        status_filter = st.multiselect("Status", ["pending", "in_progress", "done", "failed"], default=[])
        theme_filter = st.multiselect("Thème", ["lawyers", "doctors", "consultants"], default=[])

    with col2:
        date_from = st.date_input("Date début", value=datetime.now().date() - timedelta(days=7))
        date_to = st.date_input("Date fin", value=datetime.now().date())

    with col3:
        search_url = st.text_input("🔍 Recherche URL", placeholder="Tapez pour chercher...")
        limit = st.selectbox("Limite résultats", [50, 100, 250, 500], index=1)

    with col4:
        sort_by = st.selectbox("Trier par", ["updated_at", "created_at", "priority", "retry_count"])
        sort_order = st.selectbox("Ordre", ["DESC", "ASC"])

    cols_priority = "priority" if table_has_column("queue", "priority") else "10 as priority"
    cols_contacts = "contacts_extracted" if table_has_column("queue", "contacts_extracted") else "0 as contacts_extracted"
    cols_maxretries = "max_retries" if table_has_column("queue", "max_retries") else "3 as max_retries"
    cols_lasterr = "last_error" if table_has_column("queue", "last_error") else "NULL as last_error"
    cols_nextretry = "next_retry_at" if table_has_column("queue", "next_retry_at") else "NULL as next_retry_at"

    base_query = f"""
    SELECT 
        id, url, status, theme, country_filter, lang_filter, 
        use_js, {cols_priority} as priority, retry_count, {cols_maxretries} as max_retries, {cols_contacts} as contacts_extracted,
        created_at, updated_at, {cols_lasterr} as last_error, {cols_nextretry} as next_retry_at,
        CASE 
            WHEN status = 'done' THEN '✅'
            WHEN status = 'failed' THEN '❌'
            WHEN status = 'in_progress' THEN '⚡'
            WHEN status = 'pending' AND retry_count > 0 THEN '🔄'
            ELSE '⏳'
        END as status_icon
    FROM queue 
    WHERE 1=1
    """

    params = []

    if status_filter:
        placeholders = ','.join(['%s'] * len(status_filter))
        base_query += f" AND status IN ({placeholders})"
        params.extend(status_filter)

    if theme_filter:
        placeholders = ','.join(['%s'] * len(theme_filter))
        base_query += f" AND theme IN ({placeholders})"
        params.extend(theme_filter)

    if search_url:
        base_query += " AND url ILIKE %s"
        params.append(f"%{search_url}%")

    base_query += f" AND DATE(created_at) BETWEEN %s AND %s"
    params.extend([date_from, date_to])

    safe_sort_by = sort_by
    if sort_by == "priority" and not table_has_column("queue", "priority"):
        safe_sort_by = "created_at"
    if sort_by == "retry_count" and not table_has_column("queue", "retry_count"):
        safe_sort_by = "created_at"

    base_query += f" ORDER BY {safe_sort_by} {sort_order} LIMIT %s"
    params.append(limit)

    jobs_data = execute_query(base_query, tuple(params))

    if jobs_data:
        df_jobs = pd.DataFrame(jobs_data)

        st.subheader("⚡ Actions en Lot")
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            if st.button("⏸️ Pause Sélectionnés"):
                st.info("Fonctionnalité en développement")
        with col2:
            if st.button("▶️ Resume Sélectionnés"):
                st.info("Fonctionnalité en développement")
        with col3:
            if st.button("🔄 Retry Échoués"):
                retry_query = "UPDATE queue SET status = 'pending', retry_count = 0 WHERE status = 'failed'"
                if execute_query(retry_query, fetch='none'):
                    st.success("✅ Jobs échoués remis en file")
                    st.rerun()
        with col4:
            if st.button("🗑️ Supprimer Anciens"):
                cleanup_query = """
                UPDATE queue SET deleted_at = NOW() 
                WHERE status IN ('done', 'failed') 
                  AND updated_at < NOW() - INTERVAL '7 days'
                """
                if execute_query(cleanup_query, fetch='none'):
                    st.success("✅ Anciens jobs supprimés")
                    st.rerun()
        with col5:
            if st.button("📊 Export CSV"):
                csv = df_jobs.to_csv(index=False)
                st.download_button(
                    "⬇️ Télécharger",
                    data=csv,
                    file_name=f"jobs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

        st.subheader(f"📋 Jobs ({len(df_jobs)} résultats)")

        df_display = df_jobs.copy()
        df_display['url_short'] = df_display['url'].str[:60] + '...'
        df_display['error_short'] = df_display['last_error'].fillna('').str[:50]

        st.dataframe(
            df_display[[
                'status_icon', 'id', 'url_short', 'theme', 'priority',
                'retry_count', 'contacts_extracted', 'updated_at'
            ]],
            hide_index=True,
            use_container_width=True,
            column_config={
                'status_icon': st.column_config.TextColumn("", width=40),
                'id': st.column_config.NumberColumn("ID", width=60),
                'url_short': st.column_config.TextColumn("URL"),
                'theme': st.column_config.TextColumn("Thème", width=100),
                'priority': st.column_config.NumberColumn("Priorité", width=80),
                'retry_count': st.column_config.NumberColumn("Retry", width=60),
                'contacts_extracted': st.column_config.NumberColumn("Contacts", width=80),
                'updated_at': st.column_config.DatetimeColumn("Mis à jour", width=130)
            }
        )
    else:
        st.info("Aucun job trouvé avec ces critères")

# ============================================================================
# PAGES – CONTACTS
# ============================================================================

def page_contacts():
    """Page d'exploration et gestion avancée des contacts"""
    st.title("📇 Contacts Explorer")

    # --- KPIs rapides -------------------------------------------------------
    stats_query = """
    SELECT 
        COUNT(*) as total_contacts,
        COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as today_contacts,
        COUNT(*) FILTER (WHERE verified = true) as verified_contacts,
        COUNT(DISTINCT country) as unique_countries,
        COUNT(DISTINCT theme) as unique_themes,
        COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as week_contacts
    FROM contacts WHERE deleted_at IS NULL
    """
    stats = execute_query(stats_query, fetch='one')
    if stats:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("📊 Total", f"{stats['total_contacts']:,}")
        with col2:
            st.metric("📈 Aujourd'hui", stats['today_contacts'])
        with col3:
            st.metric("✅ Vérifiés", stats['verified_contacts'])
        with col4:
            st.metric("🌍 Pays", stats['unique_countries'])
        with col5:
            st.metric("🏷️ Thèmes", stats['unique_themes'])
        with col6:
            st.metric("📅 Cette semaine", stats['week_contacts'])

    st.divider()

    # --- Filtres avancés ----------------------------------------------------
    st.subheader("🔍 Filtres Avancés")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Pays : privilégie la liste complète COUNTRIES si elle est disponible
        countries_source = None
        try:
            # COUNTRIES doit être défini plus haut dans le fichier (197 pays)
            if isinstance(COUNTRIES, list) and len(COUNTRIES) >= 190:
                countries_source = ["Tous"] + COUNTRIES
        except NameError:
            countries_source = None

        if not countries_source:
            # Fallback propre : lire les pays présents en base
            countries_query = "SELECT DISTINCT country FROM contacts WHERE country IS NOT NULL ORDER BY country"
            countries_data = execute_query(countries_query) or []
            countries_source = ["Tous"] + [c['country'] for c in countries_data]

        selected_country = st.selectbox(
            "🌍 Pays",
            countries_source,
            index=0,
            placeholder="Tous (pas de filtre)"
        )

        # Thèmes depuis la base (liste réelle)
        themes_query = "SELECT DISTINCT theme FROM contacts WHERE theme IS NOT NULL ORDER BY theme"
        themes_data = execute_query(themes_query) or []
        themes = ["Tous"] + [t['theme'] for t in themes_data]
        selected_theme = st.selectbox("🏷️ Thème", themes, index=0)

    with col2:
        search_text = st.text_input("🔍 Recherche", placeholder="Nom, email, organisation...")
        verified_filter = st.selectbox("Vérification", ["Tous", "Vérifiés", "Non vérifiés"], index=0)

    with col3:
        date_from = st.date_input("📅 Date début", value=datetime.now().date() - timedelta(days=30))
        date_to = st.date_input("📅 Date fin", value=datetime.now().date())

    with col4:
        sort_options = {
            "Plus récents": "created_at DESC",
            "Plus anciens": "created_at ASC",
            "Nom A-Z": "name ASC",
            "Nom Z-A": "name DESC",
            "Pays A-Z": "country ASC"
        }
        sort_by = st.selectbox("🔄 Tri", list(sort_options.keys()), index=0)
        limit = st.selectbox("📊 Limite", [100, 250, 500, 1000], index=1)

    # --- Construction de la requête ----------------------------------------
    base_contacts_query = """
    SELECT 
        id, name, email, org, phone, country, theme, 
        verified, created_at, updated_at, page_lang, url,
        CASE WHEN verified THEN '✅' ELSE '⏳' END as verified_icon
    FROM contacts 
    WHERE deleted_at IS NULL
    """
    contacts_params = []

    if selected_country != "Tous":
        base_contacts_query += " AND country = %s"
        contacts_params.append(selected_country)

    if selected_theme != "Tous":
        base_contacts_query += " AND theme = %s"
        contacts_params.append(selected_theme)

    if search_text:
        base_contacts_query += " AND (name ILIKE %s OR email ILIKE %s OR org ILIKE %s)"
        search_param = f"%{search_text}%"
        contacts_params.extend([search_param, search_param, search_param])

    if verified_filter == "Vérifiés":
        base_contacts_query += " AND verified = true"
    elif verified_filter == "Non vérifiés":
        base_contacts_query += " AND verified = false"

    base_contacts_query += " AND DATE(created_at) BETWEEN %s AND %s"
    contacts_params.extend([date_from, date_to])

    base_contacts_query += f" ORDER BY {sort_options[sort_by]} LIMIT %s"
    contacts_params.append(limit)

    # --- Données ------------------------------------------------------------
    contacts_data = execute_query(base_contacts_query, tuple(contacts_params))

    if contacts_data:
        df_contacts = pd.DataFrame(contacts_data)

        # --- Actions en lot --------------------------------------------------
        st.subheader("⚡ Actions sur les Contacts")
        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            if st.button("✅ Marquer Vérifiés"):
                st.info("Sélectionnez d'abord les contacts")

        with col2:
            if st.button("📧 Valider Emails"):
                st.info("Validation email en développement")

        with col3:
            if st.button("🧹 Déduplication"):
                dedup_query = """
                WITH duplicates AS (
                    SELECT id, email, ROW_NUMBER() OVER (PARTITION BY email ORDER BY created_at ASC) as rn
                    FROM contacts WHERE deleted_at IS NULL AND email IS NOT NULL AND email <> ''
                )
                UPDATE contacts SET deleted_at = NOW() 
                WHERE id IN (SELECT id FROM duplicates WHERE rn > 1)
                """
                result = execute_query(dedup_query, fetch='none')
                if result:
                    st.success("✅ Doublons supprimés")
                    st.rerun()

        with col4:
            if st.button("📊 Export CSV"):
                csv_data = df_contacts.to_csv(index=False)
                st.download_button(
                    "⬇️ Télécharger CSV",
                    data=csv_data,
                    file_name=f"contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

        with col5:
            if st.button("📈 Export Excel"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_contacts.to_excel(writer, sheet_name='Contacts', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Contacts']
                    header_format = workbook.add_format({
                        'bold': True,
                        'bg_color': '#4F81BD',
                        'font_color': 'white'
                    })
                    for col_num, value in enumerate(df_contacts.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                st.download_button(
                    "⬇️ Télécharger Excel",
                    data=output.getvalue(),
                    file_name=f"contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        with col6:
            if st.button("📧 Export Emails"):
                emails_list = df_contacts['email'].dropna().tolist()
                emails_text = '\n'.join(emails_list)
                st.download_button(
                    "⬇️ Liste Emails",
                    data=emails_text,
                    file_name=f"emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )

        # --- Tableau principal ----------------------------------------------
        st.subheader(f"📋 Contacts ({len(df_contacts):,} résultats)")

        df_display = df_contacts.copy()
        df_display['name_display'] = df_display['name'].fillna('N/A').str[:30]
        df_display['email_display'] = df_display['email'].astype(str).str[:35]
        df_display['org_display'] = df_display['org'].fillna('N/A').str[:25]

        st.dataframe(
            df_display[[
                'verified_icon', 'name_display', 'email_display', 'org_display',
                'phone', 'country', 'theme', 'created_at'
            ]],
            hide_index=True,
            use_container_width=True,
            column_config={
                'verified_icon': st.column_config.TextColumn("✓", width=30),
                'name_display': st.column_config.TextColumn("Nom", width=120),
                'email_display': st.column_config.TextColumn("Email", width=140),
                'org_display': st.column_config.TextColumn("Organisation", width=120),
                'phone': st.column_config.TextColumn("Téléphone", width=120),
                'country': st.column_config.TextColumn("Pays", width=80),
                'theme': st.column_config.TextColumn("Thème", width=100),
                'created_at': st.column_config.DatetimeColumn("Créé le", width=110)
            }
        )

        # --- Statistiques de la sélection -----------------------------------
        st.subheader("📊 Statistiques de la Sélection")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            verified_count = len(df_contacts[df_contacts['verified'] == True])
            verified_rate = (verified_count / len(df_contacts) * 100) if len(df_contacts) > 0 else 0
            st.metric("Taux Vérification", f"{verified_rate:.1f}%")
        with col2:
            st.metric("Pays Uniques", df_contacts['country'].nunique())
        with col3:
            st.metric("Thèmes Uniques", df_contacts['theme'].nunique())
        with col4:
            has_phone = len(df_contacts[df_contacts['phone'].notna()])
            phone_rate = (has_phone / len(df_contacts) * 100) if len(df_contacts) > 0 else 0
            st.metric("Avec Téléphone", f"{phone_rate:.1f}%")

    else:
        st.info("🔍 Aucun contact trouvé avec ces critères de recherche")
        st.markdown("**Suggestions :**\n- Élargir la période de dates\n- Supprimer certains filtres\n- Vérifier l'orthographe des termes de recherche")


# ============================================================================
# PAGE PROXY MANAGEMENT AVANCÉE
# ============================================================================

def page_proxies():
    st.title("🌐 Proxy Management")

    proxy_stats_query = """
    SELECT 
        COUNT(*) as total_proxies,
        COUNT(*) FILTER (WHERE active = true) as active_proxies,
        COUNT(*) FILTER (WHERE last_test_status = 'success') as working_proxies,
        COUNT(*) FILTER (WHERE last_test_status = 'failed') as failed_proxies,
        AVG(response_time_ms) FILTER (WHERE response_time_ms > 0) as avg_response_time,
        AVG(success_rate) as avg_success_rate
    FROM proxies
    """
    proxy_stats = execute_query(proxy_stats_query, fetch='one')
    if proxy_stats:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.metric("📊 Total", proxy_stats['total_proxies'])
        with col2:
            st.metric("🟢 Actifs", proxy_stats['active_proxies'])
        with col3:
            st.metric("✅ Fonctionnels", proxy_stats['working_proxies'] or 0)
        with col4:
            st.metric("❌ En échec", proxy_stats['failed_proxies'] or 0)
        with col5:
            avg_time = proxy_stats['avg_response_time']
            st.metric("⏱️ Temps moy.", f"{avg_time:.0f}ms" if avg_time else "N/A")
        with col6:
            avg_rate = proxy_stats['avg_success_rate']
            st.metric("📈 Taux succès", f"{avg_rate:.1f}%" if avg_rate else "N/A")

    st.divider()

    st.subheader("➕ Ajouter des Proxies")
    tab1, tab2, tab3 = st.tabs(["📝 Proxy Unique", "📋 Import en Masse", "🔧 Import Avancé"])

    with tab1:
        with st.form("add_single_proxy"):
            col1, col2, col3 = st.columns(3)
            with col1:
                label = st.text_input("🏷️ Label", placeholder="Proxy France 1")
                scheme = st.selectbox("🔌 Type", ["http", "https", "socks5"])
                host = st.text_input("🌐 Host/IP", placeholder="1.2.3.4")
                port = st.number_input("📟 Port", min_value=1, max_value=65535, value=8080)
            with col2:
                username = st.text_input("👤 Username (optionnel)")
                password = st.text_input("🔒 Password (optionnel)", type="password")
                priority = st.slider("⭐ Priorité", 1, 100, 10)
                active = st.checkbox("✅ Actif", value=True)
            with col3:
                country_code = st.text_input("🏳️ Code Pays", placeholder="FR", max_chars=2)
                provider = st.text_input("🏢 Fournisseur", placeholder="ProxyProvider")
                cost_per_gb = st.number_input("💰 Coût/GB", min_value=0.0, value=0.0, step=0.01)

            submit_single = st.form_submit_button("➕ Ajouter Proxy", use_container_width=True, type="primary")

            if submit_single and host and port:
                upsert_query = """
                INSERT INTO proxies (
                    label, scheme, host, port, username, password, priority, active,
                    country_code, provider, cost_per_gb, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scheme, host, port, username) DO UPDATE SET
                    label = EXCLUDED.label,
                    priority = EXCLUDED.priority,
                    active = EXCLUDED.active,
                    country_code = COALESCE(EXCLUDED.country_code, proxies.country_code),
                    provider = COALESCE(EXCLUDED.provider, proxies.provider),
                    cost_per_gb = COALESCE(EXCLUDED.cost_per_gb, proxies.cost_per_gb),
                    updated_at = NOW()
                """
                params = (
                    label or f"{host}:{port}", scheme, host, port,
                    username or None, password or None, priority, active,
                    country_code.upper() or None, provider or None, cost_per_gb,
                    st.session_state.get('username', 'dashboard')
                )
                execute_query(upsert_query, params, fetch='none')
                st.success("✅ Proxy ajouté/mis à jour avec succès!")
                time.sleep(0.6)
                st.rerun()

    with tab2:
        st.info("💡 **Formats supportés:**\\n- `IP:PORT`\\n- `IP:PORT:USER:PASS`\\n- `SCHEME://IP:PORT`\\n- `SCHEME://USER:PASS@IP:PORT`")
        bulk_input = st.text_area(
            "Liste de proxies (un par ligne)",
            height=200,
            placeholder="""192.168.1.1:8080
192.168.1.2:8080:user:pass
http://proxy.example.com:3128
socks5://user:pass@proxy.example.com:1080"""
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            bulk_scheme = st.selectbox("🔌 Type par défaut", ["http", "https", "socks5"], key="bulk_scheme")
            bulk_priority = st.slider("⭐ Priorité par défaut", 1, 100, 10, key="bulk_priority")
        with col2:
            bulk_active = st.checkbox("✅ Tous actifs", value=True, key="bulk_active")
            auto_test = st.checkbox("🧪 Test automatique", value=True)
        with col3:
            bulk_country = st.text_input("🏳️ Code pays", placeholder="FR", key="bulk_country", max_chars=2)
            bulk_provider = st.text_input("🏢 Fournisseur", key="bulk_provider")

        if st.button("📥 Importer Proxies en Masse", use_container_width=True, type="primary"):
            if bulk_input.strip():
                import_results = import_bulk_proxies(
                    bulk_input, bulk_scheme, bulk_priority, bulk_active,
                    bulk_country, bulk_provider, auto_test
                )
                if import_results:
                    st.success(f"✅ {import_results['added']} proxies importés!")
                    if import_results['failed'] > 0:
                        st.warning(f"⚠️ {import_results['failed']} lignes ignorées")
                    if import_results['duplicates'] > 0:
                        st.info(f"ℹ️ {import_results['duplicates']} doublons mis à jour")
                    st.rerun()

    with tab3:
        st.subheader("🔧 Import depuis Fichier")
        uploaded_file = st.file_uploader(
            "Choisir un fichier proxy",
            type=['txt', 'csv'],
            help="Fichier texte ou CSV avec une liste de proxies"
        )
        if uploaded_file:
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            st.text_area("Aperçu du contenu", content[:500] + ("..." if len(content) > 500 else ""), height=150, disabled=True)
            if st.button("📥 Importer depuis Fichier"):
                results = import_bulk_proxies(content, "http", 10, True, "", "", False)
                if results:
                    st.success(f"✅ Import terminé: {results['added']} ajoutés, {results['failed']} échoués")
                    st.rerun()

    st.divider()

    st.subheader("⚡ Actions en Lot")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        if st.button("✅ Activer Tous", use_container_width=True):
            update_query = "UPDATE proxies SET active = true, updated_at = NOW()"
            if execute_query(update_query, fetch='none'):
                st.success("✅ Tous les proxies activés")
                st.rerun()

    with col2:
        if st.button("⏸️ Désactiver Tous", use_container_width=True):
            update_query = "UPDATE proxies SET active = false, updated_at = NOW()"
            if execute_query(update_query, fetch='none'):
                st.warning("⏸️ Tous les proxies désactivés")
                st.rerun()

    with col3:
        if st.button("🧪 Test Tous Actifs", use_container_width=True):
            with st.spinner("Test des proxies en cours..."):
                test_results = test_all_proxies()
                if test_results:
                    st.info(f"🧪 Test terminé: {test_results['tested']} proxies testés")
                    st.rerun()

    with col4:
        if st.button("🗑️ Suppr. Inactifs", use_container_width=True):
            delete_query = "DELETE FROM proxies WHERE active = false"
            if execute_query(delete_query, fetch='none'):
                st.success("🗑️ Proxies inactifs supprimés")
                st.rerun()

    with col5:
        if st.button("🔄 Reset Stats", use_container_width=True):
            reset_query = """
            UPDATE proxies SET 
                total_requests = 0, failed_requests = 0, success_rate = 1.0,
                response_time_ms = 0, last_test_at = NULL, last_test_status = NULL
            """
            if execute_query(reset_query, fetch='none'):
                st.success("🔄 Statistiques réinitialisées")
                st.rerun()

    with col6:
        if st.button("📊 Export Config", use_container_width=True):
            export_data = export_proxy_config()
            if export_data:
                st.download_button(
                    "⬇️ Télécharger",
                    data=export_data,
                    file_name=f"proxy_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )

    st.subheader("📊 Monitoring des Proxies")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Status", ["Tous", "Actifs", "Inactifs", "Fonctionnels", "En échec"])
    with col2:
        country_filter = st.selectbox("Pays", ["Tous"] + get_unique_proxy_countries())
    with col3:
        sort_proxy = st.selectbox("Trier par", ["Priorité", "Temps réponse", "Taux succès", "Dernière utilisation"])

    proxies_query = build_proxy_query(status_filter, country_filter, sort_proxy)
    proxies_data = execute_query(proxies_query)

    if proxies_data:
        df_proxies = pd.DataFrame(proxies_data)
        st.dataframe(
            df_proxies,
            hide_index=True,
            use_container_width=True,
            column_config={
                'status_icon': st.column_config.TextColumn("", width=40),
                'label': st.column_config.TextColumn("Label", width=120),
                'proxy_url': st.column_config.TextColumn("Proxy", width=220),
                'country_code': st.column_config.TextColumn("Pays", width=60),
                'response_time_ms': st.column_config.ProgressColumn("Temps (ms)", min_value=0, max_value=5000, format="%.0f ms"),
                'success_rate': st.column_config.ProgressColumn("Succès %", min_value=0.0, max_value=1.0, format="%.1%"),
                'total_requests': st.column_config.NumberColumn("Total Req.", width=90),
                'last_used_at': st.column_config.DatetimeColumn("Dernière util.", width=150)
            }
        )

        col1, col2 = st.columns(2)
        with col1:
            if 'response_time_ms' in df_proxies.columns:
                fig_response = px.histogram(
                    df_proxies[df_proxies['response_time_ms'] > 0],
                    x='response_time_ms',
                    title="Distribution des Temps de Réponse",
                    nbins=20
                )
                fig_response.update_layout(height=300)
                st.plotly_chart(fig_response, use_container_width=True)
        with col2:
            if 'country_code' in df_proxies.columns:
                country_counts = df_proxies['country_code'].fillna('N/A').value_counts()
                fig_countries = px.pie(
                    values=country_counts.values,
                    names=country_counts.index,
                    title="Répartition par Pays"
                )
                st.plotly_chart(fig_countries, use_container_width=True)
    else:
        st.info("Aucun proxy trouvé")

# ============================================================================
# FONCTIONS UTILITAIRES POUR PROXIES
# ============================================================================

def import_bulk_proxies(content: str, default_scheme: str, default_priority: int,
                        default_active: bool, default_country: str, default_provider: str,
                        auto_test: bool) -> dict:
    results = {'added': 0, 'failed': 0, 'duplicates': 0}

    for line_num, line in enumerate(content.strip().split('\\n'), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        try:
            proxy_info = parse_proxy_line(line, default_scheme)
            if not proxy_info:
                results['failed'] += 1
                continue

            upsert_query = """
            INSERT INTO proxies (
                label, scheme, host, port, username, password, priority, active,
                country_code, provider, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (scheme, host, port, username) DO UPDATE SET
                label = EXCLUDED.label,
                priority = EXCLUDED.priority,
                active = EXCLUDED.active,
                updated_at = NOW()
            RETURNING (xmax = 0) as inserted
            """
            params = (
                proxy_info.get('label', f"{proxy_info['host']}:{proxy_info['port']}"),
                proxy_info['scheme'], proxy_info['host'], proxy_info['port'],
                proxy_info.get('username'), proxy_info.get('password'),
                default_priority, default_active,
                default_country.upper() if default_country else None,
                default_provider or None,
                st.session_state.get('username', 'bulk_import')
            )
            result = execute_query(upsert_query, params, fetch='one')
            if result and result['inserted']:
                results['added'] += 1
            else:
                results['duplicates'] += 1

        except Exception as e:
            st.warning(f"Erreur ligne {line_num}: {line} - {e}")
            results['failed'] += 1

    if auto_test and results['added'] > 0:
        test_all_proxies()

    return results

def parse_proxy_line(line: str, default_scheme: str) -> Optional[Dict]:
    import re

    full_match = re.match(r'^(\\w+)://(?:([^:]+):([^@]+)@)?([^:]+):(\\d+)$', line)
    if full_match:
        scheme, username, password, host, port = full_match.groups()
        return {'scheme': scheme, 'host': host, 'port': int(port), 'username': username, 'password': password}

    parts = line.split(':')
    if len(parts) >= 2:
        try:
            host = parts[0]
            port = int(parts[1])
            username = parts[2] if len(parts) > 2 else None
            password = parts[3] if len(parts) > 3 else None
            return {'scheme': default_scheme, 'host': host, 'port': port, 'username': username, 'password': password}
        except ValueError:
            return None

    return None

def test_all_proxies() -> dict:
    import requests
    from concurrent.futures import ThreadPoolExecutor

    proxies_query = "SELECT id, scheme, host, port, username, password FROM proxies WHERE active = true"
    proxies = execute_query(proxies_query)

    if not proxies:
        return {'tested': 0}

    results = {'tested': 0, 'working': 0, 'failed': 0}

    def test_single_proxy(proxy):
        proxy_id = proxy['id']
        proxy_url = build_proxy_url(proxy)
        try:
            start_time = time.time()
            response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=10
            )
            response_time = int((time.time() - start_time) * 1000)
            if response.status_code == 200:
                update_query = """
                UPDATE proxies SET 
                    last_test_at = NOW(),
                    last_test_status = 'success',
                    response_time_ms = %s,
                    success_rate = CASE 
                        WHEN total_requests = 0 THEN 1.0
                        ELSE (total_requests - failed_requests + 1.0) / (total_requests + 1.0)
                    END,
                    total_requests = total_requests + 1
                WHERE id = %s
                """
                execute_query(update_query, (response_time, proxy_id), fetch='none')
                results['working'] += 1
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception:
            update_query = """
            UPDATE proxies SET 
                last_test_at = NOW(),
                last_test_status = 'failed',
                success_rate = CASE 
                    WHEN total_requests = 0 THEN 0.0
                    ELSE (total_requests - failed_requests) / (total_requests + 1.0)
                END,
                total_requests = total_requests + 1,
                failed_requests = failed_requests + 1
            WHERE id = %s
            """
            execute_query(update_query, (proxy_id,), fetch='none')
            results['failed'] += 1
        results['tested'] += 1

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(test_single_proxy, proxies)

    return results

def build_proxy_url(proxy: dict) -> str:
    scheme = proxy['scheme']
    host = proxy['host']
    port = proxy['port']
    username = proxy.get('username')
    password = proxy.get('password')
    if username and password:
        return f"{scheme}://{username}:{password}@{host}:{port}"
    else:
        return f"{scheme}://{host}:{port}"

def get_unique_proxy_countries() -> List[str]:
    query = "SELECT DISTINCT country_code FROM proxies WHERE country_code IS NOT NULL ORDER BY country_code"
    result = execute_query(query)
    return [r['country_code'] for r in (result or [])]

def build_proxy_query(status_filter: str, country_filter: str, sort_option: str) -> str:
    base_query = """
    SELECT 
        id, label, scheme, host, port, username, active, priority,
        COALESCE(response_time_ms,0) as response_time_ms,
        COALESCE(success_rate,0.0) as success_rate,
        COALESCE(total_requests,0) as total_requests,
        COALESCE(failed_requests,0) as failed_requests,
        last_used_at, last_test_at, last_test_status, country_code,
        provider, created_at,
        CASE 
            WHEN active = false THEN '⏸️'
            WHEN last_test_status = 'success' THEN '🟢'
            WHEN last_test_status = 'failed' THEN '🔴'
            ELSE '⚪'
        END as status_icon,
        CASE 
            WHEN username IS NOT NULL THEN CONCAT(scheme, '://', username, ':***@', host, ':', port)
            ELSE CONCAT(scheme, '://', host, ':', port)
        END as proxy_url
    FROM proxies 
    WHERE 1=1
    """

    if status_filter == "Actifs":
        base_query += " AND active = true"
    elif status_filter == "Inactifs":
        base_query += " AND active = false"
    elif status_filter == "Fonctionnels":
        base_query += " AND last_test_status = 'success'"
    elif status_filter == "En échec":
        base_query += " AND last_test_status = 'failed'"

    if country_filter != "Tous":
        base_query += f" AND country_code = '{country_filter}'"

    if sort_option == "Priorité":
        base_query += " ORDER BY active DESC, priority ASC"
    elif sort_option == "Temps réponse":
        base_query += " ORDER BY response_time_ms ASC NULLS LAST"
    elif sort_option == "Taux succès":
        base_query += " ORDER BY success_rate DESC"
    elif sort_option == "Dernière utilisation":
        base_query += " ORDER BY last_used_at DESC NULLS LAST"

    return base_query

def export_proxy_config() -> str:
    query = """
    SELECT scheme, host, port, username, password, active, priority, country_code, provider
    FROM proxies 
    ORDER BY priority, id
    """
    proxies = execute_query(query)
    if proxies:
        config = {
            'proxies': proxies,
            'export_date': datetime.now().isoformat(),
            'total_count': len(proxies)
        }
        return json.dumps(config, indent=2, default=str)
    return json.dumps({'proxies': [], 'export_date': datetime.now().isoformat()})

# ============================================================================
# POINT D'ENTRÉE PRINCIPAL
# ============================================================================

def main():
    if not require_authentication():
        return

    ok_schema = ensure_schema()
    if not ok_schema:
        st.warning("⚠️ Impossible de vérifier le schéma de la base. Certaines fonctionnalités peuvent être limitées.")

    current_page = render_sidebar()

    try:
        if current_page == "dashboard":
            page_dashboard()
        elif current_page == "jobs":
            page_jobs()
        elif current_page == "contacts":
            page_contacts()
        elif current_page == "proxies":
            page_proxies()
        elif current_page == "sessions":
            st.title("🗂️ Session Management")
            st.info("Upload, activation et gestion des storage_state Playwright.")
        elif current_page == "analytics":
            st.title("📈 Analytics")
            st.info("Graphiques avancés et insights.")
        elif current_page == "settings":
            st.title("⚙️ System Settings")
            st.info("Configuration système, warm-up, scheduler.")
        elif current_page == "monitor":
            st.title("🔧 System Monitor")
            st.info("Logs, métriques, health checks.")
        else:
            st.error("Page non trouvée")

    except Exception as e:
        st.error(f"Erreur lors du chargement de la page: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
