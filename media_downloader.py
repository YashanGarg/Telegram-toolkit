import os
import sys
import asyncio
from telethon import TelegramClient, errors
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeVideo
)

# Import shared credentials from config.py
from config import API_ID, API_HASH, SOURCE_GROUP

# ==========================================
# 1. DIRECTORY & SCRIPT CONFIGURATION
# ==========================================
BASE_DOWNLOAD_DIR = "downloads"

# Directory for downloader tracking files
TRACKING_DIR = os.path.join("tracking", "downloader")
os.makedirs(TRACKING_DIR, exist_ok=True)

PROGRESS_FILE = os.path.join(TRACKING_DIR, "downloader_bookmark.txt")
LOG_FILE = os.path.join(TRACKING_DIR, "download_errors.log")

MAX_RETRIES = 3  # Maximum attempts per file before skipping

# Define media subdirectories
FOLDERS = {
    "photos": os.path.join(BASE_DOWNLOAD_DIR, "photos"),
    "videos": os.path.join(BASE_DOWNLOAD_DIR, "videos"),
    "audio": os.path.join(BASE_DOWNLOAD_DIR, "audio"),
    "voice": os.path.join(BASE_DOWNLOAD_DIR, "voice_notes"),
    "documents": os.path.join(BASE_DOWNLOAD_DIR, "documents"),
    "stickers": os.path.join(BASE_DOWNLOAD_DIR, "stickers"),
}

# Statistics Counters
downloaded_count = 0
skipped_count = 0

# Initialize Client
client = TelegramClient('forwarder_session', API_ID, API_HASH)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def setup_directories():
    """Ensures all download folders exist on the file system."""
    for folder_path in FOLDERS.values():
        os.makedirs(folder_path, exist_ok=True)

def get_last_processed_id():
    """Reads downloader_bookmark.txt to resume progress."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    return 0

def save_progress(message_id):
    """Saves the current message ID to resume if interrupted."""
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(message_id))

def log_error(message_id, error_msg):
    """Logs download errors to a text file."""
    with open(LOG_FILE, "a") as f:
        f.write(f"Message ID: {message_id} | Error: {error_msg}\n")

def categorize_media(message):
    """Determines the appropriate target folder for a message's media type."""
    if message.photo:
        return FOLDERS["photos"], "Photo"
    if message.voice:
        return FOLDERS["voice"], "Voice Note"
    if message.sticker:
        return FOLDERS["stickers"], "Sticker"
    if message.video or message.gif:
        return FOLDERS["videos"], "Video"
    if message.audio:
        return FOLDERS["audio"], "Audio"
    if message.document:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeAudio):
                return FOLDERS["audio"], "Audio Document"
            if isinstance(attr, DocumentAttributeVideo):
                return FOLDERS["videos"], "Video Document"
        return FOLDERS["documents"], "Document"
    return None, None

# ==========================================
# 3. CORE DOWNLOAD ENGINE
# ==========================================
async def download_message_media(message):
    """Downloads media with custom, collision-free file naming."""
    global downloaded_count, skipped_count

    if not message.media:
        save_progress(message.id)
        return

    target_folder, media_type = categorize_media(message)
    if not target_folder:
        save_progress(message.id)
        return

    attempts = 0
    while attempts < MAX_RETRIES:
        try:
            # 1. Determine if media has an original filename (like MOV or MP4 files)
            custom_filename = None
            if hasattr(message.media, 'document') and message.media.document:
                for attr in message.media.document.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        custom_filename = attr.file_name
                        break

            # 2. If no original filename exists (e.g. photos), build a unique clean name using Message ID
            if not custom_filename:
                date_str = message.date.strftime("%Y-%m-%d_%H-%M-%S")
                # Determine file extension (.jpg, .ogg, .webp, etc.)
                ext = ".jpg"
                if message.voice:
                    ext = ".ogg"
                elif message.sticker:
                    ext = ".webp"
                elif message.video:
                    ext = ".mp4"
                
                custom_filename = f"{media_type.lower()}_{message.id}_{date_str}{ext}"

            # Combine folder path and custom filename
            full_save_path = os.path.join(target_folder, custom_filename)

            # 3. Download the file
            filename = await client.download_media(message, file=full_save_path)
            
            if filename:
                downloaded_count += 1
                clean_name = os.path.basename(filename)
                
                # Check file size in MB
                file_size_mb = os.path.getsize(filename) / (1024 * 1024)
                print(f"[DOWNLOADED] Msg ID {message.id} | Type: {media_type} | File: {clean_name} ({file_size_mb:.2f} MB)")
                
                save_progress(message.id)

                # Dynamic Pacing based on file size
                if file_size_mb < 5:
                    await asyncio.sleep(0.1)
                elif file_size_mb < 50:
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(2.5)
            else:
                skipped_count += 1
                print(f"[SKIPPED] Msg ID {message.id} | Telegram returned no file data.")
                save_progress(message.id)

            break  # Success, exit retry loop

        except errors.FloodWaitError as e:
            print(f"\n[RATE LIMIT] Telegram paused downloads. Sleeping for {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 5)

        except (ConnectionError, TimeoutError) as e:
            attempts += 1
            print(f"[NETWORK ERROR] Msg ID {message.id}. Attempt {attempts}/{MAX_RETRIES}. Retrying in 5s...")
            await asyncio.sleep(5)

        except Exception as e:
            attempts += 1
            print(f"[ERROR] Msg ID {message.id}: {e}. Attempt {attempts}/{MAX_RETRIES}.")
            await asyncio.sleep(2)

    if attempts >= MAX_RETRIES:
        print(f"[FAILED] Msg ID {message.id} permanently skipped after {MAX_RETRIES} failed attempts.")
        log_error(message.id, "Max retries exceeded due to persistent network or file errors.")
        skipped_count += 1
        save_progress(message.id)

async def run_downloader():
    """Iterates through group history and downloads all media."""
    setup_directories()
    last_id = get_last_processed_id()

    if last_id > 0:
        print(f"Resuming downloads from Message ID: {last_id}")
    else:
        print("Starting fresh media download from the oldest message...")

    async for message in client.iter_messages(SOURCE_GROUP, reverse=True, min_id=last_id):
        if message.media:
            await download_message_media(message)
        else:
            save_progress(message.id)

    print("\n✅ MEDIA DOWNLOAD COMPLETE! All media files have been organized.")

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
async def main():
    await client.connect()

    if not await client.is_user_authorized():
        import qrcode
        print("Generating QR Code...")
        qr_login = await client.qr_login()

        qr = qrcode.QRCode()
        qr.add_data(qr_login.url)
        qr.print_ascii(invert=True)

        print("\nOpen Telegram on your phone > Settings > Devices > Link Desktop Device")
        print("Scan the QR code above to log in.")

        await qr_login.wait(timeout=120)
        print("\n✅ QR Login Successful!")
    else:
        print("Telegram client logged in successfully.")

    print("\n🚀 Starting Media Downloader...")
    await run_downloader()

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n" + "="*40)
        print("DOWNLOADER PAUSED BY USER")
        print("="*40)
        print(f"Total files downloaded this session: {downloaded_count}")
        print(f"Total skipped/failed items: {skipped_count}")
        print("Progress is saved in downloader_bookmark.txt. Run again to resume.")
        print("="*40)
        sys.exit()