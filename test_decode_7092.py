import requests
import re
import sqlite3
from googlenewsdecoder._parse import build_batchexecute_body, parse_batchexecute

c = sqlite3.connect('dam_news.db')
u = c.execute('SELECT url FROM articles WHERE id = 7092').fetchone()[0]
c.close()
token = u.split('/')[-1].split('?')[0]
print('Token:', token[:40])

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}
r = requests.get(f'https://news.google.com/articles/{token}?hl=en-IN&gl=IN&ceid=IN:en', headers=headers, timeout=5)
print('status:', r.status_code, 'final url:', r.url[:60])
sg = re.findall(r'data-n-a-sg="([^"]+)"', r.text)
ts = re.findall(r'data-n-a-ts="([^"]+)"', r.text)
print('sg:', sg, 'ts:', ts)
if sg and ts:
    body = build_batchexecute_body([('0', token, ts[0], sg[0])])
    pr = requests.post('https://news.google.com/_/DotsSplashUi/data/batchexecute', headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'User-Agent': headers['User-Agent']}, data=body, timeout=5)
    print('Decoded:', parse_batchexecute(pr.text))
