# pages/20__Utilisation.py
import streamlit as st
import re
from textwrap import dedent
from pathlib import Path

st.set_page_config(
    page_title=" User Guide — Utilisation / Usage",
    page_icon="",
    layout="wide",
)

MANUAL_MD_FR = dedent(r"""
#  Mode d’emploi — Utilisation détaillée (pas-à-pas)

> Cette page explique **exactement** comment :  
> **1)** Ajouter des **proxies** (formats, tests, rotation, paramètres recommandés)  
> **2)** **Lancer une recherche** / créer un Job (tous les champs + profils conseillés)  
> **3)** **Trier / Filtrer / Rechercher** dans les résultats  
> **4)** **Exporter** (CSV depuis le dashboard & via SQL)  
> **5)** Recettes prêtes à l’emploi & **Dépannage rapide**

---

## 1) Ajouter des proxies — simple & complet

### 1.1 Ajout via l’interface (recommandé)
1. Ouvrez ** Gestion des Proxies**.  
2. Cliquez **Importer** (ou **Ajouter des proxies**).  
3. Collez **une ligne par proxy** (formats acceptés) :
   ```
   IP:PORT
   IP:PORT:USER:PASS
   http://USER:PASS@IP:PORT
   https://USER:PASS@HOST:PORT
   socks5://USER:PASS@HOST:PORT
   ```
   **Exemples valides**
   ```
   51.38.12.34:3128
   185.23.44.10:1080:user123:passABC
   http://user:pw@198.51.100.7:8080
   https://user:pw@proxy.vendor.net:8443
   socks5://login:secret@203.0.113.9:9050
   ```
4. Cliquez **Tester** → attendez le résultat.  
   - **OK** = latence raisonnable + authentification réussie  
   - **KO** = vérifiez login/mot de passe, protocole (http/https/socks5), IP/port
5. Sélectionnez les lignes **OK** puis **Activer** (ou **Enregistrer**).

**Contrôles rapides**
- *Statut* : **Actif**  
- *Latence* : **< 1500 ms** (viser < 800 ms si possible)  
- *Taux d’échec test* : **< 5–10 %**

---

### 1.2 Import par fichier (si proposé)
1. **Importer depuis un fichier** `.txt` ou `.csv` (1 proxy/ligne, mêmes formats).  
2. Lancez **Tester** puis **Activer** uniquement les **OK**.  
> Astuce : gardez un `proxies.csv` (privé) versionné pour l’équipe.

---

### 1.3 Rotation & fiabilité (réglages détaillés)
Dans **️ Paramètres** (ou `config/proxy_config.json`) :

- **Mode de rotation**  
  - `round_robin` : parcourt en boucle (simple)  
  - `random` : aléatoire (équilibrage basique)  
  - `weighted_random` : aléatoire **pondéré** (recommandé si pool mixte DC/Residential)  
  - `sticky_session` : conserve la **même IP** durant un TTL (sessions/login)
- **Sticky TTL** : durée en secondes (ex. **180 s**)  
- **RPS max** (requêtes/seconde)  
  - Datacenter : **1.0–2.0**  
  - Résidentiel : **0.3–0.8**  
- **Circuit-breaker / Cooldown**  
  - *Seuil d’échecs* (ex. **5**) → *repos* **60–120 s**  
- **Warm-up**  
  - montée en charge douce (ex. +1 req / 10 s)

**Réglage de départ conseillé**
- Rotation : `weighted_random`  
- Sticky TTL : **120–180 s** (sites sensibles)  
- RPS : **0.5** (résidentiel) / **1.5** (datacenter)  
- Circuit-breaker : **5** échecs → cooldown **90 s**

---

### 1.4 Vérifier que le pool est prêt
- Lancer un **petit job test** (cf. §2) sur 2–3 pages publiques.  
- Surveiller : **taux de réussite par proxy**, **latence**, **403/429**, **timeouts**.  
- Ajuster **Concurrence**, **Delay** et la **Rotation** si besoin.

---

## 2) Lancer une recherche (créer un Job)

### 2.1 Champs à remplir (pas-à-pas)
1. ** Gestionnaire de Jobs** → **Créer un Job**  
2. **Sources**
   - **URLs** (1 par ligne) — *ex.*  
     ```
     https://exemple.com/recherche?q=chaussures
     https://exemple.com/categorie/page/1
     https://autre-site.fr/listing
     ```
   - **Pays** *(optionnel)* : 1 ou plusieurs  
   - **Langue** *(optionnel)* : `auto` / `fr` / `en` / …
3. **Comportement**
   - **JavaScript (Playwright)** :  
     - ** Désactivé** = sites **statiques**  
     - ** Activé** = sites **dynamiques (SPA/JS)**  
   - **Concurrence** :  
     - sans JS : **6–12**  
     - avec JS : **2–4**  
   - **Download Delay** : **0.5–1.5 s** (sites sensibles : ↑)  
   - **Retry/Backoff** : **2–3** tentatives (timeouts/429)  
   - **Proxies** : vérifiez que le **pool actif** est sélectionné (si choix dans l’UI)
4. **Ciblage & limites**
   - **Mots-clés** (inclure/exclure) si proposés  
   - **Profondeur / pages max** : **3–5** pour tests, ↑ en prod  
   - **Priorité** du job (si file d’attente)
5. **Planification** (si dispo) : exécution **immédiate** ou **répétée** (quot., hebdo, …)
6. Cliquez ** START SCRAPING**.

### 2.2 Profils conseillés
- **Site statique** : JS **** | Concurrence **8–12** | Delay **~1 s** | Retry **2**  
- **Site dynamique (SPA)** : JS **** | Concurrence **2–4** | Delay **1–1.5 s** | Timeout **↑** | Sticky **souvent utile**

---

## 3) Suivre l’exécution & diagnostiquer

- ** Tableau de bord** : états **Pending / Active / Completed / Failed**  
- **Détails du job** : progression, dernières URLs, erreurs catégorisées  
- **Logs (avancé)** :
  ```bash
  docker logs -f <nom_du_worker>
  ```
**Signaux d’alerte & actions**
- **403 / 429** → Concurrence **↓**, Delay **↑**, **Rotation/Sticky** **ON**, **Cooldown**  
- **Timeouts JS** → Timeout **↑**, attendre sélecteurs (wait for selector), tester **sans JS** si fallback HTML  
- **Échecs élevés** → vérifier **pool proxy**, mode `weighted_random`, RPS **↓**

---

## 4) Résultats : trier, filtrer, rechercher

Ouvrez ** Explorateur de Contacts** (ou “Résultats”).

### 4.1 Trier
- Cliquez sur l’en-tête d’une colonne pour trier **asc/desc**  
  - Tris utiles : `created_at` (récents), `domain`, `country`, `score` (si présent)

### 4.2 Filtrer (exemples)
- **Pays** : **FR** ; **Langue** : `fr`  
- **Période** : “Derniers 7 jours”  
- **Texte** : `gmail.com` pour cibler des emails Gmail  
- **Non vides** : garder les lignes avec **email** rempli

### 4.3 Rechercher
- Zone **Rechercher** (plein-texte) sur nom/titre/email/domaine (selon schéma)

---

## 5) Exporter (CSV & SQL)

### 5.1 Export depuis le Dashboard
1. ** Explorateur de Contacts** → appliquer **filtres/tri**  
2. **⬇️ Export CSV** (ou **⬇️ Export Emails**)  
   - **CSV filtré** : exporte les lignes visibles/filtrées (selon implémentation)  
   - **CSV complet** : si bouton/option dédié(e)
3. Si Excel n’affiche pas correctement : importer le fichier en **UTF-8** via *Données → À partir d’un fichier texte/CSV*.

**Bonnes pratiques**
- Contrôlez **20–50 lignes** (colonnes, accents)  
- Rangez : `exports/2025-09-25_contacts_FR.csv`

### 5.2 Export via PostgreSQL (avancé)
```sql
-- Prévisualiser
SELECT * FROM public.contacts
ORDER BY created_at DESC
LIMIT 100;

-- Export CSV (psql)
\copy (SELECT * FROM public.contacts) TO 'contacts.csv' WITH CSV HEADER;

-- Filtrer : France + email non nul
SELECT * FROM public.contacts
WHERE country = 'FR' AND email IS NOT NULL
ORDER BY created_at DESC;

-- Dédoublonner par email (garder la plus récente)
SELECT DISTINCT ON (email) *
FROM public.contacts
WHERE email IS NOT NULL
ORDER BY email, created_at DESC;

-- Garder certains domaines
SELECT * FROM public.contacts
WHERE email LIKE '%@gmail.com' OR email LIKE '%@proton.me';
```

---

## 6) Recettes rapides

**A) Test éclair (statique)**
- Proxies : **optionnel** ; JS : **** ; Concurrence **8** ; Delay **1.0s** ; 3–5 URLs

**B) SPA (anti-bot léger)**
- Proxies : **datacenter** (≥ 10 IP) ; JS : **** ; Concurrence **3** ; Delay **1.5s** ; Sticky **TTL 180s**

**C) Emails qualifiés (FR, récents)**
- Filtre : **Pays=FR** + **email non vide** + période **30j** → **Export CSV**

---

## 7) Dépannage rapide (FAQ)

**Dashboard KO**
- `docker compose ps` ; `docker logs -f <dashboard>`

**Job pending/failed**
- Worker up ; Concurrence **↓**, Delay **↑** ; JS **ON** si SPA

**403/429**
- Rotation/Sticky ON ; Concurrence **↓**, Delay **↑** ; Cooldown ; pool résidentiel

**Timeouts/JS**
- Timeout **↑** ; attendre sélecteurs ; tester **sans JS** si fallback HTML

**Export vide**
- Vérifier **filtres** ; pipelines DB ; relancer **petit job** de test

---

## 8) Checklist quotidienne 
- [ ] Proxies **OK** (tests verts, rotation, latence)  
- [ ] Paramètres **adaptés** (JS, Concurrence, Delay, Retry)  
- [ ] Jobs **planifiés** correctement  
- [ ] Exports **vérifiés** (échantillon)  
- [ ] Monitoring **consulté** (erreurs, latence, ressources)
""").strip("\n")

