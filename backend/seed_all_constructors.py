"""
Historical F1 Constructors and Seasons Seeder
=============================================
Seeds comprehensive historical F1 constructors across all eras (1950-2026)
with their official factory headquarters base locations and links them to
seasons so users can filter by any selected year.
"""

import sys
import os
import requests

sys.path.insert(0, os.path.dirname(__file__))
from database import get_db_connection

# Comprehensive dictionary of F1 constructor headquarters across all eras
CONSTRUCTOR_LOCATIONS_MAP = {
    # Modern Era (2020-2026)
    "red_bull": ("Red Bull Racing", "Austrian", "Milton Keynes, United Kingdom"),
    "red bull": ("Red Bull Racing", "Austrian", "Milton Keynes, United Kingdom"),
    "red bull racing": ("Red Bull Racing", "Austrian", "Milton Keynes, United Kingdom"),
    "ferrari": ("Ferrari", "Italian", "Maranello, Italy"),
    "mclaren": ("McLaren", "British", "Woking, United Kingdom"),
    "mercedes": ("Mercedes", "German", "Brackley, United Kingdom"),
    "aston_martin": ("Aston Martin", "British", "Silverstone, United Kingdom"),
    "aston martin": ("Aston Martin", "British", "Silverstone, United Kingdom"),
    "alpine": ("Alpine F1 Team", "French", "Enstone, United Kingdom"),
    "alpine f1 team": ("Alpine F1 Team", "French", "Enstone, United Kingdom"),
    "williams": ("Williams", "British", "Grove, United Kingdom"),
    "rb": ("RB F1 Team", "Italian", "Faenza, Italy"),
    "rb f1 team": ("RB F1 Team", "Italian", "Faenza, Italy"),
    "racing bulls": ("RB F1 Team", "Italian", "Faenza, Italy"),
    "alphatauri": ("AlphaTauri", "Italian", "Faenza, Italy"),
    "toro_rosso": ("Toro Rosso", "Italian", "Faenza, Italy"),
    "toro rosso": ("Toro Rosso", "Italian", "Faenza, Italy"),
    "haas": ("Haas F1 Team", "American", "Kannapolis, North Carolina, USA"),
    "haas f1 team": ("Haas F1 Team", "American", "Kannapolis, North Carolina, USA"),
    "sauber": ("Sauber", "Swiss", "Hinwil, Switzerland"),
    "kick_sauber": ("Kick Sauber", "Swiss", "Hinwil, Switzerland"),
    "kick sauber": ("Kick Sauber", "Swiss", "Hinwil, Switzerland"),
    "audi": ("Audi", "German", "Hinwil, Switzerland"),
    "cadillac": ("Cadillac F1 Team", "American", "Fishers, Indiana, USA"),
    "cadillac f1 team": ("Cadillac F1 Team", "American", "Fishers, Indiana, USA"),

    # 2010s & 2000s
    "racing_point": ("Racing Point", "British", "Silverstone, United Kingdom"),
    "racing point": ("Racing Point", "British", "Silverstone, United Kingdom"),
    "force_india": ("Force India", "Indian", "Silverstone, United Kingdom"),
    "force india": ("Force India", "Indian", "Silverstone, United Kingdom"),
    "renault": ("Renault", "French", "Enstone, United Kingdom"),
    "lotus_f1": ("Lotus F1 Team", "British", "Enstone, United Kingdom"),
    "lotus f1": ("Lotus F1 Team", "British", "Enstone, United Kingdom"),
    "lotus_racing": ("Lotus Racing", "Malaysian", "Hingham, Norfolk, United Kingdom"),
    "caterham": ("Caterham", "Malaysian", "Leafield, Oxfordshire, United Kingdom"),
    "manor": ("Manor Racing", "British", "Banbury, Oxfordshire, United Kingdom"),
    "marussia": ("Marussia", "Russian", "Banbury, Oxfordshire, United Kingdom"),
    "virgin": ("Virgin", "British", "Dinnington, South Yorkshire, UK"),
    "hrt": ("HRT", "Spanish", "Madrid, Spain"),
    "bmw_sauber": ("BMW Sauber", "German", "Hinwil, Switzerland"),
    "bmw sauber": ("BMW Sauber", "German", "Hinwil, Switzerland"),
    "brawn": ("Brawn GP", "British", "Brackley, United Kingdom"),
    "brawn gp": ("Brawn GP", "British", "Brackley, United Kingdom"),
    "toyota": ("Toyota", "Japanese", "Cologne, Germany"),
    "honda": ("Honda", "Japanese", "Brackley, United Kingdom"),
    "super_aguri": ("Super Aguri", "Japanese", "Leafield, Oxfordshire, UK"),
    "super aguri": ("Super Aguri", "Japanese", "Leafield, Oxfordshire, UK"),
    "spyker": ("Spyker", "Dutch", "Silverstone, United Kingdom"),
    "midland": ("Midland", "Russian", "Silverstone, United Kingdom"),
    "mf1": ("MF1 Racing", "Russian", "Silverstone, United Kingdom"),
    "bar": ("BAR", "British", "Brackley, United Kingdom"),
    "jaguar": ("Jaguar", "British", "Milton Keynes, United Kingdom"),
    "jordan": ("Jordan", "Irish", "Silverstone, United Kingdom"),
    "arrows": ("Arrows", "British", "Leafield, Oxfordshire, United Kingdom"),
    "footwork": ("Footwork", "British", "Milton Keynes, United Kingdom"),
    "prost": ("Prost", "French", "Guyancourt, France"),
    "stewart": ("Stewart", "British", "Milton Keynes, United Kingdom"),
    "minardi": ("Minardi", "Italian", "Faenza, Italy"),

    # 1990s & 1980s
    "benetton": ("Benetton", "Italian", "Enstone, Oxfordshire, United Kingdom"),
    "tyrrell": ("Tyrrell", "British", "Ockham, Surrey, United Kingdom"),
    "ligier": ("Ligier", "French", "Magny-Cours, France"),
    "forti": ("Forti", "Italian", "Alessandria, Italy"),
    "pacific": ("Pacific", "British", "Thetford, Norfolk, United Kingdom"),
    "simtek": ("Simtek", "British", "Banbury, Oxfordshire, United Kingdom"),
    "larrousse": ("Larrousse", "French", "Antony, Paris, France"),
    "dallara": ("Dallara", "Italian", "Varano de' Melegari, Parma, Italy"),
    "scuderia_italia": ("Scuderia Italia", "Italian", "Brescia, Italy"),
    "fondmetal": ("Fondmetal", "Italian", "Palazzolo sull'Oglio, Italy"),
    "osella": ("Osella", "Italian", "Volpiano, Turin, Italy"),
    "ags": ("AGS", "French", "Gonfaron, France"),
    "coloni": ("Coloni", "Italian", "Passignano sul Trasimeno, Italy"),
    "eurobrun": ("EuroBrun", "Italian", "Senago, Milan, Italy"),
    "onyx": ("Onyx", "British", "Littlehampton, West Sussex, UK"),
    "rial": ("Rial", "German", "Fußgönheim, Germany"),
    "zakspeed": ("Zakspeed", "German", "Niederzissen, Germany"),
    "march": ("March", "British", "Bicester, Oxfordshire, United Kingdom"),
    "leyton_house": ("Leyton House", "British", "Bicester, Oxfordshire, United Kingdom"),
    "brabham": ("Brabham", "British", "Chessington, Surrey, United Kingdom"),
    "team_lotus": ("Team Lotus", "British", "Hethel, Norfolk, United Kingdom"),
    "lotus": ("Lotus", "British", "Hethel, Norfolk, United Kingdom"),
    "alfa": ("Alfa Romeo", "Italian", "Milan, Italy"),
    "alfa_romeo": ("Alfa Romeo", "Italian", "Milan, Italy"),
    "alfa romeo": ("Alfa Romeo", "Italian", "Milan, Italy"),
    "toleman": ("Toleman", "British", "Witney, Oxfordshire, United Kingdom"),
    "theodore": ("Theodore", "Hong Kong", "Reading, Berkshire, United Kingdom"),
    "fittipaldi": ("Fittipaldi", "Brazilian", "Reading, Berkshire, United Kingdom"),
    "ats": ("ATS", "German", "Bad Dürkheim, Germany"),
    "ensign": ("Ensign", "British", "Walsall, Staffordshire, UK"),
    "shadow": ("Shadow", "British", "Northampton, United Kingdom"),
    "surtees": ("Surtees", "British", "Edenbridge, Kent, United Kingdom"),
    "wolf": ("Wolf", "Canadian", "Reading, Berkshire, United Kingdom"),
    "hesketh": ("Hesketh", "British", "Easton Neston, Northamptonshire, UK"),
    "penske": ("Penske", "American", "Poole, Dorset, United Kingdom"),
    "parnelli": ("Parnelli", "American", "Torrance, California, USA"),

    # Classic Era (1950s - 1970s)
    "matra": ("Matra", "French", "Vélizy-Villacoublay, France"),
    "brm": ("BRM", "British", "Bourne, Lincolnshire, United Kingdom"),
    "cooper": ("Cooper", "British", "Surbiton, Surrey, United Kingdom"),
    "vanwall": ("Vanwall", "British", "Acton, London, United Kingdom"),
    "maserati": ("Maserati", "Italian", "Modena, Italy"),
    "lancia": ("Lancia", "Italian", "Turin, Italy"),
    "gordini": ("Gordini", "French", "Paris, France"),
    "porsche": ("Porsche", "German", "Stuttgart, Germany"),
    "eagle": ("Eagle", "American", "Santa Ana, California, USA"),
    "de_tomaso": ("De Tomaso", "Italian", "Modena, Italy"),
    "hwm": ("HWM", "British", "Walton-on-Thames, Surrey, UK"),
    "connaught": ("Connaught", "British", "Send, Surrey, United Kingdom"),
    "talbot-lago": ("Talbot-Lago", "French", "Suresnes, France"),
    "lola": ("Lola", "British", "Huntingdon, Cambridgeshire, UK"),
    "kurtis_kraft": ("Kurtis Kraft", "American", "Glendale, California, USA"),
    "watson": ("Watson", "American", "Glendale, California, USA"),
    "epperly": ("Epperly", "American", "Gardena, California, USA"),
    "kuzma": ("Kuzma", "American", "Los Angeles, California, USA"),
}


