from flask import Flask, jsonify, request, render_template, Response, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
import psycopg2
import bcrypt
import io
from functools import wraps
import initial_setup # Belangrijke import

# --- PDF & Barcode Imports ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.graphics.barcode import eanbc
from reportlab.graphics.shapes import Drawing 
from reportlab.graphics import renderPDF

# --- App Configuratie ---
DATABASE_URL = "postgresql://neondb_owner:npg_sU7B0wLzIqVp@ep-soft-frost-a2dtyc79-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
app = Flask(__name__)
app.config['SECRET_KEY'] = 'een-zeer-geheim-wachtwoord-dat-niemand-mag-raden' # Verander dit in een willekeurige string

# --- Login Manager Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(id=user_data['id'], username=user_data['username'], role=user_data['role'])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Je hebt geen toegang tot deze pagina.")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# --- Login & Logout Routes ---
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s;", (username,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password'].encode('utf-8')):
            user = User(id=user_data['id'], username=user_data['username'], role=user_data['role'])
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("Ongeldige gebruikersnaam of wachtwoord.")
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))
    
@app.route("/setup-database-once/a1b2c3d4e5f6") # Dit is je geheime URL
def run_initial_setup():
    result = initial_setup.run_full_setup(DATABASE_URL)
    return result

# --- Beveiligde Pagina Routes ---
@app.route("/")
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT COUNT(*) as val FROM Klanten;")
    klanten_aantal = cur.fetchone()['val']
    cur.execute("SELECT COUNT(*) as val FROM Uitgaande_Producten;")
    producten_aantal = cur.fetchone()['val']
    cur.execute("SELECT SUM(resterend_gewicht_kg) as val FROM Voorraad_Inkomend;")
    totaal_voorraad_kg = cur.fetchone()['val']
    stats = {"klanten_aantal": klanten_aantal, "producten_aantal": producten_aantal, "totaal_voorraad_kg": totaal_voorraad_kg}
    cur.execute("""
        SELECT v.verzend_datum, v.aantal_eenheden, pb.nieuw_lotnummer, up.productnaam, k.klantnaam FROM Verzendingen v
        JOIN Productie_Batch pb ON v.productie_batch_id = pb.id JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id
        JOIN Klanten k ON v.klant_id = k.id ORDER BY v.verzend_datum DESC LIMIT 5;
    """)
    recente_verzendingen = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", stats=stats, recente_verzendingen=recente_verzendingen)

@app.route("/ontvangst")
@login_required
def ontvangst_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT naam FROM Leveranciers ORDER BY naam;")
    leveranciers = cur.fetchall()
    cur.execute("SELECT productnaam, ean_code FROM Inkomende_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("ontvangst.html", leveranciers=leveranciers, producten=producten)

@app.route("/productie")
@login_required
def productie_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT referentie, productnaam FROM Uitgaande_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("productie.html", producten=producten)

@app.route("/verzending")
@login_required
def verzending_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, klantnaam FROM Klanten ORDER BY klantnaam;")
    klanten = cur.fetchall()
    cur.execute("SELECT referentie, productnaam, ean_code FROM Uitgaande_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("verzending.html", klanten=klanten, producten=producten)
    
@app.route("/rapport")
@login_required
def rapport_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT referentie, productnaam FROM Uitgaande_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("rapport.html", producten=producten)

@app.route("/voorraad")
@login_required
def voorraad_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT ip.productnaam, SUM(vi.resterend_gewicht_kg) as totaal_resterend
        FROM Voorraad_Inkomend vi JOIN Inkomende_Producten ip ON vi.inkomend_product_id = ip.id
        GROUP BY ip.productnaam HAVING SUM(vi.resterend_gewicht_kg) > 0 ORDER BY ip.productnaam;
    """)
    inkomende_voorraad = cur.fetchall()
    cur.execute("""
        SELECT up.productnaam, SUM(pb.resterend_aantal) as totaal_resterend
        FROM Productie_Batch pb JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id
        GROUP BY up.productnaam HAVING SUM(pb.resterend_aantal) > 0 ORDER BY up.productnaam;
    """)
    afgewerkte_voorraad = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("voorraad.html", inkomende_voorraad=inkomende_voorraad, afgewerkte_voorraad=afgewerkte_voorraad)

@app.route("/beheer/klanten")
@login_required
@admin_required
def beheer_klanten_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, klantnaam FROM Klanten ORDER BY klantnaam;")
    klanten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("beheer_klanten.html", klanten=klanten)

@app.route("/beheer/producten")
@login_required
@admin_required
def beheer_producten_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT referentie, productnaam, ean_code FROM Inkomende_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("beheer_producten.html", producten=producten)

@app.route("/beheer/leveranciers")
@login_required
@admin_required
def beheer_leveranciers_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, naam FROM Leveranciers ORDER BY naam;")
    leveranciers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("beheer_leveranciers.html", leveranciers=leveranciers)

@app.route("/beheer/gebruikers")
@login_required
@admin_required
def beheer_gebruikers_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, role FROM users ORDER BY username;")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("beheer_gebruikers.html", users=users)

# --- Helper function for trace data ---
def get_trace_data(lotnummer):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pb.*, up.productnaam, up.gewicht_gram FROM Productie_Batch pb
        JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id WHERE pb.nieuw_lotnummer = %s;
    """, (lotnummer,))
    batch_info = cur.fetchone()
    if not batch_info: return None
    cur.execute("SELECT v.*, k.klantnaam FROM Verzendingen v JOIN Klanten k ON v.klant_id = k.id WHERE v.productie_batch_id = %s;", (batch_info['id'],))
    shipping_info = cur.fetchone()
    cur.execute("""
        SELECT pc.gebruikt_gewicht_kg, vi.*, ip.productnaam, l.naam as leverancier_naam FROM Productie_Componenten pc
        JOIN Voorraad_Inkomend vi ON pc.gebruikte_voorraad_id = vi.id JOIN Inkomende_Producten ip ON vi.inkomend_product_id = ip.id
        JOIN Leveranciers l ON vi.leverancier_id = l.id WHERE pc.productie_batch_id = %s;
    """, (batch_info['id'],))
    components_info = cur.fetchall()
    cur.close()
    conn.close()
    return {"batch": batch_info, "verzending": shipping_info, "componenten": components_info}

# --- API Routes ---
@app.route("/api/users", methods=['POST'])
@login_required
@admin_required
def add_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify(status="error", message="Gebruikersnaam en wachtwoord zijn verplicht."), 400
    
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'user');", (username, hashed_password))
        return jsonify(status="success", message="Gebruiker succesvol toegevoegd.")
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify(status="error", message=f"Gebruiker '{username}' bestaat al."), 409
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None:
            conn.close()

