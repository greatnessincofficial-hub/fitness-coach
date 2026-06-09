import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from groq import Groq
from datetime import date, datetime

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

DB = "fitness.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        exercise TEXT,
        duration INTEGER,
        calories INTEGER,
        steps INTEGER,
        heartrate INTEGER,
        distance REAL
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT UNIQUE,
        value REAL,
        date TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask_coach():
    data = request.json
    goal = data.get("goal")
    details = data.get("details")
    prompt = f"""You are a friendly, motivating fitness coach.
The user wants help with: {goal}
Their details: {details}
Give a clear, safe, beginner-friendly workout plan with sets and reps.
Include nutrition tips too. Keep it encouraging!"""
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return jsonify({"response": message.choices[0].message.content})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    system = "You are a friendly, knowledgeable, and motivating personal fitness coach. Give practical, safe advice. Be encouraging and concise."
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        messages=[{"role": "system", "content": system}] + messages
    )
    return jsonify({"response": message.choices[0].message.content})

@app.route("/quote")
def quote():
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=100,
        messages=[{"role": "user", "content": "Give me one short powerful motivational fitness quote. Just the quote and author, nothing else."}]
    )
    return jsonify({"quote": message.choices[0].message.content})

@app.route("/challenge")
def challenge():
    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=200,
        messages=[{"role": "user", "content": "Give me one fun weekly fitness challenge suitable for a teenager. Be specific with numbers and keep it motivating. Just the challenge, no intro."}]
    )
    return jsonify({"challenge": message.choices[0].message.content})

@app.route("/log", methods=["POST"])
def log_activity():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO logs (date, exercise, duration, calories, steps, heartrate, distance) VALUES (?,?,?,?,?,?,?)",
        (str(date.today()), data.get("exercise"), data.get("duration"),
         data.get("calories"), data.get("steps"), data.get("heartrate"), data.get("distance"))
    )
    conn.commit()
    cal = int(data.get("calories") or 0)
    steps = int(data.get("steps") or 0)
    dur = int(data.get("duration") or 0)
    for rtype, rval in [("max_calories", cal), ("max_steps", steps), ("max_duration", dur)]:
        row = conn.execute("SELECT value FROM records WHERE type=?", (rtype,)).fetchone()
        if row is None or rval > row["value"]:
            conn.execute("INSERT OR REPLACE INTO records (type, value, date) VALUES (?,?,?)",
                        (rtype, rval, str(date.today())))
    conn.commit()
    conn.close()
    return jsonify({"status": "logged"})

@app.route("/logs")
def view_logs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM logs ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/records")
def view_records():
    conn = get_db()
    rows = conn.execute("SELECT * FROM records").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/weekly")
def weekly():
    conn = get_db()
    rows = conn.execute("SELECT date, calories, steps, duration FROM logs ORDER BY date DESC LIMIT 7").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/settings", methods=["GET", "POST"])
def settings():
    conn = get_db()
    if request.method == "POST":
        data = request.json
        for key, value in data.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()
        conn.close()
        return jsonify({"status": "saved"})
    rows = conn.execute("SELECT * FROM settings").fetchall()
    conn.close()
    return jsonify({r["key"]: r["value"] for r in rows})

@app.route("/export")
def export_csv():
    conn = get_db()
    rows = conn.execute("SELECT * FROM logs ORDER BY date DESC").fetchall()
    conn.close()
    csv = "date,exercise,duration,calories,steps,heartrate,distance\n"
    for r in rows:
        csv += f"{r['date']},{r['exercise']},{r['duration']},{r['calories']},{r['steps']},{r['heartrate']},{r['distance']}\n"
    return app.response_class(csv, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity_log.csv"})

if __name__ == "__main__":
    app.run(debug=True)
