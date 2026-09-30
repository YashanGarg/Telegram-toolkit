# chat analyzers data could be used to train chat bots or extract useful info (write this in better way)
# you could use this to generate your own data for trainng purposes


import os
import sys
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

# Import shared credentials from config.py
from config import API_ID, API_HASH, SOURCE_GROUP

# ==========================================
# 1. DIRECTORY & SCRIPT CONFIGURATION
# ==========================================
DATA_EXPORT_DIR = "data_exports"
TRACKING_DIR = os.path.join("tracking", "analyzer")

EXPORT_FILE = os.path.join(DATA_EXPORT_DIR, "chat_history.jsonl")
PROGRESS_FILE = os.path.join(TRACKING_DIR, "analyzer_bookmark.txt")
LOG_FILE = os.path.join(TRACKING_DIR, "analyzer_errors.log")

MAX_RETRIES = 3

processed_count = 0
skipped_count = 0

client = TelegramClient('forwarder_session', API_ID, API_HASH)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def setup_directories():
    os.makedirs(DATA_EXPORT_DIR, exist_ok=True)
    os.makedirs(TRACKING_DIR, exist_ok=True)

def get_last_processed_id():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    return 0

def save_progress(message_id):
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(message_id))

def log_error(message_id, error_msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"Message ID: {message_id} | Error: {error_msg}\n")

def get_media_type(message):
    if not message.media: return None
    if message.photo: return "photo"
    if message.video: return "video"
    if message.voice: return "voice"
    if message.audio: return "audio"
    if message.document: return "document"
    if message.sticker: return "sticker"
    if message.gif: return "gif"
    return "other_media"

def extract_urls(message):
    """Extracts raw URLs and hyperlink text for network/security analysis."""
    urls = []
    if message.entities and message.text:
        for entity in message.entities:
            if isinstance(entity, MessageEntityTextUrl):
                urls.append(entity.url)
            elif isinstance(entity, MessageEntityUrl):
                # Extract the actual URL string using the entity's offset and length
                url_str = message.text[entity.offset:entity.offset + entity.length]
                urls.append(url_str)
    return urls

def extract_reactions(message):
    reactions = []
    if hasattr(message, 'reactions') and message.reactions and message.reactions.results:
        for r in message.reactions.results:
            try:
                reactions.append({"emoji": r.reaction.emoticon, "count": r.count})
            except AttributeError:
                reactions.append({"emoji": "custom_emoji", "count": r.count})
    return reactions

def format_message_data(message):
    # Handle standard text
    text_content = message.text or ""
    
    # Handle action messages (e.g., UserJoined, ChannelMessagePinned)
    action_type = type(message.action).__name__ if message.action else None
    
    # Handle anonymous senders/channels securely
    sender = message.sender_id
    if not sender and hasattr(message.peer_id, 'channel_id'):
        sender = f"channel_{message.peer_id.channel_id}"

    return {
        "message_id": message.id,
        "timestamp": message.date.isoformat() if message.date else None,
        "sender_id": sender,
        "reply_to_msg_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
        "action_event": action_type,
        "is_forward": bool(message.fwd_from),
        "text_content": text_content,
        "text_length": len(text_content),
        "word_count": len(text_content.split()),
        "extracted_urls": extract_urls(message),
        "media_type": get_media_type(message),
        "views": getattr(message, 'views', 0),
        "forwards": getattr(message, 'forwards', 0),
        "reactions": extract_reactions(message)
    }

# ==========================================
# 3. CORE EXTRACTION ENGINE
# ==========================================
async def extract_chat_data():
    global processed_count, skipped_count
    
    setup_directories()
    last_id = get_last_processed_id()

    if last_id > 0:
        print(f"Resuming data extraction from Message ID: {last_id}")
    else:
        print("Starting fresh extraction from the oldest message...")

    with open(EXPORT_FILE, "a", encoding="utf-8") as file_out:
        
        async for message in client.iter_messages(SOURCE_GROUP, reverse=True, min_id=last_id):
            attempts = 0
            
            while attempts < MAX_RETRIES:
                try:
                    msg_data = format_message_data(message)
                    
                    json_string = json.dumps(msg_data, ensure_ascii=False)
                    file_out.write(json_string + "\n")
                    
                    processed_count += 1
                    save_progress(message.id)
                    
                    if processed_count % 500 == 0:
                        print(f"[EXTRACTING] Processed {processed_count} messages... (Latest ID: {message.id})")
                    
                    # Protects against standard connection resets
                    await asyncio.sleep(0.01)
                    break
                    
                except errors.FloodWaitError as e:
                    print(f"\n[RATE LIMIT] Telegram paused extraction. Sleeping for {e.seconds} seconds...")
                    await asyncio.sleep(e.seconds + 5)
                    # Does not increment attempts, just waits and retries

                except Exception as e:
                    attempts += 1
                    print(f"[ERROR] Msg ID {message.id}: {e}. Attempt {attempts}/{MAX_RETRIES}")
                    await asyncio.sleep(1)
            
            if attempts >= MAX_RETRIES:
                log_error(message.id, "Failed to parse or write message data.")
                skipped_count += 1
                save_progress(message.id)

    print("\n✅ DATA EXTRACTION COMPLETE!")
    print(f"Data saved to: {EXPORT_FILE}")

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
async def main():
    await client.connect()

    if not await client.is_user_authorized():
        print("Client not authorized. Please run forwarder.py first to log in.")
        sys.exit()

    print("\n🚀 Starting Chat Analyzer...")
    await extract_chat_data()

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n" + "="*40)
        print("EXTRACTION PAUSED BY USER")
        print("="*40)
        print(f"Total messages extracted this session: {processed_count}")
        print("Progress saved. Run again to resume.")
        print("="*40)
        sys.exit()