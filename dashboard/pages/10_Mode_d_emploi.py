# pages/10__Mode_d_emploi.py
from pathlib import Path
import re
import streamlit as st



ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
FR_FILE = DOCS_DIR / "manuel_utilisation_fr.md"
EN_FILE = DOCS_DIR / "manual_en.md"

def load_manual(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

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

st.sidebar.header("Aide / Help")
lang = st.sidebar.selectbox("Langue / Language", ["Français", "English"], index=0)

md_fr = load_manual(FR_FILE)
md_en = load_manual(EN_FILE)

active_md = md_fr if lang == "Français" or not md_en else md_en

c1, c2 = st.columns([3, 2])
with c1:
    st.title(" Mode d'emploi / User Manual")
with c2:
    st.download_button(
        "⬇️ Télécharger (Markdown)" if lang == "Français" else "⬇️ Download (Markdown)",
        data=active_md,
        file_name="mode_emploi.md" if lang == "Français" else "user_manual.md",
        mime="text/markdown",
        use_container_width=True,
    )

st.caption("Astuce / Tip: utilisez la recherche pour surligner les occurrences.")

q = st.text_input(
    "Rechercher / Search",
    placeholder="proxy, export, 429, délai… / proxy, export, 429, delay…"
).strip()

toc = make_toc(active_md)
with st.expander(" Sommaire / Table of Contents", expanded=True):
    for level, title, anchor in toc:
        indent = "&nbsp;" * (level - 1) * 4
        st.markdown(f"{indent}• [{title}](#{anchor})", unsafe_allow_html=True)

render_md = highlight_query(active_md, q) if q else active_md
st.markdown(inject_anchors(render_md), unsafe_allow_html=True)

st.divider()
with st.expander(" Rappel express / Quick recap"):
    st.markdown("""
- **Proxies** → * Gestion des Proxies / Proxy Management* → Import → Test → Activer/Enable  
- **Job** → * Gestionnaire de Jobs / Job Manager* → URLs → JS (si SPA / if SPA) → Concurrence/Delay → ** START**  
- **Export** → * Explorateur de Contacts / Contacts Explorer* → **⬇️ Export CSV**  
- **Dépannage / Troubleshoot** → `docker compose ps`, `docker logs -f <service>`
    """)
