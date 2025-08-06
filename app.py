from flask import Flask, jsonify, request, render_template, Response, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
import psycopg2
import bcrypt
import io
from functools import wraps

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
app.config['SECRET_KEY'] = 'een-zeer-geheim-wachtwoord-dat-niemand-mag-raden'

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
        GROUP BY ip.productnaam HAVING SUM(vi.resterend_gewicht_kg) > 0.01 ORDER BY ip.productnaam;
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

@app.route("/voorraadcorrecties")
@login_required
def voorraadcorrecties_pagina():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT referentie, productnaam FROM Inkomende_Producten ORDER BY productnaam;")
    producten = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("voorraad_correcties.html", producten=producten)

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
    # ... (code is ongewijzigd) ...
    pass

# --- API Routes ---
@app.route("/api/users", methods=['POST'])
@login_required
@admin_required
def add_user():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/leveranciers", methods=['POST'])
@login_required
@admin_required
def add_leverancier():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/klanten", methods=['POST'])
@login_required
@admin_required
def add_klant():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/producten/inkomend", methods=['POST'])
@login_required
@admin_required
def add_inkomend_product():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/ontvangst", methods=['POST'])
@login_required
def ontvangst_product():
    # ... (code is ongewijzigd) ...
    pass

@app.route('/api/productie', methods=['POST'])
@login_required
def productie_run():
    # ... (code is ongewijzigd) ...
    pass

@app.route('/api/voorraad/product/<string:referentie>')
@login_required
def get_product_voorraad(referentie):
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/verzending", methods=['POST'])
@login_required
def verzending_producten_new():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/winkelverkoop", methods=['POST'])
@login_required
def api_winkelverkoop():
    # ... (code is ongewijzigd) ...
    pass

@app.route('/api/voorraad/inkomend/<string:referentie>')
@login_required
def get_inkomende_voorraad(referentie):
    # ... (code is ongewijzigd) ...
    pass

@app.route('/api/batches/inkomend/<string:referentie>')
@login_required
def get_inkomende_batches(referentie):
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/voorraad/verwijder", methods=['POST'])
@login_required
def api_verwijder_voorraad():
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/rapport/lot/<string:lotnummer>")
@login_required
def rapport_lot(lotnummer):
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/rapport/product/<string:referentie>")
@login_required
def rapport_product(referentie):
    # ... (code is ongewijzigd) ...
    pass

@app.route("/api/label/lot/<string:lotnummer>/pdf")
@login_required
def label_lot_pdf(lotnummer):
    # ... (code is ongewijzigd) ...
    pass
    
@app.route("/api/verzending/<string:zending_id>/pdf")
@login_required
def verzending_pdf(zending_id):
    # ... (code is ongewijzigd) ...
    pass

if __name__ == '__main__':
    app.run(debug=True)
