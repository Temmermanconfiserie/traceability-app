import psycopg2
import bcrypt

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# --- KIES HIER JE ADMIN GEGEVENS ---
Temmermanconfiserie = "admin"
Temmerman1904 = "your_secure_password" # Verander dit!
# ------------------------------------

def create_admin():
    """Maakt de eerste admin gebruiker aan in de database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Versleutel het wachtwoord
        hashed_password = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Voeg de admin toe (of update als hij al bestaat)
        cur.execute(
            """
            INSERT INTO users (username, password, role) VALUES (%s, %s, 'admin')
            ON CONFLICT (username) DO UPDATE SET
                password = EXCLUDED.password,
                role = EXCLUDED.role;
            """,
            (ADMIN_USERNAME, hashed_password)
        )
        
        conn.commit()
        cur.close()
        print(f"✅ Admin gebruiker '{ADMIN_USERNAME}' succesvol aangemaakt/bijgewerkt.")
    except Exception as e:
        print(f"❌ Fout: {e}")
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == '__main__':
    create_admin()