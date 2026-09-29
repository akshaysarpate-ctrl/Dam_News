"""Load NRSD2026.xlsx into SQLite table nrsd_dams in dam_news.db with precise coordinate parsing."""
import os
import re
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dam_news.db")
EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "NRSD2026.xlsx")

def clean_val(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return str(v).strip()

def parse_coordinates(raw):
    """Parse raw coordinate strings like '11° 37\\' 28\"N \\n92° 39\\' 33\"E' into (lat_dec, lng_dec, formatted_str)."""
    if not raw:
        return None, None, ""
    
    # Normalize characters
    s = str(raw).strip()
    s = s.replace("\ufffd", "°").replace("\xb0", "°").replace("o", "°")
    s = s.replace("''", "'").replace('""', '"').replace("\n", " ").strip()

    # Matches degrees, minutes, seconds and direction (N/S/E/W)
    pattern = r'(\d+(?:\.\d+)?)\s*°?\s*(\d+(?:\.\d+)?)\s*[\'’`]?\s*([0-9.]+)?\s*[\"”]?\s*([NSEW])'
    matches = re.findall(pattern, s, re.I)
    
    if len(matches) >= 2:
        parts = []
        clean_parts = []
        for m in matches[:2]:
            d = float(m[0])
            m_val = float(m[1]) if m[1] else 0.0
            s_val = float(m[2]) if m[2] else 0.0
            direction = m[3].upper()
            dec = d + m_val / 60.0 + s_val / 3600.0
            if direction in ('S', 'W'):
                dec = -dec
            parts.append(dec)
            clean_parts.append(f"{int(d)}° {int(m_val)}' {s_val:g}\" {direction}")

        # In India, Latitude is ~8 to 37 N, Longitude is ~68 to 98 E
        lat, lng = parts[0], parts[1]
        formatted = ", ".join(clean_parts)
        if lat > lng:
            lat, lng = lng, lat
            formatted = f"{clean_parts[1]}, {clean_parts[0]}"
        return round(lat, 6), round(lng, 6), formatted

    # Fallback to cleaned raw string
    cleaned = re.sub(r'\s+', ' ', s)
    return None, None, cleaned

def run():
    print(f"Reading {EXCEL_PATH}...")
    df = pd.read_excel(EXCEL_PATH, sheet_name=0)
    print(f"Read {len(df)} rows. Setting up database...")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS nrsd_dams")
    conn.execute("""
        CREATE TABLE nrsd_dams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sr_no INTEGER,
            pic TEXT,
            name TEXT NOT NULL,
            sdso_name TEXT,
            state TEXT,
            dam_owner TEXT,
            lat_long TEXT,
            lat_dec REAL,
            lng_dec REAL,
            year_commission TEXT,
            type_of_dam TEXT,
            river_basin TEXT,
            river TEXT,
            district TEXT,
            seismic_zone TEXT,
            height_m TEXT,
            length_m TEXT,
            gross_storage_mcm TEXT,
            effective_storage_mcm TEXT,
            spillway_capacity_cumec TEXT,
            purpose TEXT
        )
    """)
    conn.execute("CREATE INDEX idx_nrsd_name ON nrsd_dams(name COLLATE NOCASE)")
    conn.execute("CREATE INDEX idx_nrsd_pic ON nrsd_dams(pic)")
    conn.execute("CREATE INDEX idx_nrsd_state ON nrsd_dams(state COLLATE NOCASE)")

    rows = []
    for _, r in df.iterrows():
        name = clean_val(r.get("Name of Dam (3)", ""))
        if not name:
            continue
        raw_coords = clean_val(r.get("Latitude/ Longitude(7)", ""))
        lat_dec, lng_dec, formatted_coords = parse_coordinates(raw_coords)

        rows.append((
            clean_val(r.get("Sr.No. (1)", "")),
            clean_val(r.get("PIC (2)", "")),
            name,
            clean_val(r.get("SDSO Name (4)", "")),
            clean_val(r.get("State(5)", "")),
            clean_val(r.get("Dam Owner(6)", "")),
            formatted_coords or raw_coords,
            lat_dec,
            lng_dec,
            clean_val(r.get("Year of Commission (8)", "")),
            clean_val(r.get("Type of Dam(9)", "")),
            clean_val(r.get("River Basin(10)", "")),
            clean_val(r.get("River (11)", "")),
            clean_val(r.get("District(12)", "")),
            clean_val(r.get("Seismic Zone (13)", "")),
            clean_val(r.get("Height above Lowest Foundation Level(m) (14)", "")),
            clean_val(r.get("Dam Length(m) (15)", "")),
            clean_val(r.get("Gross Storage Capacity(MCM) (16)", "")),
            clean_val(r.get("Effective Storage Capacity(MCM) (17)", "")),
            clean_val(r.get("Designed Spillway Capacity(m3/s) (18)", "")),
            clean_val(r.get("Purpose (19)", "")),
        ))

    conn.executemany("""
        INSERT INTO nrsd_dams (
            sr_no, pic, name, sdso_name, state, dam_owner, lat_long,
            lat_dec, lng_dec, year_commission, type_of_dam, river_basin,
            river, district, seismic_zone, height_m, length_m,
            gross_storage_mcm, effective_storage_mcm, spillway_capacity_cumec, purpose
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM nrsd_dams").fetchone()[0]
    coords_count = conn.execute("SELECT COUNT(*) FROM nrsd_dams WHERE lat_dec IS NOT NULL").fetchone()[0]
    conn.close()
    print(f"Successfully loaded {count} dams ({coords_count} with precise decimal coordinates) into {DB_PATH}.")

if __name__ == "__main__":
    run()
