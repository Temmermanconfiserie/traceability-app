import psycopg2
import pandas as pd
import math
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
EXCEL_FILE_PATH = "data.xlsx"

def import_leveranciers():
    print("--- Start import Leveranciers ---")
    try:
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Leveranciers", dtype=str)
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for index, row in df.iterrows():
            if pd.notna(row['Naam']):
                cur.execute("INSERT INTO Leveranciers (naam) VALUES (%s) ON CONFLICT (naam) DO NOTHING;", (row['Naam'],))
        conn.commit()
        cur.close()
        print("✅ Import van leveranciers voltooid!")
    except Exception as e:
        print(f"❌ FOUT bij importeren van leveranciers: {e}")
    finally:
        if 'conn' in locals() and conn is not None: conn.close()

def import_klanten():
    print("\n--- Start import Klanten ---")
    try:
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Klanten", dtype=str)
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for index, row in df.iterrows():
            if pd.notna(row['Klantnaam']):
                cur.execute("INSERT INTO Klanten (klantnaam) VALUES (%s) ON CONFLICT (klantnaam) DO NOTHING;",(row['Klantnaam'],))
        conn.commit()
        cur.close()
        print("✅ Import van klanten voltooid!")
    except Exception as e:
        print(f"❌ FOUT bij importeren van klanten: {e}")
    finally:
        if 'conn' in locals() and conn is not None: conn.close()

def import_inkomende_producten():
    print("\n--- Start import Inkomende Producten ---")
    try:
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Inkomende_Producten", dtype=str)
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for index, row in df.iterrows():
            houdbaarheid = row.get('Houdbaarheid_dagen')
            houdbaarheid_db = int(float(houdbaarheid)) if pd.notna(houdbaarheid) else None
            cur.execute(
                """
                INSERT INTO Inkomende_Producten (referentie, ean_code, productnaam, houdbaarheid_dagen)
                VALUES (%s, %s, %s, %s) ON CONFLICT (referentie) DO UPDATE SET
                    ean_code = EXCLUDED.ean_code, productnaam = EXCLUDED.productnaam, houdbaarheid_dagen = EXCLUDED.houdbaarheid_dagen;
                """,
                (row['Referentie'], row.get('EAN_code'), row['Productnaam'], houdbaarheid_db)
            )
        conn.commit()
        cur.close()
        print("✅ Import van inkomende producten voltooid!")
    except Exception as e:
        print(f"❌ FOUT bij importeren van inkomende producten: {e}")
    finally:
        if 'conn' in locals() and conn is not None: conn.close()

def import_recipes_and_final_products():
    print("\n--- Start import Recepten & Uitgaande Producten ---")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        df_recept_def = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Recept_Definities", dtype=str)
        df_recept_comp = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Recept_Componenten", dtype=str)
        df_uitgaand = pd.read_excel(EXCEL_FILE_PATH, sheet_name="Uitgaande_Producten", dtype=str)

        for _, row in df_recept_def.iterrows():
            cur.execute(
                "INSERT INTO Recept_Definities (recept_id, recept_naam) VALUES (%s, %s) ON CONFLICT (recept_id) DO UPDATE SET recept_naam = EXCLUDED.recept_naam;",
                (row['Recept_ID'].strip(), row['Recept_Naam'].strip())
            )
        print(" -> Recept definities verwerkt.")

        cur.execute("SELECT id, referentie FROM Inkomende_Producten;")
        inkomend_map = {str(row['referentie']).strip(): row['id'] for row in cur.fetchall()}

        for _, row in df_recept_comp.iterrows():
            inkomend_id = inkomend_map.get(row['Inkomend_Product_Referentie'].strip())
            if inkomend_id:
                cur.execute(
                    "INSERT INTO Recept_Componenten (recept_id, inkomend_product_id, percentage) VALUES (%s, %s, %s) ON CONFLICT (recept_id, inkomend_product_id) DO UPDATE SET percentage = EXCLUDED.percentage;",
                    (row['Recept_ID'].strip(), inkomend_id, int(float(row['Percentage'])))
                )
        print(" -> Recept componenten verwerkt.")

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
                INSERT INTO Uitgaande_Producten (referentie, ean_code, productnaam, gewicht_gram, bron_recept_id, bron_inkomend_id)
                VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (referentie) DO UPDATE SET
                    ean_code = EXCLUDED.ean_code, productnaam = EXCLUDED.productnaam, gewicht_gram = EXCLUDED.gewicht_gram,
                    bron_recept_id = EXCLUDED.bron_recept_id, bron_inkomend_id = EXCLUDED.bron_inkomend_id;
                """,
                (row['Referentie'], row.get('EAN_code'), row['Productnaam'], int(float(row['Gewicht_gram'])), bron_recept_id, bron_inkomend_id)
            )
        print(" -> Uitgaande producten verwerkt.")

        conn.commit()
        cur.close()
        print("✅ Import van recepten en uitgaande producten voltooid!")
    except Exception as e:
        print(f"❌ FOUT bij importeren van recepten en uitgaande producten: {e}")
    finally:
        if conn is not None: conn.close()

if __name__ == '__main__':
    import_leveranciers()
    import_klanten()
    import_inkomende_producten()
    import_recipes_and_final_products()