@app.route("/api/leveranciers", methods=['POST'])
@login_required
@admin_required
def add_leverancier():
    data = request.get_json()
    naam = data.get('naam')
    if not naam:
        return jsonify(status="error", message="Naam is verplicht."), 400
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO Leveranciers (naam) VALUES (%s);", (naam,))
        return jsonify(status="success", message="Leverancier succesvol toegevoegd.")
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify(status="error", message=f"Leverancier '{naam}' bestaat al."), 409
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None:
            conn.close()

@app.route("/api/klanten", methods=['POST'])
@login_required
@admin_required
def add_klant():
    data = request.get_json()
    klantnaam = data.get('klantnaam')
    if not klantnaam:
        return jsonify(status="error", message="Klantnaam is verplicht."), 400
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO Klanten (klantnaam) VALUES (%s);", (klantnaam,))
        return jsonify(status="success", message="Klant succesvol toegevoegd.")
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify(status="error", message=f"Klant '{klantnaam}' bestaat al."), 409
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None:
            conn.close()

@app.route("/api/producten/inkomend", methods=['POST'])
@login_required
@admin_required
def add_inkomend_product():
    data = request.get_json()
    ref = data.get('referentie')
    naam = data.get('productnaam')
    if not ref or not naam:
        return jsonify(status="error", message="Referentie en Productnaam zijn verplicht."), 400
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO Inkomende_Producten (referentie, productnaam, ean_code, houdbaarheid_dagen) VALUES (%s, %s, %s, %s);",
                    (ref, naam, data.get('ean_code'), data.get('houdbaarheid_dagen'))
                )
        return jsonify(status="success", message="Product succesvol toegevoegd.")
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify(status="error", message=f"Product met referentie '{ref}' bestaat al."), 409
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None:
            conn.close()

@app.route("/api/ontvangst", methods=['POST'])
@login_required
def ontvangst_product():
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM Inkomende_Producten WHERE TRIM(ean_code) = TRIM(%s);", (data['ean_code'],))
                product_result = cur.fetchone()
                if not product_result: return jsonify(status="error", message="Product met deze EAN-code niet gevonden."), 404
                product_id = product_result[0]
                cur.execute("SELECT id FROM Leveranciers WHERE TRIM(LOWER(naam)) = TRIM(LOWER(%s));", (data['leverancier_naam'],))
                leverancier_result = cur.fetchone()
                if not leverancier_result: return jsonify(status="error", message="Leverancier niet gevonden."), 404
                leverancier_id = leverancier_result[0]
                cur.execute(
                    "INSERT INTO Voorraad_Inkomend (inkomend_product_id, leverancier_id, lotnummer_leverancier, tht_leverancier, inkomend_gewicht_kg, resterend_gewicht_kg) VALUES (%s, %s, %s, %s, %s, %s)",
                    (product_id, leverancier_id, data['lotnummer_leverancier'], data['tht'], data['gewicht_kg'], data['gewicht_kg'])
                )
        return jsonify(status="success", message="Nieuwe voorraad succesvol geregistreerd.")
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None: conn.close()

