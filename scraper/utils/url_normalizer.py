
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def normalize(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "http"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    # sort query params
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunparse((scheme, netloc, path, "", query, ""))
