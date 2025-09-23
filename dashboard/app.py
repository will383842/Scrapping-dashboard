import os
import json
import psycopg2
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
import io

# Configuration DB
DB = dict(
    host=os.getenv("POSTGRES_HOST", "db"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "scraper_pro"),
    user=os.getenv("POSTGRES_USER", "scraper_admin"),
    password=os.getenv("POSTGRES_PASSWORD", "scraper"),
)

def get_db_connection():
    """Connexion DB avec gestion d'erreur"""
    try:
        conn = psycopg2.connect(**DB, connect_timeout=5)
        return conn
    except Exception as e:
        st.error(f"Erreur connexion DB: {e}")
        return None

def require_auth():
    """Système d'authentification"""
    user_env = os.getenv("DASHBOARD_USERNAME", "admin")
    pass_env = os.getenv("DASHBOARD_PASSWORD", "admin123")
    
    if st.session_state.get("auth_ok"):
        return True
        
    st.title("🔒 Connexion au Dashboard")
    with st.form("login_form"):
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            username = st.text_input("Utilisateur", placeholder="admin")
            password = st.text_input("Mot de passe", type="password")
            login_btn = st.form_submit_button("Se connecter", use_container_width=True)
            
        if login_btn:
            if username == user_env and password == pass_env:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("❌ Identifiants invalides")
                st.info(f"Utilisez: {user_env} / {pass_env}")
    return False

def sidebar_navigation():
    """Navigation sidebar moderne"""
    with st.sidebar:
        st.title("🕷️ Scraper Pro")
        
        # Status système
        conn = get_db_connection()
        if conn:
            st.success("🟢 Système opérationnel")
            conn.close()
        else:
            st.error("🔴 Problème DB")
            
        st.divider()
        
        # Menu navigation
        pages = {
            "📊 Dashboard": "dashboard",
            "🎯 Jobs Manager": "jobs",
            "📇 Contacts": "contacts", 
            "🌐 Proxies": "proxies",
            "⚙️ Settings": "settings"
        }
        
        selected = st.radio("Navigation", list(pages.keys()), key="nav_radio")
        
        return pages[selected]

