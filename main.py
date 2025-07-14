import asyncio
import json
import os
import re
import feedparser
from telegram import Bot
from deep_translator import GoogleTranslator
from tweepy import Client
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone

# === פתרון Render: Web Server קטן על פורט ===
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Beitar bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))  # Render יגדיר PORT
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# === הגדרות בסיס ===
TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
TW_BEARER = os.getenv("TW_BEARER_TOKEN")
bot = Bot(token=TOKEN)
twitter = Client(bearer_token=TW_BEARER)

# === מזהים שנשלחו למניעת כפילויות ===
def update_sent_file():
    sent_data["sent_ids"] = list(sent)
    sent_data["twitter_index"] = twitter_index
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_data, f, ensure_ascii=False)
        
SENT_FILE = "sent.json"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent = set(json.load(f))
else:
    sent_data = {"sent_ids": [], "twitter_index": 0}
    if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent_data = json.load(f)
        sent = set(sent_data.get("sent_ids", []))
        twitter_index = sent_data.get("twitter_index", 0)


def mark_sent(id_):
    sent.add(id_)
    update_sent_file()

# === תרגום לעברית (למקורות מחו"ל) ===
def translate(text):
    try:
        return GoogleTranslator(source='auto', target='he').translate(text)
    except:
        return text

# === שליחת הודעה לטלגרם ===
async def send_message(text, img_url=None):
    try:
        if img_url:
            await bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=text)
        else:
            await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print("Telegram error:", e)

# === בדיקת RSS כללי (עם סינון) ===
KEYWORDS = ["בית\"ר", "ביתר", "אברמוב", "יצחקי", "מביתר", "מבית\"ר", "בביתר", "בבית\"ר"]

async def check_rss(name, url):
    print(f"🔍 Checking RSS from {name}")
    feed = feedparser.parse(url)
    print(f"[{name}] נמצאו {len(feed.entries)} פריטים בפיד")
    for e in feed.entries:
        print(f"[{name}] כותרת: {e.title}")
        id_ = e.link
        if id_ in sent:
            continue
        combined_text = e.title + e.get("summary", "")
        if any(re.search(k, combined_text, re.IGNORECASE) for k in KEYWORDS):
            title = translate(e.title)
            await send_message(f"{name} 📄\n{title}\n{e.link}")
            mark_sent(id_)
        else:
            print(f"[{name}] ⛔️ לא נשלח – לא נמצא מילות מפתח")


# === ציוצים ממספר משתמשים (ללא סינון) ===
TWITTER_USERS = {
    "saar_ofir": "36787262",
    "fcbeitar": "137186222",
    "NZenziper": "143806331"
}

twitter_user_keys = list(TWITTER_USERS.keys())
twitter_index = 0  # זה נשמר גלובלית

async def check_twitter():
    global twitter_index
    username = twitter_user_keys[twitter_index]
    user_id = TWITTER_USERS[username]
    twitter_index = (twitter_index + 1) % len(twitter_user_keys)
    update_sent_file()


    print(f"🐦 Checking Twitter user @{username}")

    try:
        response = twitter.get_users_tweets(
            id=user_id,
            max_results=5,
            tweet_fields=["created_at", "text", "attachments"],
            expansions=["attachments.media_keys"],
            media_fields=["url", "preview_image_url"]
        )
        tweets = response.data or []
        media = {}
            if response.includes and "media" in response.includes:
            media = {m.media_key: m for m in response.includes["media"]}


        today = datetime.now(timezone.utc).date()

        for tweet in tweets:
            if tweet.created_at.date() != today:
                continue

            id_ = str(tweet.id)
            if id_ in sent:
                continue

            text = tweet.text
            img_url = None

            if hasattr(tweet, "attachments") and "media_keys" in tweet.attachments:
                for key in tweet.attachments["media_keys"]:
                    m = media.get(key)
                    if m and hasattr(m, "url"):
                        img_url = m.url
                        break

            await send_message(f"Twitter @{username}\n{text}", img_url)
            mark_sent(id_)
            print(f"✅ נשלח ציוץ: {text[:40]}...")

    except Exception as e:
        print(f"Twitter error ({username}):", e)



# === לולאת ריצה אוטומטית ===
async def main_loop():
    print("🏁 Beitar Bot Started Main Loop")  # שורת בדיקה
    while True:
        try:
            await check_rss("ONE", "https://www.one.co.il/cat/coop/xml/rss/newsfeed.aspx?t=1")
            await check_rss("Sport5", "https://www.sport5.co.il/rss.aspx?FolderID=2529")
            await check_rss("Sport1", "https://www.sport1.co.il/feed")
            await check_rss("וואלה ספורט", "https://rss.walla.co.il/feed/156")
            await check_twitter()
        except Exception as e:
            print("Main loop error:", e)
        await asyncio.sleep(60)  # כל 1 דקות

# === התחלה ===
async def main():
    await main_loop()

# תמיד להריץ, גם אם לא מריצים עם `python main.py`
asyncio.run(main())

