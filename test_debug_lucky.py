import requests
import urllib.parse
import util

q = '"Dam breach has Jodhpur on alert" Mumbai Mirror'
u = f'https://www.google.com/search?q={urllib.parse.quote(q)}&btnI=1'
r = requests.get(u, headers=util.HEADERS, allow_redirects=False, timeout=5)
print('status:', r.status_code, 'location:', r.headers.get('location'))
