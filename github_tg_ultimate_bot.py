import asyncio
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
import json
import os
import pytz
import random

# Telegram API credentials (replace with environment variables in production)
API_ID = "29714294"
API_HASH = "bd44a7527bbb8ef23552c569ff3a0d93"
TELEGRAM_TOKEN = "8478146426:AAGPuhgfnqf7JR9I5Cu2pz0EQoFppJOxuYE"
TELEGRAM_CHANNEL_ID = "@GITHUB_MONITOR"
GITHUB_TOKEN = "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"
ADMIN_ID = 5978396634
CHANNEL_LINK = "https://t.me/GITHUB_MONITOR"
MAIN_LINK = "https://t.me/TOOLS_BOTS_KING"
BOT_LINK = "https://t.me/GITHUB_MONITOR_I_BOT"
CHANNEL_TEXT = f"\n🔹CHANNEL 🔹\n👉 <a href='{CHANNEL_LINK}'>Join our Telegram Channel</a>\n👉 <a href='{BOT_LINK}'>Join our Telegram Bot</a>\n👉 <a href='{MAIN_LINK}'>Join our Telegram Main Channel</a>"
POLL_INTERVAL = 30  # seconds

# Initialize Pyrogram client
app = Client("github_bot", api_id=API_ID, api_hash=API_HASH, bot_token=TELEGRAM_TOKEN)

# --- User subscriptions (simple JSON db) ---
SUBS_DB = "subs_db.json"
def load_subs():
    if os.path.exists(SUBS_DB):
        with open(SUBS_DB, "r") as f:
            return json.load(f)
    return {}

def save_subs(data):
    with open(SUBS_DB, "w") as f:
        json.dump(data, f)

# --- Fetch repository languages ---
async def fetch_repo_languages(session, repo_fullname):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    url = f"https://api.github.com/repos/{repo_fullname}/languages"
    try:
        r = await session.get(url, headers=headers)
        r.raise_for_status()
        lang_data = r.json()
        total_bytes = sum(lang_data.values())
        if total_bytes == 0:
            return "No language data available"
        # Calculate percentages and format
        lang_list = [
            (lang, (bytes_count / total_bytes) * 100)
            for lang, bytes_count in lang_data.items()
        ]
        # Sort by percentage (descending) and take top 3
        lang_list = sorted(lang_list, key=lambda x: x[1], reverse=True)[:3]
        return ", ".join(f"{lang}: {percent:.1f}%" for lang, percent in lang_list)
    except Exception as e:
        print(f"Error fetching languages for {repo_fullname}: {e}")
        return "Language data unavailable"

# --- Fetch GitHub events (new repos and push events) ---
async def fetch_github_events(session, last_seen_id):
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    url = "https://api.github.com/events"
    r = await session.get(url, headers=headers)
    r.raise_for_status()
    events = r.json()
    new_events = []
    for event in events:
        if event["type"] in ["CreateEvent", "PushEvent"]:
            event_id = event["id"]
            if last_seen_id is not None and event_id == last_seen_id:
                break
            new_events.append(event)
    return new_events[::-1]

def format_new_repo(event):
    repo = event["repo"]["name"]
    repo_url = f"https://github.com/{repo}"
    author = event["actor"]["login"]
    author_url = f"https://github.com/{author}"
    date = event["created_at"]
    date_fmt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"🆕 <b>New GitHub Repository Alert</b> 🆕\n"
        f"➡️ <b>Repository:</b> <a href='{repo_url}'>{repo}</a>\n"
        f"👤 <b>Created by:</b> <a href='{author_url}'>{author}</a>\n"
        f"🕒 <b>Date:</b> {date_fmt}\n{CHANNEL_TEXT}"
    )

async def format_push_event(session, event):
    repo = event["repo"]["name"]
    repo_url = f"https://github.com/{repo}"
    author = event["actor"]["login"]
    author_url = f"https://github.com/{author}"
    commit_count = len(event["payload"]["commits"])
    branch = event["payload"]["ref"].replace("refs/heads/", "")
    commit_url = f"{repo_url}/commits/{branch}"
    date = event["created_at"]
    date_fmt = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M UTC")
    message = event["payload"]["commits"][0]["message"] if commit_count > 0 else "No commit message"
    # Fetch languages
    languages = await fetch_repo_languages(session, repo)
    return (
        f"📝 <b>Code Update Alert for {repo}</b> 📝\n\n"
        f"➡️ <b>Repository:</b> <a href='{repo_url}'>{repo}</a>\n"
        f"🖥️ <b>Languages:</b> {languages}\n"
        f"🔗 <b>Commits:</b> <a href='{commit_url}'>{commit_count} new commit(s)</a>\n"
        f"👤 <b>Pushed by:</b> <a href='{author_url}'>{author}</a>\n"
        f"🌿 <b>Branch:</b> {branch}\n"
        f"📜 <b>Message:</b> <i>{message[:100]}{'...' if len(message) > 100 else ''}</i>\n"
        f"🕒 <b>Date:</b> {date_fmt}\n{CHANNEL_TEXT}"
    )

