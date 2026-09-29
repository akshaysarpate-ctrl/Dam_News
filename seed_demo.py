#!/usr/bin/env python3
"""Fill the database with clearly-labelled FAKE demo rows so you can preview the interface.

    python seed_demo.py           add demo rows
    python seed_demo.py --clear   remove them again (real collected rows are not touched)
"""
import random
import sys
from datetime import datetime, timedelta, timezone

import db

SAMPLES = [
    ("en", "[DEMO] Dam breach sample story", "Sample Daily", "Maharashtra"),
    ("en", "[DEMO] Villages inundated after reservoir release, sample", "Sample Times", "Gujarat"),
    ("hi", "[डेमो] बांध टूटा, नमूना समाचार", "नमूना समाचार", "Madhya Pradesh"),
    ("hi", "[डेमो] बांध में दरार, खेत जलमग्न", "नमूना भारती", "Bihar"),
    ("mr", "[डेमो] धरण फुटले, नमुना बातमी", "नमुना लोकमत", "Maharashtra"),
    ("ta", "[டெமோ] அணை உடைப்பு மாதிரி செய்தி", "மாதிரி மலர்", "Tamil Nadu"),
    ("te", "[డెమో] చెరువు కట్ట తెగింది, నమూనా వార్త", "నమూనా ప్రభ", "Telangana"),
    ("kn", "[ಡೆಮೊ] ಕೆರೆ ಏರಿ ಒಡೆದು ಮಾದರಿ ಸುದ್ದಿ", "ಮಾದರಿ ವಾಣಿ", "Karnataka"),
    ("ml", "[ഡെമോ] അണക്കെട്ട് തകർന്നു, മാതൃകാ വാർത്ത", "മാതൃകാ ഭൂമി", "Kerala"),
    ("gu", "[ડેમો] ડેમમાં ગાબડું, નમૂનો સમાચાર", "નમૂનો સંદેશ", "Gujarat"),
    ("bn", "[ডেমো] বাঁধ ভেঙে গ্রাম প্লাবিত, নমুনা খবর", "নমুনা বার্তা", "West Bengal"),
]


def main():
    conn = db.connect()
    if "--clear" in sys.argv:
        n = conn.execute("DELETE FROM articles WHERE collector = 'demo'").rowcount
        conn.commit()
        print(f"Removed {n} demo rows.")
        return
    random.seed(7)
    now = datetime.now(timezone.utc)
    added = 0
    for i in range(70):
        lang, title, source, state = random.choice(SAMPLES)
        # more recent than old, with a couple of busy weeks so the strip has some shape
        age = int(random.triangular(0, 360, 20))
        when = now - timedelta(days=age, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        video = random.random() < 0.18
        added += db.insert_article(conn, {
            "kind": "video" if video else "article",
            "title": f"{title} {i + 1}",
            "url": f"https://example.com/demo/{i + 1}",
            "source": "Sample Channel" if video else source, "language": lang,
            "published_at": db.utc_iso(when),
            "snippet": "This is fake demo text used only to preview the layout." if i % 3 == 0 else "",
            "thumbnail": "", "state": state, "score": 80,
            "status": "maybe" if i % 11 == 0 else "relevant", "collector": "demo",
        })
    conn.commit()
    print(f"Added {added} demo rows. Run  python seed_demo.py --clear  to remove them.")


if __name__ == "__main__":
    main()
