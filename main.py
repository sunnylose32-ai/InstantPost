import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.responses import PlainTextResponse

from telegram import Bot
from telegram.error import TelegramError

import firebase_admin
from firebase_admin import credentials, db

# ────────────────────────────────────────────────
#               CONFIGURATION
# ────────────────────────────────────────────────

TOKEN = "8367074937:AAEZxClEC3BBYnu5guTL90tAAthsBA1uqT4"
CHANNEL_ID = "-1003710231413"

FIREBASE_CREDENTIALS_FILE = "promovie-77716-firebase-adminsdk-fbsvc-5a08658719.json"
FIREBASE_DATABASE_URL = "https://promovie-77716-default-rtdb.firebaseio.com/"

POSTS_PER_BATCH = 5
DELAY_BETWEEN_MESSAGES = 3.0  # seconds

# Schedule times in "HH:MM" (24h)
SCHEDULE_TIMES = ["22:20", "22:21", "22:23", "22:25"]

POSTED_TRACKER_FILE = Path("posted_videos.json")
# ────────────────────────────────────────────────

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CREDENTIALS_FILE)
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DATABASE_URL})

bot = Bot(token=TOKEN)

# Load posted videos
posted_videos = set()
if POSTED_TRACKER_FILE.is_file():
    try:
        with POSTED_TRACKER_FILE.open("r", encoding="utf-8") as f:
            posted_videos = set(json.load(f))
    except:
        pass

# ── FastAPI app for Render health check ──
app = FastAPI(title="Telegram Poster Bot (Render Free)")

@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "OK"

@app.get("/")
async def root():
    return {"status": "running", "posted_count": len(posted_videos)}

# ── Bot logic (same as before) ──

async def get_unposted_movies() -> list[dict]:
    ref = db.reference("/movies")
    all_data = ref.get() or {}
    return [
        m for m in all_data.values()
        if isinstance(m, dict) and (url := m.get("videoUrl")) and url not in posted_videos
    ]

async def post_batch():
    movies = await get_unposted_movies()
    if not movies:
        print("No unposted movies.")
        return

    print(f"Found {len(movies)} unposted → posting up to {POSTS_PER_BATCH}")
    random.shuffle(movies)

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
                    disable_notification=True
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=caption,
                    parse_mode="Markdown",
                    disable_notification=True
                )

            posted_videos.add(video_url)
            print(f"Posted: {title}")
            sent += 1
            await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

        except TelegramError as te:
            print(f"Telegram fail '{title}': {te}")
        except Exception as ex:
            print(f"Error '{title}': {ex}")

    if sent > 0:
        with POSTED_TRACKER_FILE.open("w", encoding="utf-8") as f:
            json.dump(list(posted_videos), f, ensure_ascii=False, indent=2)
        print(f"Batch complete — {sent} posted")

# ── Background scheduler task ──
async def scheduler_task():
    print("Scheduler started — waiting for times...")
    last_triggered = None

    while True:
        now = datetime.now()
        hm = now.strftime("%H:%M")

        if hm in SCHEDULE_TIMES and hm != last_triggered:
            print(f"[{now}] Triggering batch")
            await post_batch()
            last_triggered = hm
            await asyncio.sleep(70)  # avoid same-minute re-trigger

        await asyncio.sleep(10)

# ── Startup event: launch bot scheduler ──
@app.on_event("startup")
async def startup_event():
    print("Web server starting + launching bot scheduler...")
    try:
        await bot.send_message(
            CHANNEL_ID,
            "Bot online on Render (free web service) 🟢\nScheduler active.",
            disable_notification=True
        )
        print("Online notification sent")
    except Exception as e:
        print(f"Telegram startup notify failed: {e}")

    # Start the scheduler in background
    asyncio.create_task(scheduler_task())

# ── Main entry ──
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Render sets PORT env var
    print(f"Starting uvicorn on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
