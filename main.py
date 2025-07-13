import asyncio
import json
import os
import re
import time

from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
import instaloader
import tweepy
import aiohttp

# === הגדרות ===
TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
KEYWORDS = ["בית\"ר", "ביתר", "יצחקי", "אברמוב"]
SENT_FILE = "sent.json"

# === אתחול שליחה ===
bot = Bot(token=TOKEN)

# === טוויטר API (מפתח אישית נדרשת) ===
TW_API_KEY = os.getenv("TW_API_KEY")
TW_API_SECRET = os.getenv("TW_API_SECRET")
TW_TOKEN = os.getenv("TW_TOKEN")
TW_TOKEN_SECRET = os.getenv("TW_TOKEN_SECRET")
auth = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_TOKEN, TW_TOKEN_SECRET)
twitter_api = tweepy.API(auth)

# === אינסטגרם עם instaloader ===
insta = instaloader.Instaloader()

# === תמיכה בתרגום ===
def translate(text):
    try:
        return GoogleTranslator(source='auto', target='he').translate(text)
    except:
        return text

# === ניהול מזהים שנשלחו ===
if os.path.exists(SENT_FILE):
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        sent = set(json.load(f))
else:
    sent = set()

def mark_sent(id_):
    sent.add(id_)
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent), f, ensure_ascii=False)

# === שליחה לטלגרם ===
async def send_message(text, img_url=None):
    if img_url:
        await bot.send_photo(chat_id=CHAT_ID, photo=img_url, caption=text)
    else:
        await bot.send_message(chat_id=CHAT_ID, text=text)

# === RSS וואן ===
async def check_rss(name, url):
    feed = feedparser.parse(url)
    for e in feed.entries:
        id_ = e.link
        if id_ in sent: continue
        if any(re.search(k, e.title, re.IGNORECASE) for k in KEYWORDS):
            title = translate(e.title)
            await send_message(f"{name} 📄\n{title}\n{e.link}")
            mark_sent(id_)

# === טוויטר של אופיר סער ===
async def check_twitter():
    tweets = twitter_api.user_timeline(screen_name="saar_ofir", tweet_mode="extended", count=5)
    for t in tweets:
        id_ = str(t.id)
        if id_ in sent: continue
        text = t.full_text
        if any(k in text for k in KEYWORDS):
            media_url = None
            if 'media' in t.entities:
                media_url = t.entities['media'][0]['media_url_https']
            await send_message(f"Twitter @{t.user.screen_name}\n{text}", media_url)
            mark_sent(id_)

# === אינסטגרם של בית"ר ===
async def check_instagram():
    profile = instaloader.Profile.from_username(insta.context, "beitarfc_official")
    posts = profile.get_posts()
    count = 0
    async for p in posts:
        id_ = p.shortcode
        if id_ in sent: continue
        caption = p.caption or ""
        if any(k in caption for k in KEYWORDS):
            img = p.url
            text = translate(caption)
            await send_message("Instagram Beitar\n" + text, img)
            mark_sent(id_)
        count += 1
        if count >= 5:
            break

# === MAIN LOOP אוטומטי כל 5 דק' ===
async def main_loop():
    while True:
        await check_rss("ONE", "https://www.one.co.il/Feed/RssFeedZone?zone=1")
        await check_rss("Sport5", "https://www.sport5.co.il/rss.aspx?FolderID=2529")
        await check_rss("Sport1", "https://www.sport1.co.il/feed")
        await check_twitter()
        await check_instagram()
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main_loop())
