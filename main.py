import asyncio
import json
import os
import re
import feedparser
import aiohttp
from telegram import Bot
from deep_translator import GoogleTranslator
from tweepy import Client
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta
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
            "קאני", "שועה", "אצילי", "קאלו", "אילסון", "איילסון", "זסנו", "קראבאלי", "אריאל מנדי"]

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

def update_sent_file():
    sent_data = {"sent_ids": list(sent), "twitter_index": twitter_index}
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent_data, f, ensure_ascii=False)

def mark_sent(id_):
    sent.add(id_)
    update_sent_file()

def translate(text):
    try:
        return GoogleTranslator(source='auto', target='he').translate(text)
    except:
        return text

async def send_message(text, img_url=None):
    try:
        if img_url:
            await bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=text)
        else:
            await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception as e:
        print("Telegram error:", e, flush=True)

# === בדיקת RSS ===
async def check_rss(name, url):
    print(f"\U0001F50D נכנס ל־check_rss עבור {name}", flush=True)
    feed = feedparser.parse(url)
    print(f"[{name}] נמצאו {len(feed.entries)} פריטים בפיד", flush=True)
    for e in feed.entries:
        id_ = e.link
        if id_ in sent:
            continue
        combined_text = e.title + e.get("summary", "")
        if any(re.search(k, combined_text, re.IGNORECASE) for k in KEYWORDS):
            title = translate(e.title)
            await send_message(f"{name} 📄\n{title}\n{e.link}")
            print(f"📤 {name} — נשלחת כותרת: {title}", flush=True)
            mark_sent(id_)
        else:
            print(f"[{name}] ❌ אין מילות מפתח בכותרת: \"{e.title}\"", flush=True)

# === ספורט5 ===
async def check_sport5():
    print("🔍 נכנס ל־check_sport5", flush=True)
    url = "https://www.sport5.co.il/"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select(".article-list h2 a, .mainarticle-league h2 a")
        print(f"[Sport5] נמצאו {len(items)} פריטים", flush=True)
    except Exception as e:
        print(f"[Sport5] שגיאה בהורדת עמוד הבית: {e}", flush=True)
        return

    for a in items:
        title = a.get_text(strip=True)
        link = a.get("href")
        if not link or not link.startswith("/"):
            continue
        link = "https://www.sport5.co.il" + link
        if link in sent:
            continue

        try:
            article_res = requests.get(link, timeout=10)
            article_soup = BeautifulSoup(article_res.text, "html.parser")
            paragraphs = article_soup.select("div.articleText p")
            body = " ".join(p.get_text(strip=True) for p in paragraphs)
        except Exception as e:
            print(f"[Sport5] שגיאה בשליפת תוכן מ־{link}: {e}", flush=True)
            body = ""

        full_text = title + " " + body
        print(f"[Sport5] 🔍 נבדקת כותרת: \"{title}\"", flush=True)
        if any(k in full_text for k in KEYWORDS):
            await send_message(f"Sport5 📄\n{title}\n{link}")
            print(f"📤 Sport5 — נשלחת כותרת: {title}", flush=True)
            mark_sent(link)
        else:
            print(f"[Sport5] ❌ אין מילות מפתח בכותרת: \"{title}\"", flush=True)

# === ספורט1 ===
async def check_sport1():
    print("🔍 נכנס ל־check_sport1", flush=True)
    url = "https://sport1.maariv.co.il/israeli-soccer/"
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        items = soup.select("article a")
        print(f"[Sport1] נמצאו {len(items)} פריטים", flush=True)
    except Exception as e:
        print(f"[Sport1] שגיאה בהורדת עמוד הבית: {e}", flush=True)
        return

    for a in items:
        title = a.get_text(strip=True)
        link = a.get("href")
        if not link or not link.startswith("http"):
            continue
        if link in sent:
            continue

        try:
            article_res = requests.get(link, timeout=10)
            article_soup = BeautifulSoup(article_res.text, "html.parser")
            paragraphs = article_soup.select("div.textSection p")
            body = " ".join(p.get_text(strip=True) for p in paragraphs)
        except Exception as e:
            print(f"[Sport1] שגיאה בשליפת תוכן מ־{link}: {e}", flush=True)
            body = ""

        full_text = title + " " + body
        if any(k in full_text for k in KEYWORDS):
            await send_message(f"Sport1 📄\n{title}\n{link}")
            print(f"📤 Sport1 — נשלחת כותרת: {title}", flush=True)
            mark_sent(link)
        else:
            print(f"[Sport1] ❌ אין מילות מפתח בכותרת: \"{title}\"", flush=True)

# === טוויטר ===
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

    if now - last_checked[username] < timedelta(minutes=40):
        print(f"⏳ מדלג על @{username}, נבדק לאחרונה לפני פחות מ־40 דקות", flush=True)
        twitter_index = (twitter_index + 1) % len(twitter_user_keys)
        update_sent_file()
        return

    last_checked[username] = now
    twitter_index = (twitter_index + 1) % len(twitter_user_keys)
    update_sent_file()

    print(f"🐦 נכנס ל־check_twitter עבור @{username}", flush=True)

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

            if any(re.search(k, text, re.IGNORECASE) for k in KEYWORDS):
                await send_message(f"Twitter @{username}\n{text}", img_url)
                print(f"✅ נשלח ציוץ: {text[:40]}...", flush=True)
                mark_sent(id_)
            else:
                print(f"[Twitter @{username}] ❌ אין מילות מפתח בציוץ: \"{text[:40]}...\"", flush=True)

    except Exception as e:
        print(f"Twitter error ({username}):", e, flush=True)

# === פינג עצמי לשמירה על פעילות ב־Render ===
async def ping_self():
    url = os.getenv("SELF_URL")
    if not url:
        print("⚠️ SELF_URL not set. Skipping ping.", flush=True)
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                print(f"🌐 Pinged self: {resp.status}", flush=True)
    except Exception as e:
        print(f"Ping error: {e}", flush=True)

async def keep_alive_loop():
    while True:
        await ping_self()
        await asyncio.sleep(840)  # כל 14 דקות

# === לולאת הריצה הראשית ===
async def main_loop():
    print("🏁 Beitar Bot Started Main Loop ✅", flush=True)
    while True:
        try:
            print("🔄 Beginning new loop iteration", flush=True)
            await check_rss("ONE", "https://www.one.co.il/cat/coop/xml/rss/newsfeed.aspx?t=1")
            await check_sport5()
            await check_sport1()
            await check_rss("וואלה ספורט", "https://rss.walla.co.il/feed/156")
            await check_twitter()
        except Exception as e:
            print("❌ Main loop error:", e, flush=True)
        await asyncio.sleep(60)

# === הפעלת שתי הלולאות בו־זמנית ===
async def main():
    await asyncio.gather(
        main_loop(),
        keep_alive_loop()
    )

# === הפעלה ===
asyncio.run(main())

