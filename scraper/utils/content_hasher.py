
import hashlib
def content_hash(text: str) -> str:
    if text is None:
        text = ""
    return hashlib.sha256(text.encode('utf-8', errors='ignore')).hexdigest()