def init_constructor_seasons_table(cur):
    """Ensure the CONSTRUCTOR_SEASONS table exists."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS CONSTRUCTOR_SEASONS (
            constructor_id INT NOT NULL,
            season_year INT NOT NULL,
            PRIMARY KEY (constructor_id, season_year),
            FOREIGN KEY (constructor_id) REFERENCES CONSTRUCTORS(constructor_id) ON DELETE CASCADE
        )
    """)


def seed_constructors_and_seasons():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        init_constructor_seasons_table(cur)

        # 1. Seed known base locations into CONSTRUCTORS
        print("1. Seeding / updating historical constructor base locations...")
        for key, (name, nationality, base) in CONSTRUCTOR_LOCATIONS_MAP.items():
            cur.execute("SELECT constructor_id, base_location FROM CONSTRUCTORS WHERE LOWER(name) = LOWER(%s)", (name,))
            row = cur.fetchone()
            if row:
                if row.get("base_location") in ("N/A", "", "Unknown"):
                    cur.execute(
                        "UPDATE CONSTRUCTORS SET base_location = %s, nationality = %s WHERE constructor_id = %s",
                        (base, nationality, row["constructor_id"])
                    )
            else:
                cur.execute(
                    "INSERT INTO CONSTRUCTORS (name, nationality, base_location) VALUES (%s, %s, %s)",
                    (name, nationality, base)
                )

        conn.commit()

        # 2. Populate CONSTRUCTOR_SEASONS from existing races & results & contracts in DB
        print("2. Syncing existing race results & contracts into CONSTRUCTOR_SEASONS...")
        cur.execute("""
            INSERT IGNORE INTO CONSTRUCTOR_SEASONS (constructor_id, season_year)
            SELECT DISTINCT rr.constructor_id, r.season_year
            FROM RACE_RESULTS rr
            JOIN RACES r ON rr.race_id = r.race_id
        """)
        cur.execute("""
            INSERT IGNORE INTO CONSTRUCTOR_SEASONS (constructor_id, season_year)
            SELECT DISTINCT constructor_id, season_year
            FROM DRIVER_CONTRACTS
        """)
        conn.commit()

        # 3. Pre-seed key historical seasons (e.g. 2026, 2025, 2024, 2023, 2022, 2021, 2020, 2012, 2008, 1998, 1988, 1976, 1950)
        # Fetching season constructors from Jolpica
        key_seasons = [2026, 2024, 2023, 2021, 2020, 2012, 2008, 1998, 1988, 1976, 1950]
        print(f"3. Fetching and linking constructors for milestone seasons: {key_seasons}...")

        for season in key_seasons:
            try:
                url = f"https://api.jolpi.ca/ergast/f1/{season}/constructors/?format=json&limit=100"
                r = requests.get(url, timeout=15)
                if r.status_code != 200:
                    continue
                data = r.json()
                constructors = data.get("MRData", {}).get("ConstructorTable", {}).get("Constructors", [])

                for c in constructors:
                    c_name = c.get("name") or c.get("constructorId")
                    c_id_raw = str(c.get("constructorId", "")).lower().strip()
                    c_name_low = c_name.lower().strip()
                    nat = c.get("nationality") or "Unknown"

                    base = "N/A"
                    if c_id_raw in CONSTRUCTOR_LOCATIONS_MAP:
                        base = CONSTRUCTOR_LOCATIONS_MAP[c_id_raw][2]
                    elif c_name_low in CONSTRUCTOR_LOCATIONS_MAP:
                        base = CONSTRUCTOR_LOCATIONS_MAP[c_name_low][2]
                    else:
                        for k, v in CONSTRUCTOR_LOCATIONS_MAP.items():
                            if k in c_id_raw or c_id_raw in k or k in c_name_low or c_name_low in k:
                                base = v[2]
                                break

                    # Find or insert constructor
                    cur.execute("SELECT constructor_id, base_location FROM CONSTRUCTORS WHERE LOWER(name) = LOWER(%s)", (c_name,))
                    existing = cur.fetchone()
                    if existing:
                        cid = existing["constructor_id"]
                        if existing.get("base_location") in ("N/A", "") and base != "N/A":
                            cur.execute("UPDATE CONSTRUCTORS SET base_location = %s WHERE constructor_id = %s", (base, cid))
                    else:
                        cur.execute(
                            "INSERT INTO CONSTRUCTORS (name, nationality, base_location) VALUES (%s, %s, %s)",
                            (c_name, nat, base)
                        )
                        cid = cur.lastrowid

                    # Link into CONSTRUCTOR_SEASONS
                    cur.execute(
                        "INSERT IGNORE INTO CONSTRUCTOR_SEASONS (constructor_id, season_year) VALUES (%s, %s)",
                        (cid, season)
                    )

                conn.commit()
                print(f"   Season {season}: {len(constructors)} teams linked.")
            except Exception as e:
                print(f"   Season {season} error: {e}")

        # Summary
        cur.execute("SELECT COUNT(*) AS total_constructors FROM CONSTRUCTORS")
        total_c = cur.fetchone()["total_constructors"]
        cur.execute("SELECT COUNT(*) AS total_links FROM CONSTRUCTOR_SEASONS")
        total_l = cur.fetchone()["total_links"]
        print(f"\nDone! Total constructors: {total_c}, Total season linkages: {total_l}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    seed_constructors_and_seasons()
