import urllib.parse
import base64
import requests
from selectolax.parser import HTMLParser

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept-Language': 'en-IN,en;q=0.9',
}

def resolve_direct(title: str, source: str) -> str:
    # 1. Try Bing News Search
    q = f'"{title}"'
    if source and source.lower() not in ('unknown source', 'google news'):
        q += f' {source}'
    
    try:
        url = f'https://www.bing.com/news/search?q={urllib.parse.quote(q)}'
        r = requests.get(url, headers=HEADERS, timeout=3.5)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('a.title, div.news-card a, a[href^="http"]'):
                href = a.attributes.get('href', '')
                if href.startswith('http') and 'bing.com' not in href and 'msn.com' not in href and 'microsoft.com' not in href:
                    return href
    except Exception:
        pass

    # 2. Try Bing Web Search with base64 decoding
    try:
        url = f'https://www.bing.com/search?q={urllib.parse.quote(title + " " + source)}'
        r = requests.get(url, headers=HEADERS, timeout=3.5)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('li.b_algo h2 a, a[href*="u=a1"]'):
                href = a.attributes.get('href', '')
                if 'u=a1' in href:
                    raw = href.split('u=a1')[1].split('&')[0]
                    try:
                        dec = base64.b64decode(raw + '===').decode('utf-8', errors='ignore')
                        if dec.startswith('http') and 'bing.com' not in dec and 'microsoft.com' not in dec:
                            return dec
                    except Exception:
                        pass
                elif href.startswith('http') and 'bing.com' not in href and 'microsoft.com' not in href:
                    return href
    except Exception:
        pass

    return ""

test_cases = [
    ("Dam breach has Jodhpur on alert", "Mumbai Mirror"),
    ("Tamil Nadu: Mettur dam level falls as delta farmers wait for water to plant samba paddy", "thehansindia.com"),
    ("Water level in dams rises after heavy rainfall in Maharashtra", "The Hindu"),
    ("Bhakra dam water level reaches season high", "The Tribune"),
]

for t, s in test_cases:
    print(f"{s} -> {resolve_direct(t, s)}")
