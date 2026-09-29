"""Load NRSD2026.xlsx into SQLite table nrsd_dams in dam_news.db"""
import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dam_news.db")
EXCEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "NRSD2026.xlsx")

def clean_val(v):
    if pd.isna(v):
        return ""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    s = str(v).strip()
    s = s.replace("\ufffd", "°")
    return s

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
        rows.append((
            clean_val(r.get("Sr.No. (1)", "")),
            clean_val(r.get("PIC (2)", "")),
            name,
            clean_val(r.get("SDSO Name (4)", "")),
            clean_val(r.get("State(5)", "")),
            clean_val(r.get("Dam Owner(6)", "")),
            clean_val(r.get("Latitude/ Longitude(7)", "")),
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
            year_commission, type_of_dam, river_basin, river, district,
            seismic_zone, height_m, length_m, gross_storage_mcm,
            effective_storage_mcm, spillway_capacity_cumec, purpose
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM nrsd_dams").fetchone()[0]
    conn.close()
    print(f"Successfully loaded {count} dams into nrsd_dams table in {DB_PATH}.")

if __name__ == "__main__":
    run()
