import os
import requests
from flask import Flask, render_template, request, jsonify, redirect, session
from groq import Groq
from datetime import date

app = Flask(__name__)
app.secret_key = "fitness-coach-secret"
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

activity_log = []

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

@app.route("/log", methods=["POST"])
def log_activity():
    data = request.json
    entry = {
        "date": str(date.today()),
        "exercise": data.get("exercise"),
        "duration": data.get("duration"),
        "calories": data.get("calories"),
        "steps": data.get("steps"),
        "heartrate": data.get("heartrate"),
        "distance": data.get("distance")
    }
    activity_log.append(entry)
    return jsonify({"status": "logged", "entry": entry})

@app.route("/logs")
def view_logs():
    return jsonify(activity_log)

if __name__ == "__main__":
    app.run(debug=True)
