import json, os
with open(os.path.join(os.getcwd(),'config','languages.json'),'r',encoding='utf-8') as f:
    LANGCFG=json.load(f)
def page_lang_from_text(text:str):
    t=(text or '').lower()
    for code,markers in LANGCFG.get("language_markers",{}).items():
        for m in markers:
            if m.lower() in t: return code
    return None
def matches_keywords(text:str, lang:str, theme:str):
    t=(text or '').lower()
    kws=LANGCFG.get("keywords",{}).get(lang or "",{}).get(theme or "",[])
    if not kws: return True
    for k in kws:
        if k.lower() in t: return True
    return False
