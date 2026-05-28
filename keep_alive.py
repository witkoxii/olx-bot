"""
Mini serwer www - pozwala UptimeRobot pingować bota żeby działał 24/7.
Uruchom razem z botem.
"""
from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot iPhone Alert dziala! 🤖"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
