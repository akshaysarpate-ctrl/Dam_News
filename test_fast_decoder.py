import requests
import re
import sqlite3
from googlenewsdecoder._parse import build_batchexecute_body, parse_batchexecute

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}

def decode_token(token):
    try:
        r = requests.get(f'https://news.google.com/articles/{token}?hl=en-IN&gl=IN&ceid=IN:en', headers=headers, timeout=4)
        if r.status_code != 200:
            return None
        sg = re.findall(r'data-n-a-sg="([^"]+)"', r.text)
        ts = re.findall(r'data-n-a-ts="([^"]+)"', r.text)
        if not (sg and ts):
            return None
        body = build_batchexecute_body([('0', token, ts[0], sg[0])])
        pr = requests.post(
            'https://news.google.com/_/DotsSplashUi/data/batchexecute',
            headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'User-Agent': headers['User-Agent']},
            data=body,
            timeout=4
        )
        if pr.status_code != 200:
            return None
        pairs = parse_batchexecute(pr.text)
        if pairs and pairs[0][1] and pairs[0][1].startswith('http'):
            return pairs[0][1]
    except Exception as e:
        return None
    return None

c = sqlite3.connect('dam_news.db')
rows = c.execute('SELECT id, source, url FROM articles WHERE id >= 7092 LIMIT 10').fetchall()
c.close()

for r in rows:
    tok = r[2].split('/')[-1].split('?')[0]
    real_url = decode_token(tok)
    print(r[0], '|', r[1], '-->', real_url)