@app.route('/api/productie', methods=['POST'])
@login_required
def productie_run():
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM Uitgaande_Producten WHERE referentie = %s;", (data['referentie'],))
                uitgaand_product = cur.fetchone()
                if not uitgaand_product: raise Exception(f"Uitgaand product {data['referentie']} niet gevonden.")
                benodigd_gewicht_totaal = uitgaand_product['gewicht_gram'] * data['aantal'] / 1000.0
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
                    cur.execute("SELECT * FROM Voorraad_Inkomend WHERE inkomend_product_id = %s AND resterend_gewicht_kg > 0.01 ORDER BY tht_leverancier ASC;", (comp['inkomend_product_id'],))
                    beschikbare_batches = cur.fetchall()
                    for batch in beschikbare_batches:
                        if benodigd_comp_gewicht <= 0: break
                        gewicht_te_gebruiken = min(benodigd_comp_gewicht, batch['resterend_gewicht_kg'])
                        gebruikte_voorraad_batches.append({'id': batch['id'], 'gewicht': gewicht_te_gebruiken})
                        if kortste_tht is None or batch['tht_leverancier'] < kortste_tht:
                            kortste_tht = batch['tht_leverancier']
                        benodigd_comp_gewicht -= gewicht_te_gebruiken
                    if benodigd_comp_gewicht > 0.01: raise Exception(f"Onvoldoende voorraad voor '{comp['productnaam']}'.")
                today = date.today()
                cur.execute("INSERT INTO Lot_Sequence (sequence_date, last_sequence) VALUES (%s, 1) ON CONFLICT (sequence_date) DO UPDATE SET last_sequence = Lot_Sequence.last_sequence + 1 RETURNING last_sequence;", (today,))
                next_seq = cur.fetchone()['last_sequence']
                yyyymmdd = today.strftime('%y%m%d')
                sequence_str = f"{next_seq:03d}"
                nieuw_lotnummer = f"L{yyyymmdd}{sequence_str}"
                cur.execute(
                    "INSERT INTO Productie_Batch (uitgaand_product_id, nieuw_lotnummer, nieuwe_tht, aantal_eenheden, resterend_aantal) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                    (uitgaand_product['id'], nieuw_lotnummer, kortste_tht, data['aantal'], data['aantal'])
                )
                productie_batch_id = cur.fetchone()['id']
                for gebruikte_batch in gebruikte_voorraad_batches:
                    cur.execute("UPDATE Voorraad_Inkomend SET resterend_gewicht_kg = resterend_gewicht_kg - %s WHERE id = %s;", (gebruikte_batch['gewicht'], gebruikte_batch['id']))
                    cur.execute("INSERT INTO Productie_Componenten (productie_batch_id, gebruikte_voorraad_id, gebruikt_gewicht_kg) VALUES (%s, %s, %s);", (productie_batch_id, gebruikte_batch['id'], gebruikte_batch['gewicht']))
        return jsonify(status="success", message="Productie succesvol geregistreerd.", lotnummer=nieuw_lotnummer)
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None: conn.close()

@app.route('/api/voorraad/product/<string:referentie>')
@login_required
def get_product_voorraad(referentie):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pb.id, pb.nieuw_lotnummer, pb.resterend_aantal, up.productnaam
        FROM Productie_Batch pb JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id
        WHERE up.referentie = %s AND pb.resterend_aantal > 0 ORDER BY pb.productie_datum ASC;
    """, (referentie,))
    batches = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(batches)

@app.route("/api/verzending", methods=['POST'])
@login_required
def verzending_producten_new():
    data = request.get_json()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                zending_id = f"Z{datetime.now().strftime('%y%m%d%H%M%S')}"
                for lot in data['loten']:
                    cur.execute("SELECT resterend_aantal FROM Productie_Batch WHERE id = %s FOR UPDATE;", (lot['batch_id'],))
                    batch = cur.fetchone()
                    if not batch or batch[0] < lot['aantal']:
                        raise Exception(f"Onvoldoende voorraad voor lot ID {lot['batch_id']}.")
                    cur.execute("UPDATE Productie_Batch SET resterend_aantal = resterend_aantal - %s WHERE id = %s;", (lot['aantal'], lot['batch_id']))
                    cur.execute(
                        "INSERT INTO Verzendingen (zending_id, productie_batch_id, klant_id, aantal_eenheden, factuurnummer) VALUES (%s, %s, %s, %s, %s);",
                        (zending_id, lot['batch_id'], data['klant_id'], lot['aantal'], data.get('factuurnummer'))
                    )
        return jsonify(status="success", message="Verzending succesvol geregistreerd.", zending_id=zending_id)
    except Exception as e:
        conn.rollback()
        return jsonify(status="error", message=str(e)), 500
    finally:
        if conn is not None: conn.close()

@app.route("/api/rapport/lot/<string:lotnummer>")
@login_required
def rapport_lot(lotnummer):
    data = get_trace_data(lotnummer)
    if not data: return jsonify({"error": "Lotnummer niet gevonden"}), 404
    return jsonify(data)

@app.route("/api/rapport/product/<string:referentie>")
@login_required
def rapport_product(referentie):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pb.nieuw_lotnummer, pb.nieuwe_tht, pb.aantal_eenheden, pb.productie_datum, k.klantnaam, v.factuurnummer
        FROM Productie_Batch pb JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id
        LEFT JOIN Verzendingen v ON pb.id = v.productie_batch_id LEFT JOIN Klanten k ON v.klant_id = k.id
        WHERE up.referentie = %s ORDER BY pb.productie_datum DESC;
    """, (referentie,))
    batches = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(batches)

