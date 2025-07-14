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
import requests
from bs4 import BeautifulSoup

# === פתרון Render: Web Server קטן על פורט ===
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Beitar bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()

# === הגדרות בסיס ===
TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
TW_BEARER = os.getenv("TW_BEARER_TOKEN")
bot = Bot(token=TOKEN)
twitter = Client(bearer_token=TW_BEARER)

# === מילות מפתח לסינון ===
KEYWORDS = ["בית\"ר", "ביתר", "אברמוב", "יצחקי", "מביתר", "מבית\"ר", "בביתר", "בבית\"ר",
            "גיל כהן", "מיגל סילבה", "ירדן שועה", "עומר אצילי", "סילבה קאני", "טימוטי מוזי", "מוזי",
            "קאני", "שועה", "אצילי", "קאלו", "אילסון", "איילסון", "טבארש", "קראבאלי", "אריאל מנדי"]

# === טעינת מזהים שנשלחו בעבר ===
SENT_FILE = "sent.json"
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        try:
            sent_data = json.load(f)
            if isinstance(sent_data, list):
                sent = set(sent_data)
                twitter_index = 0
            else:
                sent = set(sent_data.get("sent_ids", []))
                twitter_index = sent_data.get("twitter_index", 0)
        except:
            sent = set()
            twitter_index = 0
else:
    sent = set()
    twitter_index = 0

# === עדכון קובץ מזהים ===
def update_sent_file():
    sent_data = {"sent_ids": list(sent), "twitter_index": twitter_index}
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_data, f, ensure_ascii=False)

def mark_sent(id_):
    sent.add(id_)
    update_sent_file()

# === תרגום ===
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

# === בדיקת RSS ===
async def check_rss(name, url):
    print(f"🔍 Checking RSS from {name}")
    feed = feedparser.parse(url)
    print(f"[{name}] נמצאו {len(feed.entries)} פריטים בפיד")
    for e in feed.entries:
        id_ = e.link
        if id_ in sent:
            continue
        combined_text = e.title + e.get("summary", "")
        if any(re.search(k, combined_text, re.IGNORECASE) for k in KEYWORDS):
            title = translate(e.title)
            await send_message(f"{name} 📄\n{title}\n{e.link}")
            mark_sent(id_)

# === ספורט5 — גירוד עמוד במקום RSS ===
async def check_sport5():
    print("🔍 Checking Sport5")
    try:
        url = "https://www.sport5.co.il/liga.aspx?FolderID=44"
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".articleText")
        print(f"[Sport5] נמצאו {len(items)} פריטים")
        for tag in items:
            a = tag.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            link = "https://www.sport5.co.il" + a.get("href")
            if link in sent:
                continue
            if any(k in title for k in KEYWORDS):
                await send_message(f"Sport5 📄\n{title}\n{link}")
                mark_sent(link)
    except Exception as e:
        print("Sport5 error:", e)

# === ספורט1 — גירוד עמוד במקום RSS ===
async def check_sport1():
    print("🔍 Checking Sport1")
    try:
        url = "https://www.sport1.co.il/category/%D7%9B%D7%93%D7%95%D7%A8%D7%92%D7%9C-%D7%99%D7%A9%D7%A8%D7%90%D7%9C%D7%99/"
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".main-article-title a, .articles-list-item-title a")
        print(f"[Sport1] נמצאו {len(items)} פריטים")
        for a in items:
            title = a.get_text(strip=True)
            link = a.get("href")
            if not link.startswith("http"):
                link = "https://www.sport1.co.il" + link
            if link in sent:
                continue
            if any(k in title for k in KEYWORDS):
                await send_message(f"Sport1 📄\n{title}\n{link}")
                mark_sent(link)
    except Exception as e:
        print("Sport1 error:", e)

# === טוויטר — משתמש אחד בכל סיבוב ===
TWITTER_USERS = {
    "saar_ofir": "36787262",
    "fcbeitar": "137186222",
    "NZenziper": "143806331"
}

twitter_user_keys = list(TWITTER_USERS.keys())
last_checked = {user: datetime.min.replace(tzinfo=timezone.utc) for user in TWITTER_USERS}

async def check_twitter():
    global twitter_index
    username = twitter_user_keys[twitter_index]
    user_id = TWITTER_USERS[username]
    now = datetime.now(timezone.utc)

    # הגבלת זמן – פעם ב־15 דקות בלבד
    if now - last_checked[username] < timedelta(minutes=15):
        print(f"⏳ מדלג על @{username}, נבדק לאחרונה לפני פחות מ־15 דקות")
        twitter_index = (twitter_index + 1) % len(twitter_user_keys)
        update_sent_file()
        return

    last_checked[username] = now
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

# === לולאת הריצה ===
async def main_loop():
    print("🏁 Beitar Bot Started Main Loop")
    while True:
        try:
            await check_rss("ONE", "https://www.one.co.il/cat/coop/xml/rss/newsfeed.aspx?t=1")
            await check_sport5()
            await check_sport1()
            await check_rss("וואלה ספורט", "https://rss.walla.co.il/feed/156")
            await check_twitter()
        except Exception as e:
            print("Main loop error:", e)
        await asyncio.sleep(60)

async def main():
    await main_loop()

asyncio.run(main())
