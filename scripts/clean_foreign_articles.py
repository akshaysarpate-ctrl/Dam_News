import sqlite3
import re

conn = sqlite3.connect("dam_news.db")
c = conn.cursor()

FOREIGN_DAMS = [
    "three gorges", "hoover dam", "oroville", "kakhovka", "nova kakhovka", "kariba", "aswan",
    "tarbela", "mangla", "diamer", "bhasha", "brumadinho", "mariana dam", "bento rodrigues",
    "matai'an", "banqiao", "itaipu", "tucurui", "guri dam", "grand renaissance", "gerd dam",
    "bagre dam", "luzon", "fontana dam", "rutland water", "fujinuma", "kunfusi", "lac qui parle",
    "fukushima", "chornobyl", "chernobyl", "dagestan", "moscow", "kyiv", "kherson",
    "alaska", "michigan", "arizona", "sultan property", "lake oroville", "lake mead",
    "mississippi", "tennessee valley", "tva's", "colorado river", "potomac",
]
foreign_dam_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in FOREIGN_DAMS) + r")\b", re.IGNORECASE)

FOREIGN_COUNTRIES = [
    "china", "chinese", "pakistan", "pakistani", "ukraine", "ukrainian", "russia", "russian",
    "brazil", "brazilian", "united states", "usa", "america", "american", "california", "texas",
    "florida", "australia", "australian", "canada", "canadian", "japan", "japanese", "taiwan",
    "taiwanese", "indonesia", "indonesian", "philippines", "turkey", "turkish", "syria", "syrian",
    "iraq", "iran", "mexico", "colombia", "argentina", "spain", "germany", "italy",
    "britain", "british", "england", "scotland", "egypt", "ethiopia", "kenya", "sudan", "zambia",
    "zimbabwe", "ghana", "myanmar", "burma", "thailand", "vietnam", "laos", "cambodia", "kazakhstan",
]
foreign_country_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in FOREIGN_COUNTRIES) + r")\b", re.IGNORECASE)

INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa",
    "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
    "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura",
    "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir", "ladakh",
    "orissa", "j&k", "jammu & kashmir", "puducherry", "chandigarh"
]
state_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in INDIAN_STATES) + r")\b", re.IGNORECASE)

INDIAN_CITIES = [
    "mumbai", "pune", "nagpur", "nashik", "aurangabad", "chhatrapati sambhajinagar", "kolhapur", "solapur", "thane",
    "ahmedabad", "surat", "vadodara", "rajkot", "bhavnagar", "jamnagar", "junagadh", "gandhinagar", "morbi", "kutch",
    "jaipur", "jodhpur", "kota", "bikaner", "ajmer", "udaipur", "bhilwara", "alwar", "sikar",
    "bhopal", "indore", "gwalior", "jabalpur", "ujjain", "sagar", "dewas", "satna", "rewa",
    "patna", "gaya", "bhagalpur", "muzaffarpur", "purnia", "darbhanga", "bihar sharif",
    "lucknow", "kanpur", "ghaziabad", "agra", "meerut", "varanasi", "prayagraj", "bareilly", "aligarh", "moradabad", "saharanpur", "gorakhpur", "noida", "jhansi",
    "dehradun", "haridwar", "rishikesh", "roorkee", "haldwani", "rudrapur", "nainital", "tehri", "uttarkashi", "chamoli",
    "shimla", "mandi", "dharamshala", "solan", "kullu", "manali", "bilaspur", "chamba", "kangra", "kinnaur",
    "srinagar", "jammu", "anantnag", "baramulla", "udhampur", "leh", "kargil", "kishtwar", "doda", "ramban", "reasi",
    "bengaluru", "bangalore", "mysuru", "mysore", "hubballi", "dharwad", "mangaluru", "mangalore", "belagavi", "belgaum", "kalaburagi", "davanagere", "ballari", "vijayapura", "shivamogga", "shimoga", "tumakuru", "raichur", "bidar", "hassan",
    "hyderabad", "warangal", "nizamabad", "khammam", "karimnagar", "ramagundam", "mahbubnagar", "nalgonda", "adilabad", "suryapet",
    "chennai", "coimbatore", "madurai", "tiruchirappalli", "salem", "tirunelveli", "tiruppur", "erode", "vellore", "thoothukudi", "dindigul", "thanjavur",
    "thiruvananthapuram", "kochi", "cochin", "kozhikode", "calicut", "thrissur", "kollam", "palakkad", "alappuzha", "malappuram", "kannur", "kottayam", "idukki", "wayanad", "pathanamthitta", "kasaragod",
    "bhubaneswar", "cuttack", "rourkela", "berhampur", "sambalpur", "puri", "balasore", "bhadrak", "baripada",
    "kolkata", "howrah", "asansol", "siliguri", "durgapur", "bardhaman", "malda", "kharagpur", "habra",
    "guwahati", "silchar", "dibrugarh", "jorhat", "nagaon", "tinsukia", "tezpur",
    "raipur", "bhilai", "bilaspur", "korba", "durg", "rajnandgaon", "jagdalpur",
    "ranchi", "jamshedpur", "dhanbad", "bokaro", "deoghar", "hazaribagh",
    "ludhiana", "amritsar", "jalandhar", "patiala", "bathinda", "mohali", "pathankot", "hoshiarpur",
    "faridabad", "gurugram", "gurgaon", "panipat", "ambala", "yamunanagar", "rohtak", "hisar", "karnal", "sonipat", "panchkula"
]
city_re = re.compile(r"\b(" + "|".join(re.escape(c) for c in INDIAN_CITIES) + r")\b", re.IGNORECASE)

