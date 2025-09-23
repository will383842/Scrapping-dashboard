import re, urllib.parse
EMAIL_RE=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_RE=re.compile(r'\+\d[\d\s().-]{5,}')
def find_emails(text:str): return list(dict.fromkeys(EMAIL_RE.findall(text or "")))
def find_phones(text:str): return list(dict.fromkeys(PHONE_RE.findall(text or "")))
def absolutize(base,href): return urllib.parse.urljoin(base, href or "")
def get_domain(url:str):
    try:
        return urllib.parse.urlparse(url).netloc
    except Exception:
        return None
def guess_name_from_text(text:str):
    if not text: return None
    m=re.search(r'\b([A-Z][a-z]{2,})\s+([A-Z][a-z]{2,})\b', text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return None
