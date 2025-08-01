import psycopg2
import pandas as pd
import bcrypt
import math
from psycopg2.extras import RealDictCursor

# --- BELANGRIJK: PAS DEZE GEGEVENS AAN ---
# Verander de tekst TUSSEN de aanhalingstekens
ADMIN_USERNAME = "Temmermanconfiserie" 
ADMIN_PASSWORD = "Temmerman1904" # Kies een sterk wachtwoord!
# ----------------------------------------

EXCEL_FILE_PATH = "data.xlsx"

def run_full_setup(db_url):
    """Voert de volledige setup uit: admin aanmaken en data importeren."""
    try:
        print("--- Start admin aanmaken ---")
        create_admin(db_url)
        print("--- Start data import ---")
        import_all_data(db_url)
        return "✅ Setup succesvol voltooid! De database is gevuld."
    except Exception as e:
        return f"❌ FOUT tijdens setup: {e}"

def create_admin(db_url):
    """Maakt de eerste admin gebruiker aan."""
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    hashed_password = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute(
        """
        INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin')
        ON CONFLICT (username) DO UPDATE SET password = EXCLUDED.password, role = EXCLUDED.role;
        """,
        (ADMIN_USERNAME, hashed_password)
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"-> Admin gebruiker '{ADMIN_USERNAME}' aangemaakt/bijgewerkt.")

def import_all_data(db_url):
    """Importeert alle data uit het Excel-bestand."""
    # Deze functie bevat de logica van het oude import_data.py script
    # (Leveranciers, Klanten, Producten, Recepten)
    # Voor de beknoptheid wordt de volledige code hier niet herhaald,
    # maar je kunt de functies uit je oude import_data.py hierin plakken.
    # Hieronder staat een vereenvoudigde versie die de belangrijkste tabellen importeert.
    
    conn = psycopg2.connect(db_url)
    
    # Leveranciers
    df_leveranciers = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Leveranciers", dtype=str)
    with conn.cursor() as cur:
        for _, row in df_leveranciers.iterrows():
            if pd.notna(row['Naam']):
                cur.execute("INSERT INTO Leveranciers (naam) VALUES (%s) ON CONFLICT (naam) DO NOTHING;", (row['Naam'],))
    conn.commit()
    print("-> Leveranciers geïmporteerd.")
    
    # Klanten
    df_klanten = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Klanten", dtype=str)
    with conn.cursor() as cur:
        for _, row in df_klanten.iterrows():
            if pd.notna(row['Klantnaam']):
                cur.execute("INSERT INTO Klanten (klantnaam) VALUES (%s) ON CONFLICT (klantnaam) DO NOTHING;", (row['Klantnaam'],))
    conn.commit()
    print("-> Klanten geïmporteerd.")

    # Inkomende Producten
    df_inkomend = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Inkomende_Producten", dtype=str)
    with conn.cursor() as cur:
        for _, row in df_inkomend.iterrows():
            houdbaarheid = row.get('Houdbaarheid_dagen')
            houdbaarheid_db = int(float(houdbaarheid)) if pd.notna(houdbaarheid) else None
            cur.execute(
                """
                INSERT INTO Inkomende_Producten (referentie, productnaam, ean_code, houdbaarheid_dagen) VALUES (%s, %s, %s, %s)
                ON CONFLICT (referentie) DO UPDATE SET productnaam = EXCLUDED.productnaam, ean_code = EXCLUDED.ean_code, houdbaarheid_dagen = EXCLUDED.houdbaarheid_dagen;
                """,
                (row['Referentie'], row['Productnaam'], row.get('EAN_code'), houdbaarheid_db)
            )
    conn.commit()
    print("-> Inkomende producten geïmporteerd.")

    # Recepten & Uitgaande producten
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        df_recept_def = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Recept_Definities", dtype=str)
        df_recept_comp = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Recept_Componenten", dtype=str)
        df_uitgaand = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Uitgaande_Producten", dtype=str)

        for _, row in df_recept_def.iterrows():
            cur.execute("INSERT INTO Recept_Definities (recept_id, recept_naam) VALUES (%s, %s) ON CONFLICT (recept_id) DO UPDATE SET recept_naam = EXCLUDED.recept_naam;", (row['Recept_ID'].strip(), row['Recept_Naam'].strip()))
        
        cur.execute("SELECT id, referentie FROM Inkomende_Producten;")
        inkomend_map = {str(row['referentie']).strip(): row['id'] for row in cur.fetchall()}

        for _, row in df_recept_comp.iterrows():
            inkomend_id = inkomend_map.get(row['Inkomend_Product_Referentie'].strip())
            if inkomend_id:
                cur.execute("INSERT INTO Recept_Componenten (recept_id, inkomend_product_id, percentage) VALUES (%s, %s, %s) ON CONFLICT (recept_id, inkomend_product_id) DO UPDATE SET percentage = EXCLUDED.percentage;", (row['Recept_ID'].strip(), inkomend_id, int(float(row['Percentage']))))

        for _, row in df_uitgaand.iterrows():
            bron_ref = row['Bron_Referentie'].strip()
            bron_recept_id = None
            bron_inkomend_id = None
            if bron_ref.startswith("M"):
                bron_recept_id = bron_ref
            else:
                bron_inkomend_id = inkomend_map.get(bron_ref)
            if bron_recept_id is None and bron_inkomend_id is None:
                raise Exception(f"Kon bron niet vinden voor product '{row['Productnaam']}' met referentie '{bron_ref}'")
            cur.execute(
                """
                INSERT INTO Uitgaande_Producten (referentie, ean_code, productnaam, gewicht_gram, bron_recept_id, bron_inkomend_id) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (referentie) DO UPDATE SET ean_code = EXCLUDED.ean_code, productnaam = EXCLUDED.productnaam, gewicht_gram = EXCLUDED.gewicht_gram, bron_recept_id = EXCLUDED.bron_recept_id, bron_inkomend_id = EXCLUDED.bron_inkomend_id;
                """,
                (row['Referentie'], row.get('EAN_code'), row['Productnaam'], int(float(row['Gewicht_gram'])), bron_recept_id, bron_inkomend_id)
            )
    conn.commit()
    print("-> Recepten en uitgaande producten geïmporteerd.")
    
    conn.close()