INDIAN_RIVERS = [
    "ganga", "ganges", "yamuna", "godavari", "krishna", "narmada", "mahanadi", "cauvery", "kaveri",
    "brahmaputra", "tapi", "tapti", "sabarmati", "mahi", "periyar", "pennar", "subarnarekha",
    "beas", "sutlej", "ravi", "chenab", "jhelum", "tungabhadra", "bhima", "koyna", "vaigai",
    "damodar", "teesta", "chambal", "betwa", "ken river", "son river", "ghaghara", "gandak", "kosi",
    "bhagirathi", "alaknanda", "mandakini", "pinakini", "sharavathi", "netravati", "chalakudy", "bharathapuzha",
    "indus", "dhanasari", "subansiri", "barak", "kopili", "manas", "aravali"
]
river_re = re.compile(r"\b(" + "|".join(re.escape(r) for r in INDIAN_RIVERS) + r")\b", re.IGNORECASE)

india_word_re = re.compile(r"\b(india|indian|bharat|hindustan|cwc|ndsa|sdso)\b", re.IGNORECASE)

# Distinct NRSD dam names with length >= 4
raw_names = [r[0].strip() for r in c.execute("SELECT DISTINCT name FROM nrsd_dams").fetchall() if r[0]]
nrsd_set = {n.lower() for n in raw_names if len(n) >= 4 and not n.isdigit()}

rows = c.execute("SELECT id, title, snippet, state, district, dam_name, language, source FROM articles").fetchall()

to_delete = []

for r in rows:
    aid, title, snippet, state, district, dam, lang, source = r
    text = f"{title} {snippet}".lower()
    
    # Check 1: Explicit Foreign Dam
    if foreign_dam_re.search(text):
        to_delete.append(aid)
        continue
        
    has_state = bool(state or state_re.search(text))
    has_city = bool(city_re.search(text))
    has_river = bool(river_re.search(text))
    
    # Check if dam matches NRSD
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
    has_dam = bool(dam) or any(w in nrsd_set for w in words)
    has_india = bool(india_word_re.search(text))
    has_indian_anchor = has_state or has_city or has_river or has_dam or has_india

    # Check 2: Foreign Country mentioned without strong Indian dam/state
    fc_match = foreign_country_re.search(text)
    if fc_match:
        if not (has_state or has_dam):
            to_delete.append(aid)
            continue
        # Even with Indian anchor, if title is about foreign country disaster
        if fc_match.group(0) in ["china", "pakistan", "ukraine", "brazil", "russia", "myanmar", "indonesia"]:
            if any(w in title.lower() for w in ["mega-dam", "dam project", "rains, dam breach", "floods hit", "spencer", "vale's", "dagestan", "taiwan", "mataian", "fujinuma", "dyke"]):
                to_delete.append(aid)
                continue

    # Check 3: For English articles, must have AT LEAST ONE Indian anchor
    if lang == "en":
        if not has_indian_anchor:
            to_delete.append(aid)
            continue

print(f"Total articles in DB: {len(rows)}")
print(f"Articles to purge: {len(to_delete)}")

if to_delete:
    c.executemany("DELETE FROM articles WHERE id = ?", [(aid,) for aid in to_delete])
    conn.commit()
    print(f"Successfully deleted {len(to_delete)} foreign/unrelated articles from database.")
    
# Remaining count
remaining = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
print(f"Remaining clean Indian dam articles: {remaining}")
conn.close()
