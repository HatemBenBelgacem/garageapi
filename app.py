from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "iot_secure_secret_key"  # Für Flash-Nachrichten

# SQLite Verbindungskonfiguration (v3 zur sauberen Aktiv-Logik-Übernahme)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kennzeichen_v3.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==============================================================================
# DATENMODELLE (DATENBANK-TABELLEN)
# ==============================================================================

# Tabelle 1: Registrierte Fahrzeuge (jetzt mit standardmäßigem Aktiv-Status)
class Kennzeichen(db.Model):
    __tablename__ = 'kennzeichen'
    id = db.Column(db.Integer, primary_key=True)
    platte = db.Column(db.String(20), unique=True, nullable=False)
    fahrzeug_halter = db.Column(db.String(100), nullable=False)
    notiz = db.Column(db.String(200), nullable=True)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)  # Standardmäßig AKTIV (True)

    def __init__(self, platte, fahrzeug_halter, notiz, aktiv=True):
        self.platte = platte.upper().strip()
        self.fahrzeug_halter = fahrzeug_halter.strip()
        self.notiz = notiz.strip()
        self.aktiv = aktiv

# Tabelle 2: Scan-Historie (Logbuch für IoT-Abfragen)
class ScanHistory(db.Model):
    __tablename__ = 'scan_history'
    id = db.Column(db.Integer, primary_key=True)
    platte = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # 'Angenommen', 'Gesperrt' oder 'Abgelehnt'
    zeitstempel = db.Column(db.DateTime, default=datetime.now)

    def __init__(self, platte, status):
        self.platte = platte.upper().strip()
        self.status = status

# Datenbank initialisieren
with app.app_context():
    db.create_all()

# ==============================================================================
# WEB-DASHBOARD ROUTEN
# ==============================================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        platte = request.form['platte']
        halter = request.form['halter']
        notiz = request.form['notiz']
        # Prüft, ob das "aktiv"-Häkchen gesetzt ist (standardmäßig ja)
        aktiv = 'aktiv' in request.form 

        if not platte or not halter:
            flash('Bitte Kennzeichen und Halter angeben!', 'error')
        else:
            existiert = Kennzeichen.query.filter_by(platte=platte.upper().strip()).first()
            if existiert:
                flash('Dieses Kennzeichen existiert bereits!', 'error')
            else:
                neues_kennzeichen = Kennzeichen(platte, halter, notiz, aktiv=aktiv)
                db.session.add(neues_kennzeichen)
                db.session.commit()
                flash('Kennzeichen erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('index'))

    # Daten für das Dashboard laden
    alle_kennzeichen = Kennzeichen.query.order_by(Kennzeichen.id.desc()).all()
    gesamte_historie = ScanHistory.query.order_by(ScanHistory.zeitstempel.desc()).all()
    
    return render_template('index.html', kennzeichen_liste=alle_kennzeichen, historie_liste=gesamte_historie)

@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    eintrag = db.session.get(Kennzeichen, id)
    
    if eintrag:
        eintrag.platte = request.form['platte'].upper().strip()
        eintrag.fahrzeug_halter = request.form['halter'].strip()
        eintrag.notiz = request.form['notiz'].strip()
        eintrag.aktiv = 'aktiv' in request.form  # Aktualisiert den Aktiv-Status
        
        db.session.commit()
        flash('Eintrag erfolgreich aktualisiert!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    eintrag = db.session.get(Kennzeichen, id)
    if eintrag:
        db.session.delete(eintrag)
        db.session.commit()
        flash('Kennzeichen gelöscht!', 'success')
    return redirect(url_for('index'))

# ==============================================================================
# IOT-API ROUTE FÜR DEN RASPBERRY PI
# ==============================================================================
@app.route('/api/check', methods=['POST'])
def check_kennzeichen():
    data = request.get_json()
    if not data or 'platte' not in data:
        return jsonify({'status': 'error', 'message': 'Ungültige Anfrage, "platte" fehlt.'}), 400

    gesuchte_platte = data['platte'].upper().strip()
    eintrag = Kennzeichen.query.filter_by(platte=gesuchte_platte).first()
    
    if eintrag:
        if not eintrag.aktiv:
            # FALL 1: Kennzeichen registriert, aber explizit INAKTIV (Gesperrt)
            neuer_log = ScanHistory(platte=gesuchte_platte, status='Gesperrt')
            db.session.add(neuer_log)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'authorized': False,
                'message': 'Zutritt verweigert: Dieses Fahrzeug ist gesperrt.'
            }), 200
        else:
            # FALL 2: Kennzeichen registriert und AKTIV
            neuer_log = ScanHistory(platte=gesuchte_platte, status='Angenommen')
            db.session.add(neuer_log)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'authorized': True,
                'platte': eintrag.platte,
                'halter': eintrag.fahrzeug_halter,
                'notiz': eintrag.notiz
            }), 200
    else:
        # FALL 3: Kennzeichen ist UNBEKANNT
        neuer_log = ScanHistory(platte=gesuchte_platte, status='Abgelehnt')
        db.session.add(neuer_log)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'authorized': False,
            'message': 'Kennzeichen nicht registriert.'
        }), 200

if __name__ == '__main__':
    app.run(debug=True)