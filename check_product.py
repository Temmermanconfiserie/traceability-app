import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
PRODUCT_NAME_TO_CHECK = "suikervrije beertjes" # Pas dit aan indien nodig

print(f"--- Checking for product: '{PRODUCT_NAME_TO_CHECK}' ---")
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Zoek naar een productnaam die de tekst bevat (case-insensitive)
    cur.execute("SELECT * FROM Inkomende_Producten WHERE productnaam ILIKE %s;", (f"%{PRODUCT_NAME_TO_CHECK}%",))
    result = cur.fetchone()
    
    cur.close()
    conn.close()
    
    print("-" * 20)
    if result:
        print("✅ SUCCESS: Found the following data in the database:")
        print(result)
    else:
        print(f"❌ FAILURE: The product '{PRODUCT_NAME_TO_CHECK}' was NOT found in the database.")
    print("-" * 20)

except Exception as e:
    print(f"An error occurred: {e}")