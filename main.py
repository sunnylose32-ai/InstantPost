import json
import random
import time
import os
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask
from telegram import Bot
import firebase_admin
from firebase_admin import credentials, db

# ── CONFIG ───────────────────────────────────────
TOKEN       = "8367074937:AAEZxClEC3BBYnu5guTL90tAAthsBA1uqT4"
CHANNEL     = "-1003710231413"
POSTS_PER_BATCH = 1
FIREBASE_JSON   = "promovie-77716-firebase-adminsdk-fbsvc-5a08658719.json"
FIREBASE_URL    = "https://promovie-77716-default-rtdb.firebaseio.com/"
SCHEDULE_HM = ["22:52", "22:53", "22:55", "22:59"]
POSTED_PATH = Path("posted_videos.json")
# ─────────────────────────────────────────────────

# ── INIT FIREBASE ────────────────────────────────
cred = credentials.Certificate(FIREBASE_JSON)
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_URL
})

# ── INIT TELEGRAM ───────────────────────────────
bot = Bot(token=TOKEN)

# ── LOAD POSTED RECORD ──────────────────────────
posted = set()
if POSTED_PATH.exists():
    try:
        posted = set(json.loads(POSTED_PATH.read_text(encoding="utf-8")))
    except Exception as e:
        print("Failed to load posted videos:", e)

# ── FUNCTIONS ───────────────────────────────────

def get_movies_to_post():
    ref = db.reference("/movies")
    data = ref.get() or {}
    movies = [
        m for m in data.values()
        if isinstance(m, dict)
        and m.get("videoUrl")
        and m.get("videoUrl") not in posted
    ]
    print(f"[DEBUG] {len(movies)} movies fetched")
    return movies


def send_one_movie(movie):
    title = movie.get("title", "No title")
    poster = movie.get("poster")

    url_slug = title.lower().replace(" ", "-")
    website_url = f"https://sjofjweawfei.blogspot.com/#movie-{url_slug}"

    caption = f"🎬 {title}\n\n📺 {website_url}"

    try:
        if poster:
            bot.send_photo(
                chat_id=CHANNEL,
                photo=poster,
                caption=caption,
                disable_notification=True
            )
        else:
            bot.send_message(
                chat_id=CHANNEL,
                text=caption,
                disable_notification=True
            )

        posted.add(movie.get("videoUrl"))
        print(f"Posted → {title}")
        time.sleep(2)
        return True

    except Exception as e:
        print(f"Failed → {title}: {e}")
        return False


def post_batch():
    movies = get_movies_to_post()
    if not movies:
        print("No new movies")
        return

    random.shuffle(movies)

    sent = 0
    for movie in movies:
        if sent >= POSTS_PER_BATCH:
            break
        if send_one_movie(movie):
            sent += 1

    if sent > 0:
        POSTED_PATH.write_text(
            json.dumps(list(posted), indent=2),
            encoding="utf-8"
        )
        print(f"Batch complete — {sent} sent")


def scheduler():
    print("Scheduler started")
    last_run = ""

    while True:
        now = datetime.now()
        hm = now.strftime("%H:%M")

        if hm in SCHEDULE_HM and hm != last_run:
            print(f"Triggering batch at {hm}")
            post_batch()
            last_run = hm
            time.sleep(60)

        time.sleep(5)

# ── FLASK (FOR RENDER FREE PLAN) ────────────────

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_bot():
    print("Bot thread starting...")
    scheduler()

if __name__ == "__main__":
    # Start scheduler in background thread
    threading.Thread(target=run_bot).start()

    # Start Flask web server (required by Render free)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
