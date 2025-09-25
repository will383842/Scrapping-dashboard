#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import re
from datetime import datetime
from typing import List, Any, Optional
from contextlib import contextmanager

import streamlit as st
st.set_page_config(page_title="Scraper Dashboard", page_icon="", layout="wide", initial_sidebar_state="expanded")
import pandas as pd

# Liens de pages (chemins ASCII, sans emoji dans le nom de fichier)
st.sidebar.page_link("pages/10_Mode_d_emploi.py", label="❓ Mode d’emploi / User Manual")
st.sidebar.page_link("pages/20_Utilisation.py", label="📘 Utilisation / Usage")

# ──────────────────────────────────────────────────────────────────────────────
# Utils
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_countries_from_config() -> List[str]:
    """Charge la liste des pays depuis config/countries.json (197+)."""
    try:
        cfg = os.path.join(os.path.dirname(__file__), "..", "config", "countries.json")
        with open(cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        countries = list(dict.fromkeys(data.get("countries", [])))
        return sorted(countries)
    except Exception:
        return []

def validate_url(url: str) -> bool:
    if not url:
        return False
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,63}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    return bool(url_pattern.match(url))

def parse_keywords(keywords_text: str) -> List[str]:
    if not keywords_text:
        return []
    parts = re.split(r'[,;\n]+', keywords_text.strip())
    return [p.strip() for p in parts if p.strip()]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers d’affichage sûrs
# ──────────────────────────────────────────────────────────────────────────────

def _to_dataframe(data: Any) -> pd.DataFrame:
    """
    Convertit de façon robuste un objet (fonction, curseur DB, Result, liste, dict…)
    en pandas.DataFrame pour Streamlit.
    """
    # 1) Si c'est une fonction, l'appeler
    if callable(data):
        data = data()

    # 2) Curseur DB-API (psycopg2…)
    if hasattr(data, "fetchall"):
        try:
            rows = data.fetchall()
        except Exception:
            rows = []
        desc = getattr(data, "description", None)
        if callable(desc):
            try:
                desc = desc()
            except Exception:
                desc = None
        cols = None
        try:
            cols = [d[0] for d in desc] if desc else None
        except Exception:
            cols = None
        try:
            return pd.DataFrame(rows, columns=cols)
        except Exception:
            return pd.DataFrame([])

    # 3) SQLAlchemy 2.x Result (si présent)
    try:
        from sqlalchemy.engine import Result
        if isinstance(data, Result):
            try:
                rows = [dict(r._mapping) for r in data]
                return pd.DataFrame(rows)
            except Exception:
                return pd.DataFrame([])
    except Exception:
        pass

    # 4) Fallback
    try:
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame([])

def _safe_dataframe(obj: Any, *, empty_msg: Optional[str] = "Aucune donnée à afficher."):
    """Affiche un dataframe sans planter l'app si l'objet est inattendu."""
    try:
        df = _to_dataframe(obj)
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            if empty_msg:
                st.info(empty_msg)
    except Exception as e:
        st.error(f"Erreur lors de l'affichage des données : {e}")

# ──────────────────────────────────────────────────────────────────────────────
# DB (pool)
# ──────────────────────────────────────────────────────────────────────────────
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),
    'password': os.getenv("POSTGRES_PASSWORD", "scraper_admin"),
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "30")),
    'application_name': 'dashboard_streamlit'
}

_db_pool = None

@st.cache_resource
def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=int(os.getenv("CONNECTION_POOL_SIZE", "10")),
            **DB_CONFIG
        )
    return _db_pool

@contextmanager
def get_db_connection():
    pool = get_db_pool()
    if not pool:
        raise RuntimeError("Pool DB indisponible")
    conn = None
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn and pool:
            try:
                pool.putconn(conn)
            except:
                pass