@app.route("/api/label/lot/<string:lotnummer>/pdf")
@login_required
def label_lot_pdf(lotnummer):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT pb.nieuw_lotnummer, pb.nieuwe_tht, up.productnaam, up.ean_code FROM Productie_Batch pb
        JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id WHERE pb.nieuw_lotnummer = %s;
    """, (lotnummer,))
    data = cur.fetchone()
    cur.close()
    conn.close()
    if not data: return "Lotnummer niet gevonden", 404
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=(60 * mm, 40 * mm))
    product_name = (data['productnaam'][:30] + '..') if len(data['productnaam']) > 32 else data['productnaam']
    p.drawString(3 * mm, 32 * mm, product_name)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(3 * mm, 24 * mm, data['nieuw_lotnummer'])
    p.setFont("Helvetica", 10)
    p.drawString(3 * mm, 18 * mm, f"THT: {data['nieuwe_tht'].strftime('%d-%m-%Y')}")
    if data['ean_code'] and len(data['ean_code']) == 13:
        barcode = eanbc.Ean13BarcodeWidget(data['ean_code'])
        d = Drawing(50*mm, 12*mm)
        d.add(barcode)
        renderPDF.draw(d, p, 3*mm, 3*mm)
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename=label_{lotnummer}.pdf'})
    
@app.route("/api/verzending/<string:zending_id>/pdf")
@login_required
def verzending_pdf(zending_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT v.verzend_datum, v.factuurnummer, k.klantnaam, k.adres
        FROM Verzendingen v JOIN Klanten k ON v.klant_id = k.id
        WHERE v.zending_id = %s LIMIT 1;
    """, (zending_id,))
    shipment_info = cur.fetchone()
    if not shipment_info: return "Zending niet gevonden", 404
    cur.execute("""
        SELECT v.aantal_eenheden, pb.nieuw_lotnummer, pb.nieuwe_tht, up.productnaam
        FROM Verzendingen v JOIN Productie_Batch pb ON v.productie_batch_id = pb.id
        JOIN Uitgaande_Producten up ON pb.uitgaand_product_id = up.id
        WHERE v.zending_id = %s;
    """, (zending_id,))
    items = cur.fetchall()
    cur.close()
    conn.close()
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    p.setFont("Helvetica-Bold", 16)
    p.drawString(2*cm, height - 2*cm, "Pakbon")
    p.setFont("Helvetica", 11)
    p.drawString(2*cm, height - 3*cm, f"Verzending ID: {zending_id}")
    p.drawString(2*cm, height - 3.5*cm, f"Datum: {shipment_info['verzend_datum'].strftime('%d-%m-%Y')}")
    p.drawString(12*cm, height - 3*cm, f"Klant: {shipment_info['klantnaam']}")
    p.drawString(12*cm, height - 3.5*cm, f"Factuur: {shipment_info['factuurnummer'] or 'N/A'}")
    y_pos = height - 5*cm
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2*cm, y_pos, "Aantal")
    p.drawString(4*cm, y_pos, "Product")
    p.drawString(12*cm, y_pos, "Lotnummer")
    p.drawString(16*cm, y_pos, "THT")
    p.setFont("Helvetica", 10)
    y_pos -= 0.7*cm
    for item in items:
        p.drawString(2*cm, y_pos, str(item['aantal_eenheden']))
        p.drawString(4*cm, y_pos, item['productnaam'])
        p.drawString(12*cm, y_pos, item['nieuw_lotnummer'])
        p.drawString(16*cm, y_pos, item['nieuwe_tht'].strftime('%d-%m-%Y'))
        y_pos -= 0.6*cm
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename=pakbon_{zending_id}.pdf'})

if __name__ == '__main__':
    app.run(debug=True)
