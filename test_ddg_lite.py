import urllib.parse
import requests
from selectolax.parser import HTMLParser

# Test DuckDuckGo Lite / HTML
q = '"Water level in dams rises after heavy rainfall in Maharashtra" The Hindu'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
}
r = requests.post('https://lite.duckduckgo.com/lite/', data={'q': q}, headers=headers, timeout=5)
print('DDG Lite status:', r.status_code)
tree = HTMLParser(r.text)
for a in tree.css('a.result-link'):
    print('DDG Link:', a.attributes.get('href'))