def page_dashboard():
    """Page dashboard principal avec KPIs"""
    st.title("📊 Dashboard Principal")
    
    conn = get_db_connection()
    if not conn:
        return
        
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # KPIs généraux
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cur.execute("SELECT COUNT(*) FROM queue WHERE status = 'pending'")
            pending_jobs = cur.fetchone()['count']
            st.metric("🔄 Jobs en attente", pending_jobs)
            
        with col2:
            cur.execute("SELECT COUNT(*) FROM contacts WHERE DATE(created_at) = CURRENT_DATE")
            contacts_today = cur.fetchone()['count']  
            st.metric("👥 Contacts aujourd'hui", contacts_today)
            
        with col3:
            cur.execute("SELECT COUNT(*) FROM proxies WHERE active = true")
            active_proxies = cur.fetchone()['count']
            st.metric("🌐 Proxies actifs", active_proxies)
            
        with col4:
            cur.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done
                FROM queue WHERE DATE(created_at) = CURRENT_DATE
            """)
            perf = cur.fetchone()
            success_rate = round(perf['done'] / max(perf['total'], 1) * 100, 1)
            st.metric("✅ Taux de succès", f"{success_rate}%")
    
    conn.close()

def page_jobs():
    """Page de gestion des jobs"""
    st.title("🎯 Gestion des Jobs")
    
    # Formulaire création job
    with st.expander("➕ Nouveau Job", expanded=True):
        with st.form("create_job"):
            col1, col2 = st.columns(2)
            with col1:
                url = st.text_input("URL à scraper", placeholder="https://example.com")
                country = st.selectbox("Pays", ["", "France", "Thailand", "United States"])
                theme = st.selectbox("Thème", ["lawyers", "doctors", "consultants"])
                
            with col2:
                language = st.selectbox("Langue", ["", "fr", "en"])
                use_js = st.checkbox("Utiliser JavaScript", value=False)
                max_pages = st.slider("Max pages par domaine", 1, 100, 15)
            
            submit = st.form_submit_button("🚀 Créer Job", use_container_width=True)
                
            if submit and url:
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO queue (url, country_filter, lang_filter, theme, 
                                                 use_js, max_pages_per_domain, status)
                                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                            """, (url, country or None, language or None, theme, 
                                 use_js, max_pages))
                            conn.commit()
                        st.success("✅ Job créé avec succès!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur création job: {e}")
                    finally:
                        conn.close()
    
    # Liste des jobs
    st.subheader("📋 Liste des Jobs")
    
    conn = get_db_connection()
    if not conn:
        return
        
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, url, status, theme, use_js, created_at, updated_at
            FROM queue 
            ORDER BY id DESC 
            LIMIT 50
        """)
        jobs = pd.DataFrame(cur.fetchall())
    
    if not jobs.empty:
        st.dataframe(jobs, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun job trouvé")
    
    conn.close()

def page_proxies():
    """Page de gestion des proxies - FONCTIONNALITÉ CRITIQUE"""
    st.title("🌐 Gestion des Proxies")
    
    # Section ajout de proxies
    st.subheader("➕ Ajouter des Proxies")
    
    tab1, tab2 = st.tabs(["📝 Proxy Unique", "📋 Import en Masse"])
    
    with tab1:
        with st.form("add_single_proxy"):
            col1, col2 = st.columns(2)
            with col1:
                label = st.text_input("Label", placeholder="Proxy France 1")
                scheme = st.selectbox("Type", ["http", "https", "socks5"])
                host = st.text_input("Host/IP", placeholder="1.2.3.4")
                port = st.number_input("Port", min_value=1, max_value=65535, value=8080)
            with col2:
                username = st.text_input("Username (optionnel)")
                password = st.text_input("Password (optionnel)", type="password")
                priority = st.slider("Priorité", 1, 100, 10)
                active = st.checkbox("Actif", value=True)
                
            submit_single = st.form_submit_button("➕ Ajouter Proxy")
            
            if submit_single and host and port:
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO proxies (label, scheme, host, port, username, password, priority, active)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (scheme, host, port, COALESCE(username, ''))
                                DO UPDATE SET 
                                    label = EXCLUDED.label,
                                    priority = EXCLUDED.priority,
                                    active = EXCLUDED.active
                            """, (label or f"{host}:{port}", scheme, host, port, 
                                 username or None, password or None, priority, active))
                            conn.commit()
                        st.success("✅ Proxy ajouté!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
                    finally:
                        conn.close()
    
    with tab2:
        st.info("💡 Format supporté: IP:PORT ou IP:PORT:USER:PASS (un par ligne)")
        bulk_input = st.text_area("Liste de proxies", height=200, 
                                 placeholder="""192.168.1.1:8080
192.168.1.2:8080:user:pass
proxy.example.com:3128""")
        
        col1, col2 = st.columns(2)
        with col1:
            bulk_scheme = st.selectbox("Type par défaut", ["http", "https", "socks5"], key="bulk_scheme")
            bulk_priority = st.slider("Priorité par défaut", 1, 100, 10, key="bulk_priority")
        with col2:
            bulk_active = st.checkbox("Tous actifs", value=True, key="bulk_active")
            
        if st.button("📥 Importer Proxies en Masse"):
            if bulk_input.strip():
                conn = get_db_connection()
                if conn:
                    added_count = 0
                    failed_count = 0
                    
                    for line in bulk_input.strip().split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                            
                        try:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                host = parts[0]
                                port = int(parts[1])
                                username = parts[2] if len(parts) > 2 else None
                                password = parts[3] if len(parts) > 3 else None
                                
                                with conn.cursor() as cur:
                                    cur.execute("""
                                        INSERT INTO proxies (label, scheme, host, port, username, password, priority, active)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (scheme, host, port, COALESCE(username, ''))
                                        DO UPDATE SET active = EXCLUDED.active
                                    """, (f"{host}:{port}", bulk_scheme, host, port, 
                                         username, password, bulk_priority, bulk_active))
                                added_count += 1
                        except Exception as e:
                            failed_count += 1
                            st.warning(f"Erreur ligne '{line}': {e}")
                    
                    conn.commit()
                    conn.close()
                    
                    if added_count:
                        st.success(f"✅ {added_count} proxies ajoutés!")
                    if failed_count:
                        st.warning(f"⚠️ {failed_count} lignes ignorées")
                    
                    st.rerun()
    
    # Liste des proxies existants
    st.divider()
    st.subheader("📊 Proxies Configurés")
    
    conn = get_db_connection()
    if not conn:
        return
        
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, label, scheme, host, port, username, active, priority, 
                   last_used_at, created_at
            FROM proxies 
            ORDER BY active DESC, priority ASC, id DESC
        """)
        proxies_data = pd.DataFrame(cur.fetchall())
    
    if not proxies_data.empty:
        # Actions bulk sur proxies
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("✅ Activer Tous"):
                with conn.cursor() as cur:
                    cur.execute("UPDATE proxies SET active = true")
                    conn.commit()
                st.success("Tous les proxies activés")
                st.rerun()
        with col2:
            if st.button("⏸️ Désactiver Tous"):
                with conn.cursor() as cur:
                    cur.execute("UPDATE proxies SET active = false")
                    conn.commit()
                st.warning("Tous les proxies désactivés")
                st.rerun()
        with col3:
            if st.button("🧪 Test Tous"):
                st.info("Test en masse en développement")
        with col4:
            if st.button("🗑️ Supprimer Inactifs"):
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM proxies WHERE active = false")
                    deleted = cur.rowcount
                    conn.commit()
                st.success(f"{deleted} proxies supprimés")
                st.rerun()
        
        # Affichage du tableau
        st.dataframe(proxies_data, use_container_width=True, hide_index=True)
        
        # Stats proxies
        active_count = len(proxies_data[proxies_data['active'] == True])
        total_count = len(proxies_data)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total proxies", total_count)
        with col2:
            st.metric("Proxies actifs", active_count)  
        with col3:
            success_rate = round(active_count / total_count * 100, 1) if total_count else 0
            st.metric("Taux actifs", f"{success_rate}%")
            
    else:
        st.info("Aucun proxy configuré. Utilisez les onglets ci-dessus pour en ajouter.")
    
    conn.close()

def page_contacts():
    """Page de visualisation et gestion des contacts"""
    st.title("📇 Explorer les Contacts")
    
    conn = get_db_connection()
    if not conn:
        return
    
    # Stats rapides
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as total FROM contacts")
        total_contacts = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as today FROM contacts WHERE DATE(created_at) = CURRENT_DATE")
        today_contacts = cur.fetchone()['today']
        
        cur.execute("SELECT COUNT(DISTINCT country) as countries FROM contacts WHERE country IS NOT NULL")
        unique_countries = cur.fetchone()['countries']
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Contacts", total_contacts)
    with col2:
        st.metric("📈 Aujourd'hui", today_contacts)
    with col3:
        st.metric("🌍 Pays", unique_countries)
    
    # Filtres
    st.subheader("🔍 Filtres et Recherche")
    
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("🔍 Rechercher", placeholder="Nom, email, organisation...")
    with col2:
        limit = st.selectbox("Nombre", [100, 250, 500])
    
    # Récupération des contacts
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if search_query:
            cur.execute("""
                SELECT id, name, email, org, phone, country, theme, created_at
                FROM contacts 
                WHERE name ILIKE %s OR email ILIKE %s OR org ILIKE %s
                ORDER BY created_at DESC 
                LIMIT %s
            """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", limit))
        else:
            cur.execute("""
                SELECT id, name, email, org, phone, country, theme, created_at
                FROM contacts 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
        
        contacts_data = cur.fetchall()
    
    if contacts_data:
        df = pd.DataFrame(contacts_data)
        
        # Actions d'export
        st.subheader("📥 Export et Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Export CSV"):
                csv = df.to_csv(index=False)
                st.download_button(
                    label="⬇️ Télécharger CSV",
                    data=csv,
                    file_name=f"contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
                
        with col2:
            if st.button("📈 Export Excel"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Contacts', index=False)
                
                st.download_button(
                    label="⬇️ Télécharger Excel", 
                    data=output.getvalue(),
                    file_name=f"contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        with col3:
            if st.button("📧 Export Emails"):
                emails = df['email'].dropna().tolist()
                email_text = '\n'.join(emails)
                st.download_button(
                    label="⬇️ Liste Emails",
                    data=email_text,
                    file_name=f"emails_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    mime="text/plain"
                )
        
        # Affichage du tableau
        st.subheader(f"📋 Résultats ({len(contacts_data)} contacts)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    else:
        st.info("Aucun contact trouvé")
    
    conn.close()

def page_settings():
    """Page des paramètres système"""
    st.title("⚙️ Paramètres Système")
    
    conn = get_db_connection()
    if not conn:
        return
    
    # Récupération des paramètres actuels
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT key, value FROM settings ORDER BY key")
        current_settings = {row['key']: row['value'] for row in cur.fetchall()}
    
    # Configuration du scraping
    st.subheader("🕷️ Configuration Scraping")
    
    with st.form("scraping_settings"):
        col1, col2 = st.columns(2)
        
        with col1:
            js_limit = st.number_input(
                "Limite pages JS par jour",
                min_value=0,
                value=int(current_settings.get('js_pages_limit','2000'))
            )
            
            concurrent_req = st.number_input(
                "Requêtes simultanées",
                min_value=1,
                max_value=50,
                value=16
            )
            
        with col2:
            download_delay = st.number_input(
                "Délai entre requêtes (sec)",
                min_value=0.0,
                max_value=10.0,
                value=0.5,
                step=0.1
            )
            
            max_pages_default = st.number_input(
                "Pages max par domaine",
                min_value=1,
                max_value=200,
                value=50
            )
        
        # Scheduler settings
        st.subheader("⏰ Configuration Scheduler")
        scheduler_paused = st.checkbox(
            "Mettre en pause le scheduler",
            value=current_settings.get('scheduler_paused', 'false') == 'true'
        )
        
        submit_settings = st.form_submit_button("💾 Enregistrer les Paramètres")
        
        if submit_settings:
            try:
                with conn.cursor() as cur:
                    # Mise à jour des settings en DB
                    settings_to_update = [
                        ('js_pages_limit', str(js_limit)),
                        ('scheduler_paused', str(scheduler_paused).lower()),
                        ('max_pages_default', str(max_pages_default))
                    ]
                    
                    for key, value in settings_to_update:
                        cur.execute("""
                            INSERT INTO settings (key, value) 
                            VALUES (%s, %s)
                            ON CONFLICT (key) 
                            DO UPDATE SET value = EXCLUDED.value
                        """, (key, value))
                    
                    conn.commit()
                
                st.success("✅ Paramètres enregistrés!")
                
            except Exception as e:
                st.error(f"❌ Erreur lors de la sauvegarde: {e}")
    
    # Informations système
    st.divider()
    st.subheader("ℹ️ Informations Système")
    
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM queue")
        total_jobs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM contacts")
        total_contacts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM proxies")
        total_proxies = cur.fetchone()[0]
        
    st.info(f"""
    **Statistiques:**
    - Jobs total: {total_jobs:,}
    - Contacts total: {total_contacts:,}  
    - Proxies total: {total_proxies:,}
    """)
    
    # Utilisation JS pages
    js_used = int(current_settings.get('js_pages_used', '0'))
    js_limit_val = int(current_settings.get('js_pages_limit', '2000'))
    
    st.metric(
        "Pages JS utilisées aujourd'hui", 
        f"{js_used:,} / {js_limit_val:,}"
    )
    
    # Actions d'administration
    st.divider()
    st.subheader("🔧 Actions d'Administration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Reset Compteur JS"):
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO settings (key, value) VALUES ('js_pages_used', '0')
                        ON CONFLICT (key) DO UPDATE SET value = '0'
                    """)
                    conn.commit()
                st.success("Compteur JS remis à zéro")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with col2:
        if st.button("🗑️ Nettoyer Jobs"):
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM queue 
                        WHERE status IN ('done', 'failed') 
                        AND created_at < NOW() - INTERVAL '7 days'
                    """)
                    deleted = cur.rowcount
                    conn.commit()
                st.success(f"{deleted} anciens jobs supprimés")
            except Exception as e:
                st.error(f"Erreur: {e}")
    
    with col3:
        if st.button("💾 Export Config"):
            config_export = {
                'settings': current_settings,
                'export_date': datetime.now().isoformat()
            }
            
            config_json = json.dumps(config_export, indent=2, ensure_ascii=False)
            st.download_button(
                "⬇️ Télécharger Config",
                data=config_json,
                file_name=f"scraper_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    conn.close()

def main():
    """Fonction principale de l'application"""
    st.set_page_config(
        page_title="Scraper Pro Dashboard",
        page_icon="🕷️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Vérification de l'authentification
    if not require_auth():
        return
    
    # Navigation
    current_page = sidebar_navigation()
    
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

if __name__ == "__main__":
    main()