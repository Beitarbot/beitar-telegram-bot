# Beitar Telegram Bot

Bot to send filtered news about Beitar Jerusalem from multiple sources to Telegram.

## Usage

- Requires environment variables:
  - `TG_TOKEN`, `TG_CHAT_ID`
  - Twitter API: `TW_API_KEY`, `TW_API_SECRET`, `TW_TOKEN`, `TW_TOKEN_SECRET`

- Deploy on Render:
  - New "Web Service"
  - Build command: `pip install -r requirements.txt`
  - Start command: `python main.py`

Bot checks sources every 5 minutes and sends new filtered posts to Telegram.