def execute_query(query: str, params: tuple = None, fetch: str = 'all'):
    """
    Exécute une requête et renvoie:
      - 'none' -> True/False (succès)
      - 'one'  -> dict | None
      - 'all'  -> List[dict] | None
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                if fetch == 'none':
                    return True
                if fetch == 'one':
                    return cur.fetchone()
                return cur.fetchall()
    except Exception as e:
        st.error(f"Erreur base de données: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# i18n
# ──────────────────────────────────────────────────────────────────────────────

LANGUAGES = {'fr': 'Français', 'en': 'English'}

TRANSLATIONS = {
    'fr': {
        'app_title': '🕷️ Scraper Pro Dashboard',
        'login_title': 'Connexion',
        'username': 'Nom d\'utilisateur',
        'password': 'Mot de passe',
        'login_button': 'Se connecter',
        'logout_button': 'Déconnexion',
        'dashboard': '📊 Tableau de bord',
        'jobs_manager': '🎯 Gestionnaire de Jobs',
        'contacts_explorer': '📇 Explorateur de Contacts',
        'proxy_management': '🌐 Gestion des Proxies',
        'settings': '⚙️ Paramètres',
        'create_job': 'Créer un Job',
        'job_url': 'URLs à analyser (une par ligne)',
        'job_country': 'Pays cibles',
        'job_language': 'Langue',
        'custom_keywords': 'Mots-clés personnalisés',
        'match_mode': 'Mode de correspondance',
        'min_matches': 'Nombre minimum de correspondances',
        'match_mode_any': 'Au moins un mot-clé',
        'match_mode_all': 'Tous les mots-clés',
        'use_javascript': 'Utiliser JavaScript (Playwright)',
        'max_pages': 'Pages maximum par domaine',
        'priority': 'Priorité',
        'create_job_button': '🚀 LANCER LE SCRAPING',
        'test_url_button': 'Tester URL',
        'status': 'Statut',
        'pending_jobs': 'Jobs en attente',
        'active_jobs': 'Jobs actifs',
        'completed_jobs': 'Jobs terminés',
        'total_contacts': 'Total contacts',
        'active_proxies': 'Proxies actifs',
        'add_proxy': 'Ajouter un Proxy',
        'proxy_host': 'Adresse IP/Host',
        'proxy_port': 'Port',
        'proxy_username': 'Nom d\'utilisateur',
        'proxy_password': 'Mot de passe',
        'proxy_type': 'Type de proxy',
        'add_proxy_button': 'Ajouter le Proxy',
        'test_proxy_button': 'Tester le Proxy',
        'no_proxies_warning': '⚠️ Aucun proxy configuré ! Le scraping ne fonctionnera pas.',
        'configure_proxies': 'Configurer des Proxies',
        'system_status': 'État du système',
        'system_healthy': '🟢 Système opérationnel',
        'system_error': '🔴 Problème système'
    },
    'en': {
        'app_title': '🕷️ Scraper Pro Dashboard',
        'login_title': 'Login',
        'username': 'Username',
        'password': 'Password',
        'login_button': 'Login',
        'logout_button': 'Logout',
        'dashboard': '📊 Dashboard',
        'jobs_manager': '🎯 Jobs Manager',
        'contacts_explorer': '📇 Contacts Explorer',
        'proxy_management': '🌐 Proxy Management',
        'settings': '⚙️ Settings',
        'create_job': 'Create Job',
        'job_url': 'URLs to analyze (one per line)',
        'job_country': 'Target countries',
        'job_language': 'Language',
        'custom_keywords': 'Custom keywords',
        'match_mode': 'Match mode',
        'min_matches': 'Minimum matches',
        'match_mode_any': 'At least one keyword',
        'match_mode_all': 'All keywords',
        'use_javascript': 'Use JavaScript (Playwright)',
        'max_pages': 'Max pages per domain',
        'priority': 'Priority',
        'create_job_button': '🚀 START SCRAPING',
        'test_url_button': 'Test URL',
        'status': 'Status',
        'pending_jobs': 'Pending jobs',
        'active_jobs': 'Active jobs',
        'completed_jobs': 'Completed jobs',
        'total_contacts': 'Total contacts',
        'active_proxies': 'Active proxies',
        'add_proxy': 'Add Proxy',
        'proxy_host': 'IP/Host',
        'proxy_port': 'Port',
        'proxy_username': 'Username',
        'proxy_password': 'Password',
        'proxy_type': 'Proxy type',
        'add_proxy_button': 'Add Proxy',
        'test_proxy_button': 'Test Proxy',
        'no_proxies_warning': '⚠️ No proxies configured! Scraping will not work.',
        'configure_proxies': 'Configure Proxies',
        'system_status': 'System status',
        'system_healthy': '🟢 System operational',
        'system_error': '🔴 System problem'
    }
}

def get_lang():
    if 'language' not in st.session_state:
        st.session_state.language = 'fr'
    return st.session_state.language

def t(key: str) -> str:
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, key)

# ──────────────────────────────────────────────────────────────────────────────
# Style global
# ──────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.main .block-container { padding: 1rem; max-width: 1200px; }
[data-testid="metric-container"] {
  background: #fff; border: 1px solid #dee2e6; border-radius: 8px;
  padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,.06);
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  color: #2E7BF6; font-size: 2rem; font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────────────────────────

def require_authentication() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title(t('app_title'))
    with st.container():
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.subheader(t('login_title'))
            with st.form("login_form"):
                username = st.text_input(t('username'), value="admin")
                password = st.text_input(t('password'), type="password")
                if st.form_submit_button(t('login_button'), use_container_width=True, type="primary"):
                    if (username == os.getenv("DASHBOARD_USERNAME", "admin") and
                        password == os.getenv("DASHBOARD_PASSWORD", "admin123")):
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username
                        st.success("✅ Connexion réussie!")
                        time.sleep(0.6)
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
    return False

# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    with st.sidebar:
        st.title("🕷️ Scraper Pro")
        c1, c2 = st.columns(2)
        with c1:
            selected_lang = st.selectbox(
                "🌐", options=list(LANGUAGES.keys()),
                format_func=lambda x: LANGUAGES[x],
                index=list(LANGUAGES.keys()).index(get_lang()),
                key="language_selector"
            )
            if selected_lang != get_lang():
                st.session_state.language = selected_lang
                st.rerun()
        with c2:
            if st.button(t('logout_button')):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()

        st.divider()
        pages = {
            t('dashboard'): "dashboard",
            t('jobs_manager'): "jobs",
            t('contacts_explorer'): "contacts",
            t('proxy_management'): "proxies",
            t('settings'): "settings"
        }
        keys = list(pages.keys())
        default_index = 0
        if 'pending_nav' in st.session_state:
            target = st.session_state.pop('pending_nav')
            if target in keys:
                default_index = keys.index(target)
        selected = st.radio("📋 Navigation", keys, index=default_index, key="nav_radio")
        st.divider()

        # État système (simple ping DB)
        ok = False
        try:
            r = execute_query("SELECT 1 as ok", fetch='one')
            ok = bool(r and r.get('ok') == 1)
        except Exception as e:
            st.error(f"Erreur système: {e}")

        if ok:
            st.success(t('system_healthy'))
        else:
            st.error(t('system_error'))

        return pages[selected]

# ──────────────────────────────────────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────────────────────────────────────

def page_dashboard():
    st.title(t('dashboard'))
    col1, col2, col3, col4, col5 = st.columns(5)
    try:
        m = execute_query("""
            SELECT 
              (SELECT COUNT(*) FROM queue  WHERE status='pending'     AND deleted_at IS NULL) AS pending_jobs,
              (SELECT COUNT(*) FROM queue  WHERE status='in_progress' AND deleted_at IS NULL) AS active_jobs,
              (SELECT COUNT(*) FROM queue  WHERE status='done' AND DATE(updated_at)=CURRENT_DATE AND deleted_at IS NULL) AS completed_jobs,
              (SELECT COUNT(*) FROM contacts WHERE DATE(created_at)=CURRENT_DATE AND deleted_at IS NULL) AS total_contacts,
              (SELECT COUNT(*) FROM proxies WHERE active=true) AS active_proxies
        """, fetch='one') or {}
        col1.metric(t('pending_jobs'),  m.get('pending_jobs', 0))
        col2.metric(t('active_jobs'),   m.get('active_jobs', 0))
        col3.metric(t('completed_jobs'),m.get('completed_jobs', 0))
        col4.metric(t('total_contacts'),m.get('total_contacts', 0))
        col5.metric(t('active_proxies'),m.get('active_proxies', 0))
        if m.get('active_proxies', 0) == 0:
            st.error(t('no_proxies_warning'))
            if st.button(t('configure_proxies'), type="primary"):
                st.session_state['pending_nav'] = t('proxy_management')
                st.rerun()
    except Exception as e:
        st.error(f"Erreur métriques: {e}")

def page_jobs():
    st.title(t('jobs_manager'))
    with st.expander(t('create_job'), expanded=True):
        with st.form("job_form", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                urls_text = st.text_area(
                    t('job_url'),
                    placeholder="https://example.com\nhttps://second-site.com",
                    help="Une URL par ligne"
                )
                urls = [u.strip() for u in urls_text.splitlines() if u.strip()]

                all_countries = load_countries_from_config()
                country_options = ['(Tous les pays)'] + all_countries
                selected_countries = st.multiselect(
                    t('job_country'),
                    country_options,
                    default=['(Tous les pays)'],
                    help="Sélectionnez un ou plusieurs pays (ou '(Tous les pays)')"
                )
                countries = [None] if '(Tous les pays)' in selected_countries or not selected_countries else selected_countries

                language = st.selectbox(t('job_language'), options=['auto','fr','en'], index=0)

            with col2:
                keywords_text = st.text_area(
                    t('custom_keywords'),
                    placeholder="visa\npermis de travail\nimmigration",
                    help="Un mot-clé par ligne (ou séparés par virgules/points-virgules)"
                )
                match_mode = st.selectbox(
                    t('match_mode'),
                    options=[('any', t('match_mode_any')), ('all', t('match_mode_all'))],
                    index=0, format_func=lambda x: x[1]
                )[0]
                min_matches = st.number_input(t('min_matches'), min_value=1, max_value=20, value=1, step=1)
                use_js = st.checkbox(t('use_javascript'), value=True)
                max_pages = st.number_input(t('max_pages'), min_value=1, max_value=200, value=10, step=1)

            c1, c2 = st.columns(2)
            with c1:
                test_button = st.form_submit_button(t('test_url_button'))
            with c2:
                create_button = st.form_submit_button(t('create_job_button'), type="primary")

        if test_button:
            if not urls or not all(validate_url(u) for u in urls):
                st.error("❌ Veuillez entrer au moins une URL valide (une par ligne).")
            else:
                st.success("✅ URLs valides.")

        if create_button:
            if not urls or not all(validate_url(u) for u in urls):
                st.error("❌ Veuillez entrer au moins une URL valide (une par ligne).")
                return
            keywords = parse_keywords(keywords_text)
            if not keywords:
                st.error("❌ Veuillez saisir au moins un mot-clé.")
                return

            proxy_count = execute_query("SELECT COUNT(*) AS c FROM proxies WHERE active = true", fetch='one')
            if not proxy_count or proxy_count.get('c', 0) == 0:
                st.error("❌ Aucun proxy configuré ! Configurez des proxies avant de lancer un job.")
                return

            created = 0
            for u in urls:
                for c in countries:
                    ok = execute_query("""
                        INSERT INTO queue (
                          url, country_filter, lang_filter, custom_keywords,
                          match_mode, min_matches, use_js, max_pages_per_domain,
                          status, created_by, created_at
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s, NOW())
                    """, (
                        u, c, (None if language=='auto' else language),
                        json.dumps(keywords),
                        match_mode, int(min_matches), bool(use_js), int(max_pages),
                        st.session_state.get('username', 'dashboard')
                    ), fetch='none')
                    if ok:
                        created += 1
            st.success(f"🚀 {created} job(s) ajoutés à la file !")
            st.info(f"Config: {len(keywords)} mots-clés • mode '{match_mode}' • min {min_matches}")
            st.balloons()
            time.sleep(0.6)
            st.rerun()

    st.subheader("Jobs récents")
    try:
        rows = execute_query("""
          SELECT id, url, status, custom_keywords, match_mode, created_at, updated_at,
                 CASE 
                   WHEN status='done'        THEN '✅'
                   WHEN status='failed'      THEN '❌'
                   WHEN status='in_progress' THEN '⚡'
                   ELSE '⏳'
                 END as status_icon
          FROM queue
          WHERE deleted_at IS NULL
          ORDER BY created_at DESC
          LIMIT 20
        """) or []
        df = _to_dataframe(rows)
        if df is not None and not df.empty:
            df['url_short'] = df['url'].astype(str).str.slice(0, 50) + '...'
            def fmt_kw(v):
                try:
                    lst = v if isinstance(v, list) else json.loads(v) if v else []
                except Exception:
                    lst = []
                return ', '.join(lst[:3]) + (f" (+{len(lst)-3})" if len(lst) > 3 else '') if lst else '—'
            df['keywords_display'] = df['custom_keywords'].apply(fmt_kw)

            st.dataframe(
                df[["status_icon", "id", "url_short", "keywords_display", "match_mode", "status", "created_at"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "status_icon": st.column_config.TextColumn("", width=40),
                    "id": st.column_config.NumberColumn("ID", width=60),
                    "url_short": st.column_config.TextColumn("URL"),
                    "keywords_display": st.column_config.TextColumn("Mots-clés", width=240),
                    "match_mode": st.column_config.TextColumn("Mode", width=110),
                    "status": st.column_config.TextColumn("Statut", width=100),
                    "created_at": st.column_config.DatetimeColumn("Créé le", width=160)
                }
            )
        else:
            st.info("Aucun job trouvé. Créez votre premier job ci-dessus !")
    except Exception as e:
        st.error(f"Erreur chargement jobs: {e}")

def page_proxies():
    st.title(t('proxy_management'))
    with st.expander(t('add_proxy'), expanded=True):
        st.info("💡 Les proxies réduisent les blocages.")
        with st.form("proxy_form"):
            col1, col2 = st.columns(2)
            with col1:
                proxy_type = st.selectbox(t('proxy_type'), options=["http", "https", "socks5"])
                host = st.text_input(t('proxy_host'), placeholder="192.168.1.100 ou proxy.example.com")
                port = st.number_input(t('proxy_port'), min_value=1, max_value=65535, value=8080)
            with col2:
                username = st.text_input(t('proxy_username'))
                password = st.text_input(t('proxy_password'), type="password")
                active = st.checkbox("Activer immédiatement", value=True)
            c1, c2 = st.columns(2)
            with c1:
                test_button = st.form_submit_button(t('test_proxy_button'))
            with c2:
                add_button = st.form_submit_button(t('add_proxy_button'), type="primary")

        if add_button and host and port:
            try:
                ok = execute_query("""
                  INSERT INTO proxies (scheme, host, port, username, password, active, created_by)
                  VALUES (%s,%s,%s,%s,%s,%s,%s)
                  ON CONFLICT (scheme, host, port, COALESCE(username,'')) DO UPDATE
                  SET active = EXCLUDED.active, updated_at = NOW()
                """, (proxy_type, host, port,
                      username or None, password or None, active,
                      st.session_state.get('username', 'dashboard')),
                fetch='none')
                if ok:
                    st.success("✅ Proxy ajouté/mis à jour.")
                    st.rerun()
                else:
                    st.error("❌ Erreur lors de l'ajout.")
            except Exception as e:
                st.error(f"❌ {e}")

    st.subheader("Proxies configurés")
    try:
        rows = execute_query("""
          SELECT id, scheme, host, port, username, active,
                 CASE WHEN active THEN '🟢' ELSE '🔴' END AS status_icon,
                 CASE WHEN username IS NOT NULL
                      THEN CONCAT(scheme, '://', username, ':***@', host, ':', port)
                      ELSE CONCAT(scheme, '://', host, ':', port)
                 END AS proxy_url,
                 created_at
          FROM proxies
          ORDER BY active DESC, created_at DESC
        """) or []
        df = _to_dataframe(rows)
        if df is not None and not df.empty:
            st.dataframe(
                df[["status_icon", "proxy_url", "active", "created_at"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "status_icon": st.column_config.TextColumn("État", width=50),
                    "proxy_url":   st.column_config.TextColumn("Configuration Proxy"),
                    "active":      st.column_config.CheckboxColumn("Actif", width=70),
                    "created_at":  st.column_config.DatetimeColumn("Ajouté le", width=160)
                }
            )
            st.success(f"✅ {len(df)} proxy(s) configuré(s)")
        else:
            st.warning("⚠️ Aucun proxy configuré.")
    except Exception as e:
        st.error(f"Erreur proxies: {e}")

def page_contacts():
    st.title(t('contacts_explorer'))
    try:
        stats = execute_query("""
          SELECT 
            COUNT(*)                                            AS total_contacts,
            COUNT(*) FILTER (WHERE DATE(created_at)=CURRENT_DATE) AS today_contacts,
            COUNT(*) FILTER (WHERE verified=true)               AS verified_contacts,
            COUNT(DISTINCT country)                             AS unique_countries
          FROM contacts WHERE deleted_at IS NULL
        """, fetch='one') or {}
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📊 Total", f"{stats.get('total_contacts', 0):,}")
        c2.metric("📈 Aujourd'hui", stats.get('today_contacts', 0))
        c3.metric("✅ Vérifiés", stats.get('verified_contacts', 0))
        c4.metric("🌍 Pays", stats.get('unique_countries', 0))
    except Exception as e:
        st.error(f"Erreur stats: {e}")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        search_text = st.text_input("🔍 Rechercher", placeholder="Nom, email, organisation…")
    with col2:
        try:
            countries = execute_query("""
              SELECT DISTINCT country 
              FROM contacts 
              WHERE country IS NOT NULL AND deleted_at IS NULL 
              ORDER BY country
            """) or []
            options = ["Tous"] + [c['country'] for c in countries]
            selected_country = st.selectbox("🌍 Pays", options)
        except Exception:
            selected_country = "Tous"

    try:
        where = ["deleted_at IS NULL"]
        params = []
        if search_text:
            where.append("(name ILIKE %s OR email ILIKE %s OR org ILIKE %s)")
            like = f"%{search_text}%"
            params += [like, like, like]
        if selected_country != "Tous":
            where.append("country = %s")
            params.append(selected_country)

        sql = f"""
          SELECT 
            name, email, org, phone, country,
            COALESCE(verified,false) AS verified, created_at,
            CASE WHEN COALESCE(verified,false) THEN '✅' ELSE '⏳' END AS verified_icon
          FROM contacts
          WHERE {' AND '.join(where)}
          ORDER BY created_at DESC
          LIMIT 500
        """
        rows = execute_query(sql, tuple(params)) or []
        df = _to_dataframe(rows)

        a, b, c = st.columns(3)
        with a:
            if df is not None and not df.empty:
                csv = df.to_csv(index=False)
                st.download_button(
                    "⬇️ Export CSV", data=csv,
                    file_name=f"contacts_{datetime.now():%Y%m%d_%H%M%S}.csv",
                    mime="text/csv", use_container_width=True
                )
            else:
                st.button("⬇️ Export CSV", disabled=True, use_container_width=True)
        with b:
            if df is not None and not df.empty:
                emails = df['email'].dropna().tolist()
                st.download_button(
                    "⬇️ Export Emails", data="\n".join(emails),
                    file_name=f"emails_{datetime.now():%Y%m%d_%H%M%S}.txt",
                    mime="text/plain", use_container_width=True
                )
            else:
                st.button("⬇️ Export Emails", disabled=True, use_container_width=True)
        with c:
            st.metric("Résultats", 0 if df is None else len(df))

        if df is not None and not df.empty:
            st.dataframe(
                df[["verified_icon", "name", "email", "org", "phone", "country", "created_at"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "verified_icon": st.column_config.TextColumn("✓", width=30),
                    "name":        st.column_config.TextColumn("Nom", width=150),
                    "email":       st.column_config.TextColumn("Email", width=220),
                    "org":         st.column_config.TextColumn("Organisation", width=160),
                    "phone":       st.column_config.TextColumn("Téléphone", width=120),
                    "country":     st.column_config.TextColumn("Pays", width=90),
                    "created_at":  st.column_config.DatetimeColumn("Ajouté le", width=160)
                }
            )
        else:
            st.info("🔍 Aucun contact trouvé avec ces critères.")
    except Exception as e:
        st.error(f"Erreur chargement contacts: {e}")

def page_settings():
    st.title(t('settings'))
    st.subheader("⚙️ Configuration Générale")

    try:
        from scraper.utils.proxy_warmup import ProxyWarmer
        if st.button("🔥 Lancer le warm-up des proxies"):
            ProxyWarmer().warm_all_proxies()
            st.success("Warm-up lancé")
    except Exception as e:
        st.info("(Warm-up indisponible) " + str(e))

    c1, c2 = st.columns(2)
    with c1:
        st.info("**Variables d'environnement actuelles :**")
        env_vars = {
            'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'Non défini'),
            'POSTGRES_DB':   os.getenv('POSTGRES_DB',   'Non défini'),
            'POSTGRES_USER': os.getenv('POSTGRES_USER', 'Non défini'),
            'DASHBOARD_USERNAME': os.getenv('DASHBOARD_USERNAME', 'Non défini'),
        }
        for k, v in env_vars.items():
            st.text(f"{k}: {v}")

    with c2:
        st.info("**Statistiques système :**")
        try:
            s = execute_query("""
              SELECT 
                (SELECT COUNT(*) FROM queue    WHERE deleted_at IS NULL) AS total_jobs,
                (SELECT COUNT(*) FROM contacts WHERE deleted_at IS NULL) AS total_contacts,
                (SELECT COUNT(*) FROM proxies) AS total_proxies,
                (SELECT MAX(created_at) FROM queue WHERE deleted_at IS NULL) AS last_job_created
            """, fetch='one') or {}
            st.text(f"Jobs total: {s.get('total_jobs', 0)}")
            st.text(f"Contacts total: {s.get('total_contacts', 0)}")
            st.text(f"Proxies total: {s.get('total_proxies', 0)}")
            st.text(f"Dernier job: {s.get('last_job_created') or 'Aucun'}")
        except Exception as e:
            st.error(f"Erreur stats: {e}")

    st.divider()
    st.subheader("🧹 Maintenance")
    m1, m2, m3 = st.columns(3)
    with m1:
        if st.button("🗑️ Nettoyer les anciens jobs", use_container_width=True):
            try:
                ok = execute_query("""
                  UPDATE queue SET deleted_at = NOW()
                  WHERE status IN ('done','failed')
                  AND updated_at < NOW() - INTERVAL '7 days'
                  AND deleted_at IS NULL
                """, fetch='none')
                st.success("✅ Anciens jobs supprimés" if ok else "ℹ️ Aucun ancien job.")
            except Exception as e:
                st.error(f"❌ {e}")
    with m2:
        if st.button("📊 Optimiser la base", use_container_width=True):
            try:
                execute_query("VACUUM ANALYZE", fetch='none')
                st.success("✅ Base optimisée")
            except Exception as e:
                st.error(f"❌ {e}")
    with m3:
        if st.button("🔄 Redémarrer services", use_container_width=True):
            st.warning("⚠️ Cette action nécessite un accès administrateur au serveur")
            st.code("docker compose restart")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    try:
        if not require_authentication():
            return
        page = render_sidebar()
        if page == "dashboard":
            page_dashboard()
        elif page == "jobs":
            page_jobs()
        elif page == "contacts":
            page_contacts()
        elif page == "proxies":
            page_proxies()
        elif page == "settings":
            page_settings()
        else:
            st.error("Page non trouvée")
    except Exception as e:
        st.error(f"Erreur critique dans l'application: {e}")
        st.exception(e)
        if st.button("🔄 Recharger l'application"):
            st.rerun()

if __name__ == "__main__":
    main()
