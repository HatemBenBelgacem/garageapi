from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "iot_secure_secret_key"  # Für Flash-Nachrichten

# PostgreSQL Verbindungskonfiguration
# Format: postgresql://username:password@host:port/database_name
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:dein_passwort@localhost:5432/kennzeichen_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Datenmodell für die Kennzeichen
class Kennzeichen(db.Model):
    __tablename__ = 'kennzeichen'
    id = db.Column(db.Integer, primary_key=True)
    platte = db.Column(db.String(20), unique=True, nullable=False)
    fahrzeug_halter = db.Column(db.String(100), nullable=False)
    notiz = db.Column(db.String(200), nullable=True)

    def __init__(self, platte, fahrzeug_halter, notiz):
        self.platte = platte.upper().strip() # Automatische Formatierung in Großbuchstaben
        self.fahrzeug_halter = fahrzeug_halter.strip()
        self.notiz = notiz.strip()

# Datenbank-Tabellen initialisieren (Erstellt die Tabelle, falls sie nicht existiert)
with app.app_context():
    db.create_all()

# ROUTE: Dashboard & Hinzufügen
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        platte = request.form['platte']
        halter = request.form['halter']
        notiz = request.form['notiz']

        if not platte or not halter:
            flash('Bitte Kennzeichen und Halter angeben!', 'error')
        else:
            existiert = Kennzeichen.query.filter_by(platte=platte.upper()).first()
            if existiert:
                flash('Dieses Kennzeichen existiert bereits!', 'error')
            else:
                neues_kennzeichen = Kennzeichen(platte, halter, notiz)
                db.session.add(neues_kennzeichen)
                db.session.commit()
                flash('Kennzeichen erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('index'))

    alle_kennzeichen = Kennzeichen.query.order_by(Kennzeichen.id.desc()).all()
    return render_template('index.html', kennzeichen_liste=alle_kennzeichen)

# ROUTE: Bearbeiten
@app.route('/edit/<int:id>', methods=['POST'])
def edit(id):
    eintrag = Kennzeichen.query.get_or_transform(id) # get_or_404 alternativ
    eintrag = db.session.get(Kennzeichen, id)
    
    if eintrag:
        eintrag.platte = request.form['platte'].upper().strip()
        eintrag.fahrzeug_halter = request.form['halter'].strip()
        eintrag.notiz = request.form['notiz'].strip()
        db.session.commit()
        flash('Eintrag erfolgreich aktualisiert!', 'success')
    return redirect(url_for('index'))

# ROUTE: Löschen
@app.route('/delete/<int:id>')
def delete(id):
    eintrag = db.session.get(Kennzeichen, id)
    if eintrag:
        db.session.delete(eintrag)
        db.session.commit()
        flash('Kennzeichen gelöscht!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)