# --- Trending Scraper (for user commands only) ---
async def fetch_github_trending(language: str = "", since: str = "daily"):
    url = f"https://github.com/trending/{language}?since={since}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")
        repos = []
        for repo_item in soup.find_all("article", class_="Box-row")[:10]:
            repo_name = repo_item.h2.text.strip().replace("\n", "").replace(" ", "")
            repo_url = "https://github.com/" + repo_name
            desc_tag = repo_item.p
            desc = desc_tag.text.strip() if desc_tag else "No description available"
            stars_tag = repo_item.find("a", attrs={"href": lambda x: x and x.endswith("/stargazers")})
            stars = stars_tag.text.strip() if stars_tag else "0"
            repos.append((repo_name, repo_url, desc, stars))
        return repos

def format_trending_message(period: str, trending, items_list=None):
    msg = f"🔥 <b>{items_list.get('title', f'GitHub Trending Repositories ({period.title()})')}</b> 🔥\n\n"
    for i, (name, url, desc, stars) in enumerate(trending, 1):
        msg += f"{i}. <a href='{url}'>{name}</a> ⭐ {stars}\n   ↳ <i>{desc}</i>\n\n"
    msg += CHANNEL_TEXT
    return msg

# --- Search (for user commands only) ---
async def search_repos(keyword):
    url = f"https://api.github.com/search/repositories?q={keyword}&sort=stars&order=desc"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)
        items = r.json().get("items", [])[:5]
    return items

# --- Random repo (for user commands only) ---
async def get_random_repo():
    trending = await fetch_github_trending(since="monthly")
    return random.choice(trending) if trending else None

# --- Background job for new repos and push events ---
async def background_job():
    last_seen_id = None
    async with httpx.AsyncClient() as session:
        while True:
            try:
                if not channel_enabled:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                # Fetch GitHub events
                events = await fetch_github_events(session, last_seen_id)
                if events:
                    last_seen_id = events[-1]["id"]
                    for event in events:
                        if event["type"] == "CreateEvent" and event["payload"]["ref_type"] == "repository":
                            msg = format_new_repo(event)
                            await app.send_message(
                                TELEGRAM_CHANNEL_ID,
                                msg,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=False
                            )
                            # User subscriptions
                            db = load_subs()
                            for uid, keywords in db.items():
                                langmatches = []
                                repo_name = event['repo']['name'].lower().split('/')[-1]
                                if repo_name in keywords:
                                    langmatches.append(repo_name)
                                for word in keywords:
                                    if word.lower() in repo_name:
                                        langmatches.append(word)
                                if langmatches:
                                    try:
                                        await app.send_message(
                                            int(uid),
                                            f"🔔 <b>Subscribed Alert</b> 🔔\n{msg}",
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=False
                                        )
                                    except Exception as e:
                                        print(f"Error sending subscription alert to {uid}: {e}")
                        elif event["type"] == "PushEvent":
                            msg = await format_push_event(session, event)
                            await app.send_message(
                                TELEGRAM_CHANNEL_ID,
                                msg,
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=False
                            )
                            # User subscriptions for push events
                            db = load_subs()
                            for uid, keywords in db.items():
                                langmatches = []
                                repo_name = event['repo']['name'].lower().split('/')[-1]
                                if repo_name in keywords:
                                    langmatches.append(repo_name)
                                for word in keywords:
                                    if word.lower() in repo_name:
                                        langmatches.append(word)
                                if langmatches:
                                    try:
                                        await app.send_message(
                                            int(uid),
                                            f"🔔 <b>Subscribed Alert</b> 🔔\n{msg}",
                                            parse_mode=ParseMode.HTML,
                                            disable_web_page_preview=False
                                        )
                                    except Exception as e:
                                        print(f"Error sending subscription alert to {uid}: {e}")
                        await asyncio.sleep(2)
                await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                print(f"Error in background job: {e}")
                await asyncio.sleep(POLL_INTERVAL)

# --- Telegram Bot Handlers (user-to-user only) ---
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text(
        "👋 <b>Welcome to GitHub Ultimate Watcher Bot</b> 👋\n"
        "Stay updated with the latest GitHub activities!\n\n"
        "<b>Available Commands:</b>\n"
        "🔹 /trending [daily|weekly|monthly|yearly] - View trending repositories\n"
        "🔹 /search <keyword> - Search for repositories\n"
        "🔹 /subscribe <language|keyword> - Subscribe to alerts\n"
        "🔹 /unsubscribe <language|keyword> - Unsubscribe from alerts\n"
        "🔹 /my_subs - List your subscriptions\n"
        "🔹 /randomrepo - Discover a random repository\n"
        "🔹 /digest - Get today's trending digest\n"
        f"{CHANNEL_TEXT}",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("trending") & filters.private)
async def trending_command(client, message):
    args = message.command[1:] if len(message.command) > 1 else []
    period = args[0] if args and args[0] in ["daily", "weekly", "monthly", "yearly"] else "daily"
    trending = await fetch_github_trending(since=period)
    msg = format_trending_message(period, trending)
    await message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

