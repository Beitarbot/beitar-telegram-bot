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
SENT_FILE = "sent.json"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent = set(json.load(f))
else:
    sent = set()

def mark_sent(id_):
    sent.add(id_)
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent), f, ensure_ascii=False)

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
KEYWORDS = ["בית\"ר", "ביתר", "אברמוב", "יצחקי"]

async def check_rss(name, url):
    feed = feedparser.parse(url)
    print(f"[{name}] נמצאו {len(feed.entries)} פריטים בפיד")  # כאן ההדפסה
    for e in feed.entries:
        print(f"[{name}] כותרת: {e.title}")  # הדפס כותרות לצורך בדיקה
        id_ = e.link
        if id_ in sent:
            continue
        if any(re.search(k, e.title + e.get("summary", ""), re.IGNORECASE) for k in KEYWORDS):
            title = translate(e.title)
            await send_message(f"{name} 📄\n{title}\n{e.link}")
            mark_sent(id_)

# === ציוצים ממספר משתמשים (ללא סינון) ===
TWITTER_USERS = {
    "saar_ofir": "36787262",
    "fcbeitar": "137186222",
    "NZenziper": "143806331"
}

async def check_twitter():
    for username, user_id in TWITTER_USERS.items():
        try:
            response = twitter.get_users_tweets(
                id=user_id,
                max_results=5,
                tweet_fields=["created_at", "text"]
            )
            tweets = response.data or []
            for tweet in tweets:
                id_ = str(tweet.id)
                if id_ in sent:
                    continue
                await send_message(f"Twitter @{username}\n{tweet.text}")
                mark_sent(id_)
        except Exception as e:
            print(f"Twitter error ({username}):", e)

# === לולאת ריצה אוטומטית ===
async def main_loop():
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

if __name__ == "__main__":
    asyncio.run(main())