MANUAL_MD_EN = dedent(r"""
#  User Guide — Detailed Usage (Step-by-Step)

> This page explains exactly how to:  
> **1)** Add **proxies** (formats, testing, rotation, recommended settings)  
> **2)** **Start a search** / create a Job (all fields + suggested profiles)  
> **3)** **Sort / Filter / Search** results  
> **4)** **Export** (CSV from dashboard & via SQL)  
> **5)** Ready-made recipes & **Quick troubleshooting**

---

## 1) Add proxies — simple & complete

### 1.1 Via the interface (recommended)
1. Open ** Proxy Management**.  
2. Click **Import** (or **Add proxies**).  
3. Paste **one proxy per line** (accepted formats):
   ```
   IP:PORT
   IP:PORT:USER:PASS
   http://USER:PASS@IP:PORT
   https://USER:PASS@HOST:PORT
   socks5://USER:PASS@HOST:PORT
   ```
   **Valid examples**
   ```
   51.38.12.34:3128
   185.23.44.10:1080:user123:passABC
   http://user:pw@198.51.100.7:8080
   https://user:pw@proxy.vendor.net:8443
   socks5://login:secret@203.0.113.9:9050
   ```
4. Click **Test** → wait for results.  
   - **OK** = reasonable latency + successful auth  
   - **KO** = check credentials, protocol (http/https/socks5), IP/port
5. Select **OK** rows then **Enable** (or **Save**).

**Quick checks**
- *Status*: **Active**  
- *Latency*: **< 1500 ms** (aim **< 800 ms**)  
- *Failure rate (test)*: **< 5–10%**

---

### 1.2 Import from file (if provided)
1. **Import from file** `.txt` or `.csv` (1 proxy/line, same formats).  
2. **Test** then **Enable** only the **OK** ones.  
> Tip: keep a private, versioned `proxies.csv` for the team.

---

### 1.3 Rotation & reliability (detailed)
In **️ Settings** (or `config/proxy_config.json`):

- **Rotation mode**  
  - `round_robin` — loop through (simple)  
  - `random` — random balancing  
  - `weighted_random` — random with **weights** (great for DC/Residential mix)  
  - `sticky_session` — keep the **same IP** during a TTL (session/login)
- **Sticky TTL**: seconds (e.g. **180 s**)  
- **Max RPS** (requests/sec)  
  - Datacenter: **1.0–2.0**  
  - Residential: **0.3–0.8**  
- **Circuit-breaker / Cooldown**  
  - *Failure threshold* (e.g. **5**) → *rest* **60–120 s**  
- **Warm-up**  
  - gentle ramp-up (e.g. +1 request / 10 s)

**Suggested baseline**
- Rotation: `weighted_random`  
- Sticky TTL: **120–180 s** (sensitive sites)  
- RPS: **0.5** (residential) / **1.5** (datacenter)  
- Circuit-breaker: **5** fails → **90 s** cooldown

---

### 1.4 Validate pool readiness
- Run a **small test job** (see §2) on 2–3 public pages.  
- Watch: **success rate per proxy**, **latency**, **403/429**, **timeouts**.  
- Tune **Concurrency**, **Delay**, and **Rotation** if needed.

---

## 2) Start a search (create a Job)

### 2.1 Fields (step-by-step)
1. ** Job Manager** → **Create Job**  
2. **Sources**
   - **URLs** (1 per line) — *e.g.*  
     ```
     https://example.com/search?q=shoes
     https://example.com/category/page/1
     https://another-site.io/listing
     ```
   - **Country** *(optional)*: 1+  
   - **Language** *(optional)*: `auto` / `en` / `fr` / …
3. **Behavior**
   - **JavaScript (Playwright)**:  
     - ** Off** = **static** sites  
     - ** On** = **dynamic** (SPA/JS) sites  
   - **Concurrency**:  
     - no JS: **6–12**  
     - with JS: **2–4**  
   - **Download Delay**: **0.5–1.5 s** (increase for sensitive sites)  
   - **Retry/Backoff**: **2–3** attempts (timeouts/429)  
   - **Proxies**: ensure **active pool** is selected (if UI offers it)
4. **Targeting & limits**
   - **Include/Exclude keywords** (if available)  
   - **Depth / max pages**: **3–5** for tests, ↑ for prod  
   - **Priority** (if queueing)
5. **Scheduling** (if available): **immediate** or **recurring** (daily/weekly/…)
6. Click ** START SCRAPING**.

### 2.2 Suggested profiles
- **Static site**: JS **** | Concurrency **8–12** | Delay **~1 s** | Retry **2**  
- **Dynamic (SPA)**: JS **** | Concurrency **2–4** | Delay **1–1.5 s** | Timeout **↑** | Sticky often helpful

---

## 3) Monitor & diagnose

- ** Dashboard**: states **Pending / Active / Completed / Failed**  
- **Job details**: progress, latest URLs, categorized errors  
- **Logs (advanced)**:
  ```bash
  docker logs -f <worker_name>
  ```
**Red flags & actions**
- **403 / 429** → Concurrency **↓**, Delay **↑**, **Rotation/Sticky** **ON**, **Cooldown**  
- **JS timeouts** → Timeout **↑**, wait for stable selectors, try **No-JS** if HTML fallback  
- **High failures** → check **proxy pool**, switch to `weighted_random`, reduce RPS

---

## 4) Results: sort, filter, search

Open ** Contacts Explorer** (or “Results”).

### 4.1 Sort
- Click a column header to toggle **asc/desc**  
  - Useful: `created_at` (latest first), `domain`, `country`, `score` (if any)

### 4.2 Filter (examples)
- **Country**: **FR** ; **Language**: `fr`  
- **Date range**: “Last 7 days”  
- **Text**: `gmail.com` to target Gmail emails  
- **Non-empty**: keep rows with **email** filled

### 4.3 Search
- Full-text **Search** box across name/title/email/domain (depending on schema)

---

## 5) Export (CSV & SQL)

### 5.1 From the Dashboard
1. ** Contacts Explorer** → apply **filters/sort**  
2. **⬇️ Export CSV** (or **⬇️ Export Emails**)  
   - **Filtered CSV**: exports visible/filtered rows (depending on implementation)  
   - **Full CSV**: if there is a dedicated button/option
3. If Excel shows weird characters: import as **UTF-8** via *Data → From text/CSV*.

**Good practice**
- Check **20–50 lines** sample (columns, accents)  
- Store as: `exports/2025-09-25_contacts_FR.csv`

### 5.2 Via PostgreSQL (advanced)
```sql
-- Preview
SELECT * FROM public.contacts
ORDER BY created_at DESC
LIMIT 100;

-- CSV export (psql)
\copy (SELECT * FROM public.contacts) TO 'contacts.csv' WITH CSV HEADER;

-- Filter: France + non-null email
SELECT * FROM public.contacts
WHERE country = 'FR' AND email IS NOT NULL
ORDER BY created_at DESC;

-- Deduplicate by email (keep most recent)
SELECT DISTINCT ON (email) *
FROM public.contacts
WHERE email IS NOT NULL
ORDER BY email, created_at DESC;

-- Keep specific email domains
SELECT * FROM public.contacts
WHERE email LIKE '%@gmail.com' OR email LIKE '%@proton.me';
```

---

## 6) Quick recipes

**A) Quick static test**
- Proxies: **optional** ; JS: **** ; Concurrency **8** ; Delay **1.0s** ; 3–5 URLs

**B) SPA target (light anti-bot)**
- Proxies: **datacenter** (≥ 10 IP) ; JS: **** ; Concurrency **3** ; Delay **1.5s** ; Sticky **TTL 180s**

**C) Qualified emails (FR, recent)**
- Explorer filters: **Country=FR** + **email not null** + **last 30 days** → **CSV export**

---

## 7) Quick troubleshooting (FAQ)

**Dashboard down**
- `docker compose ps` ; `docker logs -f <dashboard>`

**Job pending/failed**
- Worker running ; Concurrency **↓**, Delay **↑** ; JS **ON** if SPA

**403/429**
- Rotation/Sticky ON ; Concurrency **↓**, Delay **↑** ; Cooldown ; consider residential pool

**Timeouts/JS**
- Timeout **↑** ; wait for selectors ; try **No-JS** if HTML fallback

**Empty export**
- Check **filters** ; DB pipelines ; rerun a **small test** job

---

## 8) Daily checklist 
- [ ] Proxies **OK** (green tests, rotation, latency)  
- [ ] **Proper settings** (JS, Concurrency, Delay, Retry)  
- [ ] **Scheduled** jobs configured  
- [ ] **Exports** verified (sample)  
- [ ] **Monitoring** reviewed (errors, latency, resources)
""").strip("\n")

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
FR_FILE = DOCS_DIR / "manuel_utilisation_fr.md"
EN_FILE = DOCS_DIR / "manual_en.md"

