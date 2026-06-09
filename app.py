import os
import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mrperfect-secret-2024")
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
DB = "fitness.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        name TEXT,
        calgoal INTEGER DEFAULT 500
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, date TEXT, exercise TEXT,
        duration INTEGER, calories INTEGER, steps INTEGER,
        heartrate INTEGER, distance REAL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, type TEXT, value REAL, date TEXT,
        UNIQUE(user_id, type)
    )''')
    conn.commit()
    conn.close()

init_db()

def uid(): return session.get("user_id")
def logged_in(): return uid() is not None

@app.route("/")
def home():
    if not logged_in():
        return render_template("auth.html")
    return render_template("index.html")

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get("username","").strip().lower()
    password = data.get("password","")
    name = data.get("name","").strip()
    if not username or not password or not name:
        return jsonify({"error": "All fields required"})
    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
        conn.close()
        return jsonify({"error": "Username already taken"})
    conn.execute("INSERT INTO users (username, password, name) VALUES (?,?,?)",
        (username, generate_password_hash(password), name))
    conn.commit()
    user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    session["user_id"] = user["id"]
    session["user_name"] = name
    conn.close()
    return jsonify({"success": True, "name": name})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username","").strip().lower()
    password = data.get("password","")
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Wrong username or password"})
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return jsonify({"success": True, "name": user["name"]})

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/me")
def me():
    if not logged_in(): return jsonify({"error": "not logged in"}), 401
    conn = get_db()
    user = conn.execute("SELECT name, calgoal FROM users WHERE id=?", (uid(),)).fetchone()
    conn.close()
    return jsonify(dict(user))

@app.route("/settings", methods=["POST"])
def save_settings():
    if not logged_in(): return jsonify({"error": "not logged in"}), 401
    data = request.json
    conn = get_db()
    if "name" in data:
        conn.execute("UPDATE users SET name=? WHERE id=?", (data["name"], uid()))
        session["user_name"] = data["name"]
    if "calgoal" in data:
        conn.execute("UPDATE users SET calgoal=? WHERE id=?", (data["calgoal"], uid()))
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/ask", methods=["POST"])
def ask_coach():
    if not logged_in(): return jsonify({"error": "not logged in"}), 401
    data = request.json
    prompt = f"""You are a friendly, motivating fitness coach.
The user wants help with: {data.get('goal')}
Their details: {data.get('details')}
Give a clear, safe, beginner-friendly workout plan with sets and reps.
Include nutrition tips too. Keep it encouraging!"""
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"response": message.choices[0].message.content})

@app.route("/chat", methods=["POST"])
def chat():
    if not logged_in(): return jsonify({"error": "not logged in"}), 401
    data = request.json
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=1024,
        messages=[{"role": "system", "content": "You are a friendly, motivating personal fitness coach. Give practical, safe advice. Be encouraging and concise."}] + data.get("messages", [])
    )
    return jsonify({"response": message.choices[0].message.content})

@app.route("/quote")
def quote():
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=100,
        messages=[{"role": "user", "content": "Give me one short powerful motivational fitness quote. Just the quote and author, nothing else."}]
    )
    return jsonify({"quote": message.choices[0].message.content})

@app.route("/challenge")
def challenge():
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=200,
        messages=[{"role": "user", "content": "Give me one fun weekly fitness challenge for a teenager. Be specific with numbers. Just the challenge, no intro."}]
    )
    return jsonify({"challenge": message.choices[0].message.content})

@app.route("/log", methods=["POST"])
def log_activity():
    if not logged_in(): return jsonify({"error": "not logged in"}), 401
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO logs (user_id, date, exercise, duration, calories, steps, heartrate, distance) VALUES (?,?,?,?,?,?,?,?)",
        (uid(), str(date.today()), data.get("exercise"), data.get("duration"),
         data.get("calories"), data.get("steps"), data.get("heartrate"), data.get("distance"))
    )
    conn.commit()
    for rtype, rval in [("max_calories", int(data.get("calories") or 0)),
                        ("max_steps", int(data.get("steps") or 0)),
                        ("max_duration", int(data.get("duration") or 0))]:
        row = conn.execute("SELECT value FROM records WHERE user_id=? AND type=?", (uid(), rtype)).fetchone()
        if row is None or rval > row["value"]:
            conn.execute("INSERT OR REPLACE INTO records (user_id, type, value, date) VALUES (?,?,?,?)",
                        (uid(), rtype, rval, str(date.today())))
    conn.commit()
    conn.close()
    return jsonify({"status": "logged"})

@app.route("/logs")
def view_logs():
    if not logged_in(): return jsonify([])
    conn = get_db()
    rows = conn.execute("SELECT * FROM logs WHERE user_id=? ORDER BY id DESC", (uid(),)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/records")
def view_records():
    if not logged_in(): return jsonify([])
    conn = get_db()
    rows = conn.execute("SELECT * FROM records WHERE user_id=?", (uid(),)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/weekly")
def weekly():
    if not logged_in(): return jsonify([])
    conn = get_db()
    rows = conn.execute("SELECT date, calories, steps, duration FROM logs WHERE user_id=? ORDER BY date DESC LIMIT 7", (uid(),)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/export")
def export_csv():
    if not logged_in(): return redirect("/")
    conn = get_db()
    rows = conn.execute("SELECT * FROM logs WHERE user_id=? ORDER BY date DESC", (uid(),)).fetchall()
    conn.close()
    csv = "date,exercise,duration,calories,steps,heartrate,distance\n"
    for r in rows:
        csv += f"{r['date']},{r['exercise']},{r['duration']},{r['calories']},{r['steps']},{r['heartrate']},{r['distance']}\n"
    return app.response_class(csv, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity_log.csv"})

if __name__ == "__main__":
    app.run(debug=True)
