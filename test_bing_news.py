import urllib.parse
import base64
import requests
from selectolax.parser import HTMLParser

q = urllib.parse.quote('Water level in dams rises after heavy rainfall in Maharashtra The Hindu')
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Accept-Language': 'en-IN,en;q=0.9',
}
r = requests.get(f'https://www.bing.com/news/search?q={q}', headers=headers, timeout=5)
print('Bing News status:', r.status_code)
tree = HTMLParser(r.text)
for a in tree.css('a.title, a[href*="http"]'):
    href = a.attributes.get('href', '')
    if 'thehindu.com' in href or 'indiatimes.com' in href:
        print('Found direct link in Bing News:', href)
        break
else:
    # Try web search
    r2 = requests.get(f'https://www.bing.com/search?q={q}', headers=headers, timeout=5)
    print('Bing Web status:', r2.status_code)
    tree2 = HTMLParser(r2.text)
    for a in tree2.css('li.b_algo h2 a'):
        href = a.attributes.get('href', '')
        if 'u=a1' in href:
            raw = href.split('u=a1')[1].split('&')[0]
            try:
                dec = base64.b64decode(raw + '===').decode('utf-8', errors='ignore')
                print('Decoded from Bing Web:', dec)
                break
            except Exception:
                pass
        elif href.startswith('http') and 'bing.com' not in href:
            print('Direct link from Bing Web:', href)
            break
