import json
import random
import time
from datetime import datetime
from pathlib import Path
from telegram import Bot
import firebase_admin
from firebase_admin import credentials, db

# ── CONFIG ───────────────────────────────────────
TOKEN       = "8367074937:AAEZxClEC3BBYnu5guTL90tAAthsBA1uqT4"
CHANNEL     = "-1003710231413"
POSTS_PER_BATCH = 1
FIREBASE_JSON   = "promovie-77716-firebase-adminsdk-fbsvc-5a08658719.json"
FIREBASE_URL    = "https://promovie-77716-default-rtdb.firebaseio.com/"
SCHEDULE_HM     = ["22:52", "22:53", "22:55", "22:59"]

POSTED_PATH     = Path("posted_videos.json")
# ─────────────────────────────────────────────────

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_JSON)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})

# Initialize Telegram bot
bot = Bot(token=TOKEN)

# Load already posted videos
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
        if isinstance(m, dict) and (url := m.get("videoUrl")) and url not in posted
    ]
    print(f"[DEBUG] Fetched {len(movies)} movies from Firebase")
    return movies

def send_one_movie(movie):
    title = movie.get("title", "No title")
    poster = movie.get("poster")

    # Generate your website URL
    url_slug = title.lower().replace(" ", "-")
    website_url = f"https://sjofjweawfei.blogspot.com/#movie-{url_slug}"

    caption = f"🎬 {title}\n\n📺 {website_url}"  # use website URL instead of Firebase

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
        posted.add(website_url)  # store website URL as posted
        print(f"Posted → {title}")
        time.sleep(2.5)
        return True
    except Exception as e:
        print(f"Failed → {title:<35}  {type(e).__name__}: {e}")
        return False


def post_batch():
    movies = get_movies_to_post()
    if not movies:
        print("No new videos available")
        return

    print(f"Preparing to send up to {POSTS_PER_BATCH} videos...")
    random.shuffle(movies)

    sent_count = 0
    for m in movies:
        if sent_count >= POSTS_PER_BATCH:
            break
        if send_one_movie(m):
            sent_count += 1

    if sent_count > 0:
        POSTED_PATH.write_text(
            json.dumps(list(posted), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"Batch finished — {sent_count} videos sent")

# ── MAIN LOOP ───────────────────────────────────

def main():
    print("Starting bot...")
    print(f"Channel: {CHANNEL}")
    print(f"Schedule times: {', '.join(SCHEDULE_HM)}")
    print(f"Already posted: {len(posted)} videos")

    try:
        bot.send_message(
            CHANNEL,
            "Bot online • scheduler active 🟢",
            disable_notification=True
        )
        print("Online message sent successfully")
    except Exception as e:
        print("Cannot reach Telegram →", e)
        return

    last_run = ""

    while True:
        now = datetime.now()
        hm = now.strftime("%H:%M")
        print(f"[DEBUG] Current time: {hm}")

        if hm in SCHEDULE_HM and hm != last_run:
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Triggering batch")
            post_batch()
            last_run = hm
            time.sleep(70)  # skip rest of this minute

        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped (Ctrl+C)")
    except Exception as exc:
        print("Main crashed:", exc)
