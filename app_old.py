from flask import Flask, jsonify, request, render_template
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# --- Pagina Routes ---
@app.route("/")
def hello_world():
    return "<h1>Hallo!</h1><a href='/ontvangst'>Ontvangst</a> | <a href='/verzending'>Verzending</a>"

@app.route("/ontvangst")
def ontvangst_pagina():
    return render_template("ontvangst.html")

@app.route("/verzending")
def verzending_pagina():
    """Toont de verzendpagina en vult de dropdowns met klanten en producten."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT id, klantnaam FROM Klanten ORDER BY klantnaam;")
    klanten = cur.fetchall()
    
    cur.execute("SELECT referentie, productnaam FROM Uitgaande_Producten ORDER BY productnaam;")
    producten = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("verzending.html", klanten=klanten, producten=producten)

# --- API Routes ---
@app.route("/api/ontvangst", methods=['POST'])
def ontvangst_product():
    data = request.get_json()
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM Inkomende_Producten WHERE ean_code = %s;", (data['ean_code'],))
        product_result = cur.fetchone()
        if not product_result: return jsonify(status="error", message="Product met deze EAN-code niet gevonden."), 404
        product_id = product_result[0]
        cur.execute("SELECT id FROM Leveranciers WHERE naam = %s;", (data['leverancier_naam'],))
        leverancier_result = cur.fetchone()
        if not leverancier_result: return jsonify(status="error", message="Leverancier niet gevonden."), 404
        leverancier_id = leverancier_result[0]
        cur.execute(
            "INSERT INTO Voorraad_Inkomend (inkomend_product_id, leverancier_id, lotnummer_leverancier, tht_leverancier, inkomend_gewicht_kg, resterend_gewicht_kg) VALUES (%s, %s, %s, %s, %s, %s)",
            (product_id, leverancier_id, data['lotnummer_leverancier'], data['tht'], data['gewicht_kg'], data['gewicht_kg'])
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(status="success", message="Nieuwe voorraad succesvol geregistreerd.")
    except Exception as e:
        return jsonify(status="error", message=str(e)), 500


@app.route("/api/verzending", methods=['POST'])
def verzending_producten():
    data = request.get_json()
    conn = get_db_connection()
    
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                gegenereerde_lotnummers = []

                for product_item in data['producten']:
                    cur.execute("SELECT * FROM Uitgaande_Producten WHERE referentie = %s;", (product_item['referentie'],))
                    uitgaand_product = cur.fetchone()
                    if not uitgaand_product: raise Exception(f"Uitgaand product {product_item['referentie']} niet gevonden.")
                    
                    benodigd_gewicht_totaal = uitgaand_product['gewicht_gram'] * product_item['aantal'] / 1000.0

                    if uitgaand_product['bron_recept_id']:
                        cur.execute("SELECT pc.*, ip.productnaam FROM Recept_Componenten pc JOIN Inkomende_Producten ip ON pc.inkomend_product_id = ip.id WHERE recept_id = %s;", (uitgaand_product['bron_recept_id'],))
                        componenten = cur.fetchall()
                    else:
                        cur.execute("SELECT id, productnaam FROM Inkomende_Producten WHERE id = %s;", (uitgaand_product['bron_inkomend_id'],))
                        inkomend_product = cur.fetchone()
                        componenten = [{'inkomend_product_id': uitgaand_product['bron_inkomend_id'], 'percentage': 100, 'productnaam': inkomend_product['productnaam']}]
                    
                    gebruikte_voorraad_batches = []
                    kortste_tht = None

                    for comp in componenten:
                        benodigd_comp_gewicht = benodigd_gewicht_totaal * (comp['percentage'] / 100.0)
                        
                        cur.execute(
                            "SELECT * FROM Voorraad_Inkomend WHERE inkomend_product_id = %s AND resterend_gewicht_kg > 0.01 ORDER BY tht_leverancier ASC;", 
                            (comp['inkomend_product_id'],)
                        )
                        beschikbare_batches = cur.fetchall()

                        for batch in beschikbare_batches:
                            if benodigd_comp_gewicht <= 0: break
                            
                            gewicht_te_gebruiken = min(benodigd_comp_gewicht, batch['resterend_gewicht_kg'])
                            gebruikte_voorraad_batches.append({'id': batch['id'], 'gewicht': gewicht_te_gebruiken})
                            
                            if kortste_tht is None or batch['tht_leverancier'] < kortste_tht:
                                kortste_tht = batch['tht_leverancier']
                            
                            benodigd_comp_gewicht -= gewicht_te_gebruiken
                        
                        if benodigd_comp_gewicht > 0.01:
                            raise Exception(f"Onvoldoende voorraad voor '{comp['productnaam']}'.")

                    nieuw_lotnummer = f"L{datetime.now().strftime('%y%m%d%H%M%S')}-{uitgaand_product['referentie']}"
                    gegenereerde_lotnummers.append(nieuw_lotnummer)
                    
                    cur.execute(
                        "INSERT INTO Productie_Batch (uitgaand_product_id, nieuw_lotnummer, nieuwe_tht, aantal_eenheden) VALUES (%s, %s, %s, %s) RETURNING id;",
                        (uitgaand_product['id'], nieuw_lotnummer, kortste_tht, product_item['aantal'])
                    )
                    productie_batch_id = cur.fetchone()['id']

                    for gebruikte_batch in gebruikte_voorraad_batches:
                        cur.execute("UPDATE Voorraad_Inkomend SET resterend_gewicht_kg = resterend_gewicht_kg - %s WHERE id = %s;", (gebruikte_batch['gewicht'], gebruikte_batch['id']))
                        cur.execute("INSERT INTO Productie_Componenten (productie_batch_id, gebruikte_voorraad_id, gebruikt_gewicht_kg) VALUES (%s, %s, %s);", (productie_batch_id, gebruikte_batch['id'], gebruikte_batch['gewicht']))

                    cur.execute(
                        "INSERT INTO Verzendingen (productie_batch_id, klant_id, aantal_eenheden) VALUES (%s, %s, %s);",
                        (productie_batch_id, data['klant_id'], product_item['aantal'])
                    )

        return jsonify(status="success", message="Verzending succesvol geregistreerd.", lotnummers=gegenereerde_lotnummers)

    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None:
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)