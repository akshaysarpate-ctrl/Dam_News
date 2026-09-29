import requests
import urllib.parse
from selectolax.parser import HTMLParser

def test_resolve(title, source):
    q = f'"{title}" {source}'
    u = f'https://www.google.com/search?q={urllib.parse.quote(q)}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    }
    r = requests.get(u, headers=headers, timeout=5)
    print('Search status:', r.status_code)
    tree = HTMLParser(r.text)
    links = []
    for a in tree.css('a'):
        href = a.attributes.get('href', '')
        if href.startswith('/url?q='):
            real = href.split('/url?q=')[1].split('&')[0]
            real = urllib.parse.unquote(real)
            if real.startswith('http') and 'google.com' not in real:
                links.append(real)
        elif href.startswith('http') and 'google.com' not in href and 'gstatic.com' not in href:
            links.append(href)
    print('Found direct links:', links[:3])

test_resolve('Water level in dams rises after heavy rainfall in Maharashtra', 'The Hindu')
