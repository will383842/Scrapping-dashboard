#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import re
import io
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Base de données avec pool de connexions
import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

# ============================================================================
# CONFIGURATION MULTILINGUE - CORRIGÉE
# ============================================================================

# Langues supportées
LANGUAGES = {
    'fr': 'Français',
    'en': 'English'
}

# Traductions
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
        'job_url': 'URL à analyser',
        'job_country': 'Pays cible',
        'job_theme': 'Thème de recherche',
        'job_language': 'Langue',
        'use_javascript': 'Utiliser JavaScript',
        'max_pages': 'Pages maximum',
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
        'system_warning': '🟡 Attention requise',
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
        'job_url': 'URL to analyze',
        'job_country': 'Target country',
        'job_theme': 'Search theme',
        'job_language': 'Language',
        'use_javascript': 'Use JavaScript',
        'max_pages': 'Maximum pages',
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
        'proxy_host': 'IP Address/Host',
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
        'system_warning': '🟡 Attention required',
        'system_error': '🔴 System problem'
    }
}

# ============================================================================
# CONFIGURATION STREAMLIT - CORRIGÉE
# ============================================================================

st.set_page_config(
    page_title="🕷️ Scraper Pro Dashboard",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS amélioré et corrigé
st.markdown("""
<style>
    :root {
        --primary-color: #2E7BF6;
        --success-color: #28a745;
        --warning-color: #ffc107;
        --danger-color: #dc3545;
        --dark-color: #343a40;
        --light-color: #f8f9fa;
        --border-color: #dee2e6;
    }
    
    .main .block-container {
        padding: 1rem;
        max-width: 1200px;
    }
    
    [data-testid="metric-container"] {
        background: white;
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: var(--primary-color);
        font-size: 2rem;
        font-weight: bold;
    }
    
    .stButton > button[kind="primary"] {
        background-color: var(--success-color);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        font-size: 1.1rem;
    }
    
    .stButton > button[kind="primary"]:hover {
        background-color: #218838;
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# GESTION BASE DE DONNÉES ROBUSTE - CORRIGÉE
# ============================================================================

# Configuration de la base de données CORRIGÉE
DB_CONFIG = {
    'host': os.getenv("POSTGRES_HOST", "db"),
    'port': int(os.getenv("POSTGRES_PORT", "5432")),
    'dbname': os.getenv("POSTGRES_DB", "scraper_pro"),  # CORRIGÉ: nom cohérent
    'user': os.getenv("POSTGRES_USER", "scraper_admin"),  # CORRIGÉ
    'password': os.getenv("POSTGRES_PASSWORD", "scraper"),
    'connect_timeout': int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "30")),
    'application_name': 'dashboard_streamlit'
}

# Pool de connexions global
_db_pool = None

@st.cache_resource
def get_db_pool():
    """Crée et retourne le pool de connexions global - CORRIGÉ"""
    global _db_pool
    if _db_pool is None:
        try:
            _db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=int(os.getenv("CONNECTION_POOL_SIZE", "10")),
                **DB_CONFIG
            )
            st.success("Pool de connexions DB initialisé")
        except Exception as e:
            st.error(f"Impossible de créer le pool DB: {e}")
            return None
    return _db_pool

@contextmanager
def get_db_connection():
    """Context manager pour connexions DB avec pool - CORRIGÉ"""
    pool = get_db_pool()
    if not pool:
        raise Exception("Pool DB non disponible")
    
    conn = None
    try:
        conn = pool.getconn()
        if conn:
            yield conn
        else:
            raise Exception("Impossible d'obtenir une connexion du pool")
    except psycopg2.Error as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise e
    finally:
        if conn and pool:
            try:
                pool.putconn(conn)
            except:
                pass

def execute_query(query: str, params: tuple = None, fetch: str = 'all'):
    """Exécute une requête de manière sécurisée avec pool - FONCTION AJOUTÉE"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                
                if fetch == 'all':
                    result = cur.fetchall()
                elif fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'none':
                    conn.commit()
                    result = True
                else:
                    result = cur.fetchall()
                
                if fetch != 'none':
                    conn.commit()
                
                return result
    except Exception as e:
        st.error(f"Erreur base de données: {e}")
        return None

# ============================================================================
# FONCTIONS UTILITAIRES - CORRIGÉES
# ============================================================================

def get_lang():
    """Récupère la langue sélectionnée - CORRIGÉ"""
    if 'language' not in st.session_state:
        st.session_state.language = 'fr'
    return st.session_state.language

def t(key):
    """Fonction de traduction - CORRIGÉ"""
    lang = get_lang()
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, key)

def validate_url(url: str) -> bool:
    """Validation d'URL améliorée - CORRIGÉ"""
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

# ============================================================================
# AUTHENTIFICATION - CORRIGÉE
# ============================================================================

def require_authentication():
    """Authentification robuste - CORRIGÉE"""
    if st.session_state.get("authenticated"):
        return True
    
    st.title(t('app_title'))
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.subheader(t('login_title'))
            
            with st.form("login_form"):
                username = st.text_input(t('username'), value="admin")
                password = st.text_input(t('password'), type="password")
                
                if st.form_submit_button(t('login_button'), use_container_width=True, type="primary"):
                    env_user = os.getenv("DASHBOARD_USERNAME", "admin")
                    env_pass = os.getenv("DASHBOARD_PASSWORD", "admin123")
                    
                    if username == env_user and password == env_pass:
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username
                        st.success("✅ Connexion réussie!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
    
    return False

# ============================================================================
# INTERFACE PRINCIPALE - CORRIGÉE
# ============================================================================

def render_sidebar():
    """Sidebar avec gestion d'erreur - CORRIGÉ"""
    with st.sidebar:
        st.title("🕷️ Scraper Pro")
        
        # Sélecteur de langue
        col1, col2 = st.columns(2)
        with col1:
            selected_lang = st.selectbox(
                "🌐", 
                options=list(LANGUAGES.keys()),
                format_func=lambda x: LANGUAGES[x],
                index=list(LANGUAGES.keys()).index(get_lang()),
                key="language_selector"
            )
            if selected_lang != get_lang():
                st.session_state.language = selected_lang
                st.rerun()
        
        with col2:
            if st.button(t('logout_button')):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        st.divider()
        
        # Navigation principale
        pages = {
            t('dashboard'): "dashboard",
            t('jobs_manager'): "jobs", 
            t('contacts_explorer'): "contacts",
            t('proxy_management'): "proxies",
            t('settings'): "settings"
        }
        
        selected_page = st.radio(
            "📋 Navigation", 
            list(pages.keys()), 
            key="nav_radio"
        )
        
        st.divider()
        
        # État du système avec gestion d'erreur - CORRIGÉ
        try:
            system_status = get_system_status()
            if system_status and system_status.get('db_connected'):
                st.success(t('system_healthy'))
            else:
                st.error(t('system_error'))
        except Exception as e:
            st.error(f"Erreur système: {e}")
            
        return pages[selected_page]

def get_system_status():
    """Vérification de l'état du système avec gestion d'erreur robuste - CORRIGÉ"""
    try:
        # Test simple de connexion
        result = execute_query("SELECT 1 as test", fetch='one')
        return {'db_connected': result is not None}
    except Exception as e:
        st.error(f"Erreur vérification système: {e}")
        return {'db_connected': False}

# ============================================================================
# PAGES PRINCIPALES - CORRIGÉES
# ============================================================================

def page_dashboard():
    """Tableau de bord principal avec gestion d'erreur - CORRIGÉ"""
    st.title(t('dashboard'))
    
    # Métriques principales avec gestion d'erreur
    col1, col2, col3, col4, col5 = st.columns(5)
    
    try:
        metrics = execute_query("""
            SELECT 
                (SELECT COUNT(*) FROM queue WHERE status = 'pending') as pending_jobs,
                (SELECT COUNT(*) FROM queue WHERE status = 'in_progress') as active_jobs,
                (SELECT COUNT(*) FROM queue WHERE status = 'done' AND DATE(updated_at) = CURRENT_DATE) as completed_jobs,
                (SELECT COUNT(*) FROM contacts WHERE DATE(created_at) = CURRENT_DATE AND deleted_at IS NULL) as total_contacts,
                (SELECT COUNT(*) FROM proxies WHERE active = true) as active_proxies
        """, fetch='one')
        
        if metrics:
            with col1:
                st.metric(t('pending_jobs'), metrics['pending_jobs'])
            with col2:
                st.metric(t('active_jobs'), metrics['active_jobs'])  
            with col3:
                st.metric(t('completed_jobs'), metrics['completed_jobs'])
            with col4:
                st.metric(t('total_contacts'), metrics['total_contacts'])
            with col5:
                st.metric(t('active_proxies'), metrics['active_proxies'])
                
            # Alerte si pas de proxies
            if metrics['active_proxies'] == 0:
                st.error(t('no_proxies_warning'))
                if st.button(t('configure_proxies'), type="primary"):
                    st.session_state.nav_radio = t('proxy_management')
                    st.rerun()
        else:
            st.warning("Impossible de récupérer les métriques")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement des métriques: {e}")
        # Affichage de métriques par défaut
        for col, label in zip([col1, col2, col3, col4, col5], 
                              [t('pending_jobs'), t('active_jobs'), t('completed_jobs'), t('total_contacts'), t('active_proxies')]):
            with col:
                st.metric(label, "N/A")

def page_jobs():
    """Gestionnaire de jobs avec gestion d'erreur robuste - CORRIGÉ"""
    st.title(t('jobs_manager'))
    
    # Formulaire de création de job
    with st.expander(t('create_job'), expanded=True):
        with st.form("job_form", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                url = st.text_input(
                    t('job_url'),
                    placeholder="https://example.com",
                    help="URL du site à analyser pour extraire les contacts"
                )
                
                country = st.selectbox(
                    t('job_country'),
                    options=["", "France", "United States", "Canada", "Germany", "Spain"],
                    help="Pays cible pour filtrer les résultats"
                )
                
                theme = st.selectbox(
                    t('job_theme'),
                    options=["lawyers", "doctors", "consultants", "real-estate", "restaurants"],
                    help="Type de professionnels à rechercher"
                )
            
            with col2:
                language = st.selectbox(
                    t('job_language'),
                    options=["", "fr", "en", "es", "de"],
                    help="Langue du contenu à analyser"
                )
                
                use_js = st.checkbox(
                    t('use_javascript'),
                    value=False,
                    help="Activer pour les sites avec contenu dynamique"
                )
                
                max_pages = st.number_input(
                    t('max_pages'),
                    min_value=1,
                    max_value=100,
                    value=25,
                    help="Nombre maximum de pages à analyser par domaine"
                )
            
            # Boutons d'action
            col_a, col_b = st.columns(2)
            
            with col_a:
                test_button = st.form_submit_button(t('test_url_button'), use_container_width=True)
            
            with col_b:
                create_button = st.form_submit_button(t('create_job_button'), use_container_width=True, type="primary")
            
            # Actions des boutons
            if test_button and url:
                if validate_url(url):
                    st.success("✅ URL valide")
                else:
                    st.error("❌ URL invalide")
            
            if create_button and url:
                if not validate_url(url):
                    st.error("❌ Veuillez entrer une URL valide")
                else:
                    try:
                        # Vérifier les proxies
                        proxy_count = execute_query("SELECT COUNT(*) as count FROM proxies WHERE active = true", fetch='one')
                        if not proxy_count or proxy_count['count'] == 0:
                            st.error("❌ Aucun proxy configuré ! Configurez des proxies avant de lancer un job.")
                        else:
                            # Créer le job
                            result = execute_query("""
                                INSERT INTO queue (
                                    url, country_filter, lang_filter, theme, 
                                    use_js, max_pages_per_domain, status, created_by
                                ) VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
                            """, (
                                url, country or None, language or None, theme,
                                use_js, max_pages, st.session_state.get('username', 'dashboard')
                            ), fetch='none')
                            
                            if result:
                                st.success("🚀 Job de scraping lancé avec succès!")
                                st.balloons()
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la création du job")
                                
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la création du job: {e}")
    
    # Liste des jobs récents - CORRIGÉE
    st.subheader("Jobs Récents")
    try:
        jobs = execute_query("""
            SELECT id, url, status, theme, created_at, updated_at,
                   CASE 
                       WHEN status = 'done' THEN '✅'
                       WHEN status = 'failed' THEN '❌'
                       WHEN status = 'in_progress' THEN '⚡'
                       ELSE '⏳'
                   END as status_icon
            FROM queue 
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        
        if jobs:
            df = pd.DataFrame(jobs)
            df['url_short'] = df['url'].str[:50] + '...'
            
            st.dataframe(
                df[['status_icon', 'id', 'url_short', 'theme', 'status', 'created_at']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    'status_icon': st.column_config.TextColumn("", width=40),
                    'id': st.column_config.NumberColumn("ID", width=60),
                    'url_short': st.column_config.TextColumn("URL"),
                    'theme': st.column_config.TextColumn("Thème", width=100),
                    'status': st.column_config.TextColumn("Status", width=100),
                    'created_at': st.column_config.DatetimeColumn("Créé le", width=150)
                }
            )
        else:
            st.info("Aucun job trouvé. Créez votre premier job ci-dessus!")
            
    except Exception as e:
        st.error(f"Erreur lors du chargement des jobs: {e}")

def page_proxies():
    """Gestion des proxies avec interface robuste - CORRIGÉE"""
    st.title(t('proxy_management'))
    
    # Ajouter un proxy
    with st.expander(t('add_proxy'), expanded=True):
        st.info("💡 **Pourquoi des proxies ?** Les proxies permettent d'éviter les blocages lors du scraping.")
        
        with st.form("proxy_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                proxy_type = st.selectbox(
                    t('proxy_type'),
                    options=["http", "https", "socks5"],
                    help="Type de connexion proxy"
                )
                
                host = st.text_input(
                    t('proxy_host'),
                    placeholder="192.168.1.100 ou proxy.example.com",
                    help="Adresse IP ou nom de domaine du proxy"
                )
                
                port = st.number_input(
                    t('proxy_port'),
                    min_value=1,
                    max_value=65535,
                    value=8080,
                    help="Port de connexion"
                )
            
            with col2:
                username = st.text_input(
                    t('proxy_username'),
                    help="Nom d'utilisateur (optionnel)"
                )
                
                password = st.text_input(
                    t('proxy_password'),
                    type="password",
                    help="Mot de passe (optionnel)"
                )
                
                active = st.checkbox("Activer immédiatement", value=True)
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                test_button = st.form_submit_button(t('test_proxy_button'))
            
            with col_b:
                add_button = st.form_submit_button(t('add_proxy_button'), type="primary")
            
            if add_button and host and port:
                try:
                    result = execute_query("""
                        INSERT INTO proxies (scheme, host, port, username, password, active, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (scheme, host, port, COALESCE(username, '')) DO UPDATE SET
                            active = EXCLUDED.active,
                            updated_at = NOW()
                    """, (
                        proxy_type, host, port,
                        username if username else None,
                        password if password else None,
                        active, st.session_state.get('username', 'dashboard')
                    ), fetch='none')
                    
                    if result:
                        st.success("✅ Proxy ajouté avec succès!")
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de l'ajout du proxy")
                        
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'ajout du proxy: {e}")
    
    # Liste des proxies existants - CORRIGÉE
    st.subheader("Proxies Configurés")
    try:
        proxies = execute_query("""
            SELECT 
                id, scheme, host, port, username, active,
                CASE WHEN active THEN '🟢' ELSE '🔴' END as status_icon,
                CASE 
                    WHEN username IS NOT NULL THEN CONCAT(scheme, '://', username, ':***@', host, ':', port)
                    ELSE CONCAT(scheme, '://', host, ':', port)
                END as proxy_url,
                created_at
            FROM proxies 
            ORDER BY active DESC, created_at DESC
        """)
        
        if proxies:
            df = pd.DataFrame(proxies)
            st.dataframe(
                df[['status_icon', 'proxy_url', 'active', 'created_at']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    'status_icon': st.column_config.TextColumn("État", width=50),
                    'proxy_url': st.column_config.TextColumn("Configuration Proxy"),
                    'active': st.column_config.CheckboxColumn("Actif", width=70),
                    'created_at': st.column_config.DatetimeColumn("Ajouté le", width=150)
                }
            )
            
            st.success(f"✅ {len(df)} proxy(s) configuré(s)")
        else:
            st.warning("⚠️ Aucun proxy configuré.")
            
    except Exception as e:
        st.error(f"Erreur lors du chargement des proxies: {e}")

def page_contacts():
    """Explorateur de contacts avec interface robuste - CORRIGÉ"""
    st.title(t('contacts_explorer'))
    
    # Statistiques des contacts
    try:
        stats = execute_query("""
            SELECT 
                COUNT(*) as total_contacts,
                COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as today_contacts,
                COUNT(*) FILTER (WHERE verified = true) as verified_contacts,
                COUNT(DISTINCT country) as unique_countries,
                COUNT(DISTINCT theme) as unique_themes
            FROM contacts WHERE deleted_at IS NULL
        """, fetch='one')
        
        if stats:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("📊 Total", f"{stats['total_contacts']:,}")
            with col2:
                st.metric("📈 Aujourd'hui", stats['today_contacts'])
            with col3:
                st.metric("✅ Vérifiés", stats['verified_contacts'] or 0)
            with col4:
                st.metric("🌍 Pays", stats['unique_countries'] or 0)
            with col5:
                st.metric("🏷️ Thèmes", stats['unique_themes'] or 0)
    
    except Exception as e:
        st.error(f"Erreur lors du chargement des statistiques: {e}")
    
    st.divider()
    
    # Filtres de recherche
    col1, col2, col3 = st.columns(3)
    
    with col1:
        search_text = st.text_input("🔍 Rechercher", placeholder="Nom, email, organisation...")
    
    with col2:
        try:
            countries = execute_query("SELECT DISTINCT country FROM contacts WHERE country IS NOT NULL AND deleted_at IS NULL ORDER BY country") or []
            country_options = ["Tous"] + [c['country'] for c in countries]
            selected_country = st.selectbox("🌍 Pays", country_options)
        except:
            selected_country = "Tous"
    
    with col3:
        try:
            themes = execute_query("SELECT DISTINCT theme FROM contacts WHERE theme IS NOT NULL AND deleted_at IS NULL ORDER BY theme") or []
            theme_options = ["Tous"] + [t['theme'] for t in themes]
            selected_theme = st.selectbox("🏷️ Thème", theme_options)
        except:
            selected_theme = "Tous"
    
    # Liste des contacts - CORRIGÉE
    try:
        # Construction de la requête avec filtres
        where_conditions = ["deleted_at IS NULL"]
        params = []
        
        if search_text:
            where_conditions.append("(name ILIKE %s OR email ILIKE %s OR org ILIKE %s)")
            search_param = f"%{search_text}%"
            params.extend([search_param, search_param, search_param])
        
        if selected_country != "Tous":
            where_conditions.append("country = %s")
            params.append(selected_country)
        
        if selected_theme != "Tous":
            where_conditions.append("theme = %s") 
            params.append(selected_theme)
        
        query = f"""
            SELECT 
                name, email, org, phone, country, theme, 
                COALESCE(verified, false) as verified, created_at,
                CASE WHEN COALESCE(verified, false) THEN '✅' ELSE '⏳' END as verified_icon
            FROM contacts 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY created_at DESC 
            LIMIT 500
        """
        
        contacts = execute_query(query, tuple(params))
        
        if contacts:
            df = pd.DataFrame(contacts)
            
            # Actions sur les contacts
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📊 Export CSV", use_container_width=True):
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ Télécharger CSV",
                        data=csv,
                        file_name=f"contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📧 Export Emails", use_container_width=True):
                    emails = df['email'].dropna().tolist()
                    emails_text = '\n'.join(emails)
                    st.download_button(
                        "⬇️ Liste Emails",
                        data=emails_text,
                        file_name=f"emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
            
            with col3:
                st.metric("Résultats", len(df))
            
            # Affichage du tableau
            st.dataframe(
                df[['verified_icon', 'name', 'email', 'org', 'phone', 'country', 'theme', 'created_at']],
                hide_index=True,
                use_container_width=True,
                column_config={
                    'verified_icon': st.column_config.TextColumn("✓", width=30),
                    'name': st.column_config.TextColumn("Nom", width=150),
                    'email': st.column_config.TextColumn("Email", width=200),
                    'org': st.column_config.TextColumn("Organisation", width=150),
                    'phone': st.column_config.TextColumn("Téléphone", width=120),
                    'country': st.column_config.TextColumn("Pays", width=80),
                    'theme': st.column_config.TextColumn("Thème", width=100),
                    'created_at': st.column_config.DatetimeColumn("Ajouté le", width=120)
                }
            )
        else:
            st.info("🔍 Aucun contact trouvé avec ces critères")
            
    except Exception as e:
        st.error(f"Erreur lors du chargement des contacts: {e}")

def page_settings():
    """Page de paramètres système - CORRIGÉE"""
    st.title(t('settings'))
    
    # Configuration générale
    st.subheader("⚙️ Configuration Générale")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("**Variables d'environnement actuelles:**")
        env_vars = {
            'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'Non défini'),
            'POSTGRES_DB': os.getenv('POSTGRES_DB', 'Non défini'),
            'POSTGRES_USER': os.getenv('POSTGRES_USER', 'Non défini'),
            'DASHBOARD_USERNAME': os.getenv('DASHBOARD_USERNAME', 'Non défini'),
        }
        
        for var, value in env_vars.items():
            st.text(f"{var}: {value}")
    
    with col2:
        st.info("**Statistiques système:**")
        try:
            db_stats = execute_query("""
                SELECT 
                    (SELECT COUNT(*) FROM queue WHERE deleted_at IS NULL) as total_jobs,
                    (SELECT COUNT(*) FROM contacts WHERE deleted_at IS NULL) as total_contacts,
                    (SELECT COUNT(*) FROM proxies) as total_proxies,
                    (SELECT MAX(created_at) FROM queue WHERE deleted_at IS NULL) as last_job_created
            """, fetch='one')
            
            if db_stats:
                st.text(f"Jobs total: {db_stats['total_jobs']}")
                st.text(f"Contacts total: {db_stats['total_contacts']}")
                st.text(f"Proxies total: {db_stats['total_proxies']}")
                st.text(f"Dernier job: {db_stats['last_job_created'] or 'Aucun'}")
        except Exception as e:
            st.error(f"Erreur stats: {e}")
    
    st.divider()
    
    # Actions de maintenance - CORRIGÉES
    st.subheader("🧹 Maintenance")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Nettoyer les anciens jobs", use_container_width=True):
            try:
                result = execute_query("""
                    UPDATE queue SET deleted_at = NOW() 
                    WHERE status IN ('done', 'failed') 
                    AND updated_at < NOW() - INTERVAL '7 days'
                    AND deleted_at IS NULL
                """, fetch='none')
                if result:
                    st.success("✅ Anciens jobs supprimés")
                else:
                    st.info("ℹ️ Aucun ancien job à supprimer")
            except Exception as e:
                st.error(f"❌ Erreur: {e}")
    
    with col2:
        if st.button("📊 Optimiser la base", use_container_width=True):
            try:
                execute_query("VACUUM ANALYZE", fetch='none')
                st.success("✅ Base de données optimisée")
            except Exception as e:
                st.error(f"❌ Erreur: {e}")
    
    with col3:
        if st.button("🔄 Redémarrer services", use_container_width=True):
            st.warning("⚠️ Cette action nécessite un accès administrateur au serveur")
            st.code("docker compose restart")

# ============================================================================
# APPLICATION PRINCIPALE - CORRIGÉE
# ============================================================================

def main():
    """Application principale avec gestion d'erreur globale - CORRIGÉE"""
    
    try:
        # Vérification authentification
        if not require_authentication():
            return
        
        # Navigation et affichage des pages
        current_page = render_sidebar()
        
        # Affichage de la page sélectionnée
        if current_page == "dashboard":
            page_dashboard()
        elif current_page == "jobs":
            page_jobs()
        elif current_page == "contacts":
            page_contacts()
        elif current_page == "proxies":
            page_proxies()
        elif current_page == "settings":
            page_settings()
        else:
            st.error("Page non trouvée")
            
    except Exception as e:
        st.error(f"Erreur critique dans l'application: {e}")
        st.exception(e)
        
        # Bouton de rechargement
        if st.button("🔄 Recharger l'application"):
            st.rerun()

if __name__ == "__main__":
    main()