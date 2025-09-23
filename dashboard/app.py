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

def require_auth():
    user_env = os.getenv("DASHBOARD_USERNAME")
    pass_env = os.getenv("DASHBOARD_PASSWORD")
    if not user_env or not pass_env:
        st.warning("⚠️ Auth non configurée. Définissez DASHBOARD_USERNAME et DASHBOARD_PASSWORD dans l'environnement.")
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("🔒 Connexion")
    with st.form("login"):
        u = st.text_input("Utilisateur")
        p = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter")
        if ok:
            if u == user_env and p == pass_env:
                st.session_state["auth_ok"] = True
                st.experimental_rerun()
            else:
                st.error("Identifiants invalides.")
    return False

def page_sessions():
    st.title("🔑 Sessions (login) — storage_state / cookies")
    with st.form("upload_session"):
        domain = st.text_input("Domaine (ex: portal.example.com)")
        s_type = st.selectbox("Type", ["storage_state","cookies"], index=0)
        file = st.file_uploader("Fichier JSON", type=["json"])
        notes = st.text_area("Notes (optionnel)")
        active = st.checkbox("Actif", True)
        submitted = st.form_submit_button("Uploader")
        if submitted:
            if not (domain and file):
                st.error("Domaine et fichier requis.")
            else:
                save_dir = "/app/sessions"
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"{domain}.json")
                with open(save_path,"wb") as f:
                    f.write(file.read())
                c,q = db_cursor()
                q.execute(
                    """INSERT INTO sessions(domain,type,file_path,active,notes)
                       VALUES (%s,%s,%s,%s,%s)""",
                    (domain, s_type, save_path, active, notes)
                )
                c.commit(); q.close(); c.close()
                st.success("Session importée ✅")
    st.subheader("Liste des sessions")
    c,q = db_cursor()
    q.execute("""SELECT id,domain,type,file_path,active,notes,created_at,last_used_at
                 FROM sessions ORDER BY active DESC, domain ASC, id DESC""")
    rows = q.fetchall(); q.close(); c.close()
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune session.")

def page_queue():
    st.title("📋 File d'attente (queue)")
    c,q = db_cursor()
    # si la colonne priority n'existe pas dans ta DB, enlève "priority DESC," ci-dessous
    q.execute("""SELECT id, url, use_js, status, priority, created_at, updated_at
                 FROM queue ORDER BY status ASC, priority DESC, id DESC LIMIT 200""")
    rows = q.fetchall(); q.close(); c.close()
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune tâche.")

def page_contacts():
    st.title("📇 Contacts")
    c,q = db_cursor()
    q.execute("""SELECT id, name, email, phone, source_url, created_at
                 FROM contacts ORDER BY id DESC LIMIT 500""")
    rows = q.fetchall(); q.close(); c.close()
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun contact.")

def page_settings():
    st.title("⚙️ Paramètres")
    c,q = db_cursor()
    q.execute("""SELECT key, value FROM settings ORDER BY key ASC""")
    rows = q.fetchall()
    current = {r['key']: r['value'] for r in rows}
    with st.form("settings"):
        js_limit = st.number_input(
            "JS pages limit / jour",
            min_value=0,
            value=int(current.get('js_pages_limit','300'))
        )
        submitted = st.form_submit_button("Enregistrer")
        if submitted:
            q.execute("""INSERT INTO settings(key,value) VALUES('js_pages_limit', %s)
                        ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value""",
                      (str(js_limit),))
            c.commit()
            st.success("Paramètres enregistrés.")
    q.close(); c.close()

def main():
    st.set_page_config(page_title="Scraper Dashboard", layout="wide")
    if not require_auth():
        return
    page = st.sidebar.selectbox("Pages", ["📋 Queue", "🔑 Sessions", "📇 Contacts", "⚙️ Settings"])
    if page.startswith("🔑"):
        page_sessions()
    elif page.startswith("📇"):
        page_contacts()
    elif page.startswith("⚙️"):
        page_settings()
    else:
        page_queue()

if __name__ == "__main__":
    main()
