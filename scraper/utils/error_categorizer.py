
import json
from pathlib import Path
from typing import Dict, Any

def load_rules(path: str = "config/error_rules.json") -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def categorize(error: Exception=None, status_code: int=None, message: str="") -> str:
    rules = load_rules()
    if status_code:
        if 500 <= status_code < 600:
            return "http_5xx"
        if 400 <= status_code < 500:
            return "http_4xx"
    # string matching fallback
    msg = message.lower()
    if error:
        msg += " " + str(error).lower()
    for key, cat in rules.get("contains", {}).items():
        if key.lower() in msg:
            return cat
    return "unknown"
