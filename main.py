import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

from telegram import Bot
from telegram.error import TelegramError

import firebase_admin
from firebase_admin import credentials, db

# ────────────────────────────────────────────────
#               CONFIGURATION
# ────────────────────────────────────────────────

TOKEN = "8367074937:AAEZxClEC3BBYnu5guTL90tAAthsBA1uqT4"
CHANNEL_ID = "-1003710231413"               # your channel

FIREBASE_CREDENTIALS_FILE = "promovie-77716-firebase-adminsdk-fbsvc-5a08658719.json"
FIREBASE_DATABASE_URL = "https://promovie-77716-default-rtdb.firebaseio.com/"

POSTS_PER_BATCH = 5
DELAY_BETWEEN_MESSAGES = 3.0                # seconds – prevent flood ban

# Schedule times in "HH:MM" (24h) – add/remove as needed
SCHEDULE_TIMES = ["22:20", "22:21", "22:23", "22:25"]

POSTED_TRACKER_FILE = Path("posted_videos.json")
# ────────────────────────────────────────────────

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CREDENTIALS_FILE)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DATABASE_URL})

bot = Bot(token=TOKEN)

# Load already posted video URLs
posted_videos = set()
if POSTED_TRACKER_FILE.is_file():
    try:
        with POSTED_TRACKER_FILE.open("r", encoding="utf-8") as f:
            posted_videos = set(json.load(f))
    except Exception as e:
        print(f"Could not load posted_videos.json → {e}")

async def get_unposted_movies() -> list[dict]:
    ref = db.reference("/movies")
    all_data = ref.get() or {}
    movies = []

    for key, value in all_data.items():
        if not isinstance(value, dict):
            continue
        video_url = value.get("videoUrl")
        if video_url and video_url not in posted_videos:
            movies.append(value)

    return movies

async def post_batch():
    movies = await get_unposted_movies()

    if not movies:
        print("No unposted movies found.")
        return

    print(f"Found {len(movies)} unposted movies → will post up to {POSTS_PER_BATCH}")

    random.shuffle(movies)  # randomize order

    sent = 0
    for movie in movies:
        if sent >= POSTS_PER_BATCH:
            break

        title = movie.get("title", "No title")
        video_url = movie.get("videoUrl")
        poster_url = movie.get("poster")

        if not video_url:
            continue

        caption = f"🎬 **{title}**\n\n📺 {video_url}"

        try:
            if poster_url:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=poster_url,
                    caption=caption,
                    parse_mode="Markdown",
                    disable_notification=True,
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode="Markdown",
                    disable_notification=True,
                )

            posted_videos.add(video_url)
            print(f"Posted: {title}")

            sent += 1
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

        except TelegramError as te:
            print(f"Telegram error while posting '{title}': {te}")
        except Exception as ex:
            print(f"Unexpected error posting '{title}': {ex}")

    # Save updated list
    if sent > 0:
        with POSTED_TRACKER_FILE.open("w", encoding="utf-8") as f:
            json.dump(list(posted_videos), f, ensure_ascii=False, indent=2)
        print(f"Batch done → {sent} movies posted")


async def main_loop():
    print("Poster bot started")
    print(f"Channel     : {CHANNEL_ID}")
    print(f"Batch size  : {POSTS_PER_BATCH}")
    print(f"Schedule    : {', '.join(SCHEDULE_TIMES)}")
    print(f"Tracked posts: {len(posted_videos)}")

    # Quick online check
    try:
        await bot.send_message(
            CHANNEL_ID,
            "Poster bot online 🟢\nWaiting for scheduled times...",
            disable_notification=True
        )
        print("→ Online message sent")
    except Exception as e:
        print(f"Cannot send to Telegram → check token/channel/permissions!\n{e}")
        return

    last_triggered = None

    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        if current_time in SCHEDULE_TIMES and current_time != last_triggered:
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Starting batch …")
            await post_batch()
            last_triggered = current_time
            await asyncio.sleep(70)  # skip rest of minute + buffer

        await asyncio.sleep(10)  # check every 10 seconds


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as exc:
        print(f"Fatal error: {exc}")
