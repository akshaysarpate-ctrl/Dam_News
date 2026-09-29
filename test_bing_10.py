import sqlite3
import urllib.parse
import requests
from selectolax.parser import HTMLParser

conn = sqlite3.connect('dam_news.db')
cur = conn.cursor()
cur.execute('SELECT id, title, source, url FROM articles WHERE kind = "article" ORDER BY id DESC LIMIT 10')
rows = cur.fetchall()
conn.close()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept-Language': 'en-IN,en;q=0.9',
}

def resolve_bing_news(title, source):
    # Try with quotes first
    q = f'"{title}"'
    if source and source.lower() not in ('unknown source', 'google news'):
        q += f' {source}'
    url = f'https://www.bing.com/news/search?q={urllib.parse.quote(q)}'
    try:
        r = requests.get(url, headers=headers, timeout=3.5)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('a.title, div.news-card a, a[href^="http"]'):
                h = a.attributes.get('href', '')
                if h.startswith('http') and not any(d in h for d in ('bing.com', 'msn.com', 'microsoft.com')):
                    return h
    except Exception:
        pass

    # Try relaxed without quotes
    q2 = f'{title} {source}'
    url2 = f'https://www.bing.com/news/search?q={urllib.parse.quote(q2)}'
    try:
        r = requests.get(url2, headers=headers, timeout=3.5)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('a.title, div.news-card a, a[href^="http"]'):
                h = a.attributes.get('href', '')
                if h.startswith('http') and not any(d in h for d in ('bing.com', 'msn.com', 'microsoft.com')):
                    return h
    except Exception:
        pass

    return None

for r in rows:
    link = resolve_bing_news(r[1], r[2])
    print(f"ID {r[0]} | {r[2][:15]} -> {link}")