def maybe_load(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback

def make_toc(md_text: str):
    toc = []
    for line in md_text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = re.sub(r"[^a-z0-9\- ]", "", title.lower())
            anchor = re.sub(r"\s+", "-", anchor)
            toc.append((level, title, anchor))
    return toc

def inject_anchors(md_text: str):
    out = []
    for line in md_text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            title = m.group(2).strip()
            anchor = re.sub(r"[^a-z0-9\- ]", "", title.lower())
            anchor = re.sub(r"\s+", "-", anchor)
            out.append(f'<a id="{anchor}"></a>')
        out.append(line)
    return "\n".join(out)

def highlight_query(md_text: str, query: str) -> str:
    if not query:
        return md_text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f"**{m.group(0)}**", md_text)

st.sidebar.header("Help / Aide")
lang = st.sidebar.selectbox("Language / Langue", ["English", "Français"], index=0)
st.sidebar.caption("Switch language here to view the manual in EN or FR.")

md_fr = maybe_load(FR_FILE, MANUAL_MD_FR)
md_en = maybe_load(EN_FILE, MANUAL_MD_EN)
active_md = md_en if lang == "English" else md_fr

c1, c2 = st.columns([3, 2])
with c1:
    st.title(" User Guide — Utilisation / Usage")
with c2:
    st.download_button(
        "⬇️ Download / Télécharger (Markdown)",
        data=active_md,
        file_name="user_guide_usage.md" if lang == "English" else "mode_emploi_utilisation.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.caption("Tip / Astuce : use the Table of Contents or the search box below.")

query = st.text_input(
    " Search / Rechercher (e.g. proxy, export, 429, delay…) | (ex. proxy, export, 429, délai…)",
    placeholder="Type a keyword then press Enter / Tapez un mot-clé puis Entrée",
).strip()

toc = make_toc(active_md)
with st.expander(" Table of Contents / Sommaire", expanded=True):
    for level, title, anchor in toc:
        indent = "&nbsp;" * (level - 1) * 4
        st.markdown(f"{indent}• [{title}](#{anchor})", unsafe_allow_html=True)

render_md = highlight_query(active_md, query) if query else active_md
st.markdown(inject_anchors(render_md), unsafe_allow_html=True)

st.divider()
with st.expander(" Quick recap / Rappel express"):
    st.markdown("""
- **Proxies** → * Proxy Management / Gestion des Proxies* → Import → Test → Enable/Activer  
- **Job** → * Job Manager / Gestionnaire de Jobs* → URLs → JS (if SPA / si SPA) → Concurrency/Delay → ** START**  
- **Export** → * Contacts Explorer* → **⬇️ Export CSV** (or **⬇️ Export Emails**)  
- **Troubleshoot** → `docker compose ps`, `docker logs -f <service>`
    """)
