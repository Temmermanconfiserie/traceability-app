import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def setup_database():
    """Zet de volledige database op, inclusief de nieuwe Voorraad_Correcties tabel."""
    
    drop_commands = (
        "DROP TABLE IF EXISTS Voorraad_Correcties CASCADE;",
        "DROP TABLE IF EXISTS users CASCADE;",
        "DROP TABLE IF EXISTS Lot_Sequence CASCADE;",
        "DROP TABLE IF EXISTS Verzendingen CASCADE;",
        "DROP TABLE IF EXISTS Productie_Componenten CASCADE;",
        "DROP TABLE IF EXISTS Productie_Batch CASCADE;",
        "DROP TABLE IF EXISTS Recept_Componenten CASCADE;",
        "DROP TABLE IF EXISTS Uitgaande_Producten CASCADE;",
        "DROP TABLE IF EXISTS Voorraad_Inkomend CASCADE;",
        "DROP TABLE IF EXISTS Recept_Definities CASCADE;",
        "DROP TABLE IF EXISTS Inkomende_Producten CASCADE;",
        "DROP TABLE IF EXISTS Klanten CASCADE;",
        "DROP TABLE IF EXISTS Leveranciers CASCADE;"
    )

    create_commands = (
        """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL DEFAULT 'user'
        );
        """,
        """
        CREATE TABLE Lot_Sequence (
            sequence_date DATE PRIMARY KEY,
            last_sequence INTEGER NOT NULL
        );
        """,
        """
        CREATE TABLE Leveranciers (
            id SERIAL PRIMARY KEY,
            naam VARCHAR(255) NOT NULL UNIQUE
        );
        """,
        """
        CREATE TABLE Klanten (
            id SERIAL PRIMARY KEY,
            klantnaam VARCHAR(255) NOT NULL UNIQUE
        );
        """,
        """
        CREATE TABLE Inkomende_Producten (
            id SERIAL PRIMARY KEY,
            referentie VARCHAR(100) UNIQUE NOT NULL,
            ean_code VARCHAR(100),
            productnaam VARCHAR(255) NOT NULL,
            houdbaarheid_dagen INTEGER
        );
        """,
        """
        CREATE TABLE Recept_Definities (
            recept_id VARCHAR(50) PRIMARY KEY,
            recept_naam VARCHAR(255) NOT NULL
        );
        """,
        """
        CREATE TABLE Voorraad_Inkomend (
            id SERIAL PRIMARY KEY,
            inkomend_product_id INTEGER NOT NULL REFERENCES Inkomende_Producten(id),
            leverancier_id INTEGER NOT NULL REFERENCES Leveranciers(id),
            lotnummer_leverancier VARCHAR(255) NOT NULL,
            tht_leverancier DATE NOT NULL,
            inkomend_gewicht_kg NUMERIC(10, 2) NOT NULL,
            resterend_gewicht_kg NUMERIC(10, 2) NOT NULL,
            ontvangst_datum TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(inkomend_product_id, lotnummer_leverancier)
        );
        """,
        """
        CREATE TABLE Uitgaande_Producten (
            id SERIAL PRIMARY KEY,
            referentie VARCHAR(100) UNIQUE NOT NULL,
            ean_code VARCHAR(100),
            productnaam VARCHAR(255) NOT NULL,
            gewicht_gram INTEGER NOT NULL,
            bron_recept_id VARCHAR(50) REFERENCES Recept_Definities(recept_id),
            bron_inkomend_id INTEGER REFERENCES Inkomende_Producten(id),
            CONSTRAINT chk_bron CHECK (
                (bron_recept_id IS NOT NULL AND bron_inkomend_id IS NULL) OR
                (bron_recept_id IS NULL AND bron_inkomend_id IS NOT NULL)
            )
        );
        """,
        """
        CREATE TABLE Recept_Componenten (
            id SERIAL PRIMARY KEY,
            recept_id VARCHAR(50) NOT NULL REFERENCES Recept_Definities(recept_id),
            inkomend_product_id INTEGER NOT NULL REFERENCES Inkomende_Producten(id),
            percentage INTEGER NOT NULL,
            UNIQUE(recept_id, inkomend_product_id)
        );
        """,
        """
        CREATE TABLE Productie_Batch (
            id SERIAL PRIMARY KEY,
            uitgaand_product_id INTEGER NOT NULL REFERENCES Uitgaande_Producten(id),
            nieuw_lotnummer VARCHAR(255) UNIQUE NOT NULL,
            nieuwe_tht DATE NOT NULL,
            aantal_eenheden INTEGER NOT NULL,
            resterend_aantal INTEGER NOT NULL,
            productie_datum TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE Productie_Componenten (
            productie_batch_id INTEGER NOT NULL REFERENCES Productie_Batch(id) ON DELETE CASCADE,
            gebruikte_voorraad_id INTEGER NOT NULL REFERENCES Voorraad_Inkomend(id),
            gebruikt_gewicht_kg NUMERIC(10, 2) NOT NULL,
            PRIMARY KEY (productie_batch_id, gebruikte_voorraad_id)
        );
        """,
        """
        CREATE TABLE Verzendingen (
            id SERIAL PRIMARY KEY,
            zending_id VARCHAR(50) NOT NULL,
            productie_batch_id INTEGER NOT NULL REFERENCES Productie_Batch(id),
            klant_id INTEGER NOT NULL REFERENCES Klanten(id),
            aantal_eenheden INTEGER NOT NULL,
            factuurnummer VARCHAR(100),
            verzend_datum TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE Voorraad_Correcties (
            id SERIAL PRIMARY KEY,
            voorraad_inkomend_id INTEGER NOT NULL REFERENCES Voorraad_Inkomend(id),
            aanpassing_kg NUMERIC(10, 2) NOT NULL,
            reden VARCHAR(255) NOT NULL,
            correctie_datum TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        print("Oude tabellen verwijderen (indien aanwezig)...")
        for command in drop_commands:
            cur.execute(command)
        print("Nieuwe tabellen aanmaken...")
        for command in create_commands:
            cur.execute(command)
        cur.close()
        conn.commit()
        print("✅ Database succesvol opgezet met de definitieve structuur!")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"❌ Fout: {error}")
    finally:
        if conn is not None:
            conn.close()
            print("Databaseverbinding gesloten.")

if __name__ == '__main__':
    setup_database()
