from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import json
import random
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['DEBUG'] = True
app.secret_key = "slepena_atslega"

def izveidot_datu_bazi():
    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute('''CREATE TABLE IF NOT EXISTS lietotaji (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lietotajvards TEXT UNIQUE NOT NULL,
                            epasts TEXT NOT NULL,
                            parole TEXT NOT NULL,
                            aktivitate TIMESTAMP)''')

        kursors.execute('''CREATE TABLE IF NOT EXISTS uzdevumi (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            lietotaja_id INTEGER,
                            nosaukums TEXT NOT NULL,
                            apraksts TEXT NOT NULL,
                            prioritāte TEXT CHECK (prioritāte IN ('zems', 'vidējs', 'augsts')),
                            beigu_datums TEXT NOT NULL,
                            izpildits BOOLEAN NOT NULL CHECK (izpildits IN (0, 1)),
                            FOREIGN KEY (lietotaja_id) REFERENCES lietotaji(id))''')

izveidot_datu_bazi()

@app.route("/")
def sakumlapa():
    return render_template("index.html")

@app.route("/registrejies", methods=["GET", "POST"])
def registrejies():
    if request.method == "POST":
        lietotajvards = request.form["lietotajvards"]
        epasts = request.form["epasts"]
        parole = request.form["parole"]
        atkartotparoli = request.form["atkartotparoli"]

        if not lietotajvards or not epasts or not parole or not atkartotparoli:
            flash("Lūdzu, aizpildiet visus laukus!")
            return redirect(url_for("registrejies"))

        if parole != atkartotparoli:
            flash("Paroles nesakrīt!")
            return redirect(url_for("registrejies"))

        parole_hash = generate_password_hash(parole)

        with sqlite3.connect("datu_baze.db") as savienojums:
            kursors = savienojums.cursor()

            try:
                kursors.execute("INSERT INTO lietotaji (lietotajvards, epasts, parole) VALUES (?, ?, ?)",
                                (lietotajvards, epasts, parole_hash))
                savienojums.commit()
            except sqlite3.IntegrityError:
                flash("Lietotājvārds jau eksistē!")
                return redirect(url_for("registrejies"))

        flash("Reģistrācija veiksmīga!")
        return redirect(url_for("pieslegties"))

    return render_template("register.html")

@app.route("/pieslegties", methods=["GET", "POST"])
def pieslegties():
    if request.method == "POST":
        lietotajvards = request.form["lietotajvards"]
        parole = request.form["parole"]

        if not lietotajvards or not parole:
            flash("Lūdzu, ievadiet lietotājvārdu un paroli!")
            return redirect(url_for("pieslegties"))

        with sqlite3.connect("datu_baze.db") as savienojums:
            kursors = savienojums.cursor()
            kursors.execute("SELECT parole FROM lietotaji WHERE lietotajvards = ?", (lietotajvards,))
            dati = kursors.fetchone()

        if dati and check_password_hash(dati[0], parole):
            session["lietotajvards"] = lietotajvards
            atjauninat_aktivitati(lietotajvards)
            return redirect(url_for("mans_konts"))
        else:
            flash("Nepareizs lietotājvārds vai parole!")
            return redirect(url_for("pieslegties"))

    return render_template("login.html")

def atjauninat_aktivitati(lietotajvards):
    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("UPDATE lietotaji SET aktivitate = CURRENT_TIMESTAMP WHERE lietotajvards = ?", (lietotajvards,))
        savienojums.commit()

@app.route("/mans-konts")
def mans_konts():
    if "lietotajvards" not in session:
        return redirect(url_for("pieslegties"))

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()

        kursors.execute("SELECT id FROM lietotaji WHERE lietotajvards = ?", (session["lietotajvards"],))
        lietotaja_id = kursors.fetchone()

        if lietotaja_id:
            lietotaja_id = lietotaja_id[0]
        else:
            return redirect(url_for("pieslegties"))

        kursors.execute("SELECT id, nosaukums, apraksts, prioritāte, beigu_datums, izpildits FROM uzdevumi WHERE lietotaja_id = ?", (lietotaja_id,))
        uzdevumi = kursors.fetchall()

    with open("citati.json", "r", encoding="utf-8") as f:
        citati = json.load(f)

    random_cits = random.choice(citati)

    html_saturs = render_template("mans_konts.html", lietotajvards=session["lietotajvards"], uzdevumi=uzdevumi, random_cits=random_cits)
    return html_saturs

@app.route("/pievienot-uzdevumu", methods=["POST"])
def pievienot_uzdevumu():
    if "lietotajvards" not in session:
        return redirect(url_for("pieslegties"))

    nosaukums = request.form["nosaukums"]
    apraksts = request.form["apraksts"]
    prioritāte = request.form["prioritate"]
    beigu_datums = request.form["beigu_datums"]

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("INSERT INTO uzdevumi (lietotaja_id, nosaukums, apraksts, prioritāte, beigu_datums, izpildits) VALUES ((SELECT id FROM lietotaji WHERE lietotajvards = ?), ?, ?, ?, ?, 0)",
                        (session["lietotajvards"], nosaukums, apraksts, prioritāte, beigu_datums))
        savienojums.commit()

    atjauninat_aktivitati(session["lietotajvards"])
    return redirect(url_for("mans_konts"))

@app.route("/dzest-uzdevumu/<int:id>", methods=["POST"])
def dzest_uzdevumu(id):
    if "lietotajvards" not in session:
        return redirect(url_for("pieslegties"))

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("DELETE FROM uzdevumi WHERE id = ?", (id,))
        savienojums.commit()

    return redirect(url_for("mans_konts"))

@app.route("/atzimet-izpilditu/<int:id>", methods=["POST"])
def atzimet_izpilditu(id):
    if "lietotajvards" not in session:
        return redirect(url_for("pieslegties"))

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("UPDATE uzdevumi SET izpildits = 1 WHERE id = ?", (id,))
        savienojums.commit()

    return redirect(url_for("mans_konts"))

@app.route("/atslegties")
def atslegties():
    session.pop("lietotajvards", None)
    return redirect(url_for("sakumlapa"))

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "adminparole"

@app.route("/admin-pieslegties", methods=["GET", "POST"])
def admin_pieslegties():
    if request.method == "POST":
        lietotajvards = request.form["lietotajvards"]
        parole = request.form["parole"]

        if lietotajvards == ADMIN_USERNAME and parole == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panelis"))
        else:
            flash("Nepareizs lietotājvārds vai parole!")
            return redirect(url_for("admin_pieslegties"))

    return render_template("admin_login.html")

@app.route("/admin-panelis")
def admin_panelis():
    if "admin" not in session:
        return redirect(url_for("admin_pieslegties"))

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("SELECT id, lietotajvards, epasts, aktivitate FROM lietotaji")
        lietotaji = kursors.fetchall()

    return render_template("admin_panel.html", lietotaji=lietotaji)

@app.route("/dzest-lietotaju/<int:id>", methods=["POST"])
def dzest_lietotaju(id):
    if "admin" not in session:
        return redirect(url_for("admin_pieslegties"))

    with sqlite3.connect("datu_baze.db") as savienojums:
        kursors = savienojums.cursor()
        kursors.execute("DELETE FROM lietotaji WHERE id = ?", (id,))
        savienojums.commit()

    return redirect(url_for("admin_panelis"))

@app.route("/admin-atslegties")
def admin_atslegties():
    session.pop("admin", None)
    return redirect(url_for("sakumlapa"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