@app.on_message(filters.command("search") & filters.private)
async def search_command(client, message):
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ <b>Error:</b> Please provide a keyword\n"
            f"📋 <b>Usage:</b> /search <keyword>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
        return
    keyword = " ".join(message.command[1:])
    items = await search_repos(keyword)
    if not items:
        await message.reply_text(
            f"🔎 <b>Search Results for '{keyword}'</b>\n"
            f"❌ No repositories found.{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
        return
    msg = f"🔎 <b>Top Repositories for '{keyword}'</b> 🔎\n\n"
    for i, item in enumerate(items, 1):
        msg += (
            f"{i}. <a href='{item['html_url']}'>{item['full_name']}</a>\n"
            f"   ⭐ <b>Stars:</b> {item['stargazers_count']}\n"
            f"   📝 <b>Description:</b> <i>{item.get('description', 'No description available')}</i>\n\n"
        )
    msg += CHANNEL_TEXT
    await message.reply_text(msg, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("subscribe") & filters.private)
async def subscribe_command(client, message):
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ <b>Error:</b> Please provide a keyword\n"
            f"📋 <b>Usage:</b> /subscribe <language|keyword>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
        return
    keyword = message.command[1].lower()
    user_id = str(message.from_user.id)
    db = load_subs()
    db.setdefault(user_id, [])
    if keyword not in db[user_id]:
        db[user_id].append(keyword)
        save_subs(db)
        await message.reply_text(
            f"✅ <b>Subscription Added</b> ✅\n"
            f"Subscribed to: <b>{keyword}</b>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            f"⚠️ <b>Already Subscribed</b>\n"
            f"You are already subscribed to: <b>{keyword}</b>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command("unsubscribe") & filters.private)
async def unsubscribe_command(client, message):
    if len(message.command) < 2:
        await message.reply_text(
            f"❌ <b>Error:</b> Please provide a keyword\n"
            f"📋 <b>Usage:</b> /unsubscribe <language|keyword>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
        return
    keyword = message.command[1].lower()
    user_id = str(message.from_user.id)
    db = load_subs()
    if user_id in db and keyword in db[user_id]:
        db[user_id].remove(keyword)
        save_subs(db)
        await message.reply_text(
            f"❌ <b>Subscription Removed</b> ❌\n"
            f"Unsubscribed from: <b>{keyword}</b>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.reply_text(
            f"⚠️ <b>Not Subscribed</b>\n"
            f"You are not subscribed to: <b>{keyword}</b>{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command("my_subs") & filters.private)
async def my_subs_command(client, message):
    user_id = str(message.from_user.id)
    db = load_subs()
    subs = db.get(user_id, [])
    if not subs:
        await message.reply_text(
            f"📋 <b>Your Subscriptions</b>\n"
            f"❌ You have no subscriptions.{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )
    else:
        subs_list = "\n".join(f"🔹 {sub}" for sub in subs)
        await message.reply_text(
            f"📋 <b>Your Subscriptions</b> 📋\n"
            f"{subs_list}{CHANNEL_TEXT}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command("randomrepo") & filters.private)
async def random_repo_command(client, message):
    repo = await get_random_repo()
    if repo:
        name, url, desc, stars = repo
        msg = (
            f"🎲 <b>Random Cool Repository</b> 🎲\n"
            f"➡️ <b>Repository:</b> <a href='{url}'>{name}</a>\n"
            f"⭐ <b>Stars:</b> {stars}\n"
            f"📝 <b>Description:</b> <i>{desc}</i>\n"
            f"{CHANNEL_TEXT}"
        )
    else:
        msg = f"❌ <b>Error:</b> Could not fetch random repository.{CHANNEL_TEXT}"
    await message.reply_text(msg, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("digest") & filters.private)
async def digest_command(client, message):
    trending = await fetch_github_trending(since="daily")
    msg = format_trending_message("daily", trending, custom_title="Daily Digest: Top Trending Repositories")
    await message.reply_text(
        f"📬 <b>Daily Digest</b> 📬\n{msg}{CHANNEL_TEXT}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=False
    )

# --- Admin control for channel messages ---
@app.on_message(filters.command("toggle_channel") & filters.user(ADMIN_ID) & filters.private)
async def toggle_channel_command(client, message):
    global channel_enabled
    channel_enabled = not channel_enabled
    status = "enabled" if channel_enabled else "disabled"
    await message.reply_text(
        f"✅ <b>Channel Posting {status.capitalize()}</b>\n"
        f"Channel messages to {TELEGRAM_CHANNEL_ID} are now {status}.{CHANNEL_TEXT}",
        parse_mode=ParseMode.HTML
    )

# --- Main ---
channel_enabled = True  # Default state for channel posting
async def main():
    try:
        await app.start()
        print("Bot started!")
        asyncio.create_task(background_job())
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        await app.stop()
        print("Bot stopped!")

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            print("Running in existing event loop")
            loop.create_task(main())
            while True:
                loop.run_until_complete(asyncio.sleep(3600))
        else:
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error running bot: {e}")