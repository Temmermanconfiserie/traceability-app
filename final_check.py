import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

print("--- Checking the 'Klanten' table directly ---")
try:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM Klanten;")
    klanten = cur.fetchall()
    
    print("\nFound the following customers:")
    print(klanten)
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"An error occurred: {e}")