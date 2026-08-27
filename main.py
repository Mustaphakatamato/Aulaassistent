import asyncio
import datetime
import json
import os
import ssl
import urllib.error
import urllib.request
import zoneinfo
from pathlib import Path
import aula.cli
from aula import FileTokenStorage

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8660574815:AAFxw-D8pV_j7Li97QJyU0XU9UfwhZaNxsU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6103108909")

async def send_telegram(tekst):
    """Sender den færdige briefing direkte til din Telegram-app."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN.strip()}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID.strip(),
        "text": tekst,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url, 
        data=payload, 
        headers={"Content-Type": "application/json"}
    )
    
    context = ssl._create_unverified_context()
    try:
        urllib.request.urlopen(req, context=context)
    except urllib.error.HTTPError as e:
        error_detail = e.read().decode("utf-8")
        print(f"\n❌ Telegram API Afvist (Fejl {e.code}): {error_detail}")
        raise e

async def main():
    print("1. Henter Aula-data...")
    
    # Læs token direkte fra GitHub Secret
    env_token = os.getenv("AULA_TOKENS_JSON")
    if env_token and env_token.strip():
        token_data = json.loads(env_token)
    else:
        storage = FileTokenStorage(aula.cli.DEFAULT_TOKEN_FILE)
        token_data = await storage.load()

    if not token_data:
        raise ValueError("Kunne ikke finde gyldige Aula-tokens i systemet.")

    client = await aula.create_client(token_data)
    profile = await client.get_profile()
    
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.datetime.now(tz)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    
    child_ids = [c.id for c in profile.children] if hasattr(profile, 'children') and profile.children else []
    
    events = []
    if child_ids:
        try:
            events = await client.get_calendar_events(child_ids, day_start, day_end)
        except Exception:
            events = []

    taske_husk = set()
    skema_punkter = []
    
    for ev in events:
        titel = getattr(ev, 'title', '') or ''
        start_tid = ev.start_datetime.strftime("%H:%M") if hasattr(ev, 'start_datetime') and ev.start_datetime else ""
        end_tid = ev.end_datetime.strftime("%H:%M") if hasattr(ev, 'end_datetime') and ev.end_datetime else ""
        
        tid_str = f"{start_tid}-{end_tid}" if start_tid else ""
        skema_punkter.append(f"• {tid_str} {titel}".strip())
        
        titel_lower = titel.lower()
        if any(k in titel_lower for k in ["idræt", "gymnastik", "sport"]):
            taske_husk.add("👟 Idrætstøj & håndklæde")
        if any(k in titel_lower for k in ["svøm", "svømning"]):
            taske_husk.add("🏊‍♂️ Svømmetøj & badehætte")
        if any(k in titel_lower for k in ["tur", "skov", "udflugt"]):
            taske_husk.add("🍎 Turmadpakke & ekstra drikkedunk")

    try:
        unread_threads = await client.get_message_threads(filter_on="unread")
    except Exception:
        unread_threads = []
        
    threads = unread_threads if unread_threads else await client.get_message_threads()
    
    dato_str = now.strftime("%d/%m-%Y")
    briefing = f"☀️ *AULA MORGEN-BRIEFING* ({dato_str})\n\n"
    
    briefing += "🎒 *HUSK I TASKEN:*\n"
    if taske_husk:
        for item in taske_husk:
            briefing += f"• {item}\n"
    else:
        briefing += "• Ingen særlige ting fundet i skemaet i dag.\n"

    briefing += "\n📅 *DAGENS SKEMA:*\n"
    if skema_punkter:
        for pkt in skema_punkter[:5]:
            briefing += f"{pkt}\n"
    else:
        briefing += "• Ingen skema-aktiviteter i dag.\n"
        
    msg_overskrift = "🔴 *ULÆSTE BESKEDER:*" if unread_threads else "📥 *SENESTE BESKEDER:*"
    briefing += f"\n{msg_overskrift}\n"
    for thread in threads[:3]:
        sender = getattr(thread, 'creator_name', None) or getattr(thread, 'author', None)
        fra_tekst = f" (_Fra: {sender}_)" if sender else ""
        clean_subject = str(thread.subject).replace("*", "").replace("_", "")
        briefing += f"• *{clean_subject}*{fra_tekst}\n"
        
    print("Sender briefing til Telegram...")
    await send_telegram(briefing)
    print("🚀 Sendt!")

asyncio.run(main())
