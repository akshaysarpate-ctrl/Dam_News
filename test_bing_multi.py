import urllib.parse
import requests
import sqlite3
from selectolax.parser import HTMLParser

conn = sqlite3.connect('dam_news.db')
cur = conn.cursor()
cur.execute('SELECT id, title, source FROM articles WHERE kind = "article" LIMIT 5')
rows = cur.fetchall()
conn.close()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept-Language': 'en-IN,en;q=0.9',
}

def resolve_via_bing_news(title, source):
    q = f'"{title}"'
    if source and source.lower() not in ('unknown source', 'google news'):
        q += f' {source}'
    url = f'https://www.bing.com/news/search?q={urllib.parse.quote(q)}'
    try:
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('a.title, div.news-card a, a[href^="http"]'):
                href = a.attributes.get('href', '')
                if href.startswith('http') and 'bing.com' not in href and 'msn.com' not in href and 'microsoft.com' not in href:
                    return href
    except Exception as e:
        pass

    # Try without quotes if exact quote didn't match
    q2 = f'{title} {source}'
    url2 = f'https://www.bing.com/news/search?q={urllib.parse.quote(q2)}'
    try:
        r = requests.get(url2, headers=headers, timeout=4)
        if r.status_code == 200:
            tree = HTMLParser(r.text)
            for a in tree.css('a.title, div.news-card a, a[href^="http"]'):
                href = a.attributes.get('href', '')
                if href.startswith('http') and 'bing.com' not in href and 'msn.com' not in href and 'microsoft.com' not in href:
                    return href
    except Exception as e:
        pass
    return None

for r in rows:
    link = resolve_via_bing_news(r[1], r[2])
    print(f"ID {r[0]} ({r[2]}): {link}")
