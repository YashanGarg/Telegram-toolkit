import os
import sys
import asyncio
from telethon import TelegramClient, events, errors

# Import credentials from config.py
from config import API_ID, API_HASH, PHONE_NUMBER, SOURCE_GROUP, DESTINATION_GROUP

# ==========================================
# SCRIPT CONFIGURATION
# ==========================================
MAX_FILE_SIZE_GB = 1.95

# Directory for forwarder tracking files
TRACKING_DIR = os.path.join("tracking", "forwarder")
os.makedirs(TRACKING_DIR, exist_ok=True)

PROGRESS_FILE = os.path.join(TRACKING_DIR, "bookmark.txt")
LOG_FILE = os.path.join(TRACKING_DIR, "skipped_files.log")

# Counters
forwarded_count = 0
skipped_count = 0

# Initialize Client
client = TelegramClient(
    'forwarder_session', 
    API_ID, 
    API_HASH,
    connection_retries=10,
    retry_delay=3,
    timeout=20
)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def get_last_processed_id():
    """Reads bookmark.txt to resume from the last forwarded message."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            content = f.read().strip()
            if content.isdigit():
                return int(content)
    return 0

def save_progress(message_id):
    """Saves the current message ID so we can resume if interrupted."""
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(message_id))

def is_file_oversized(message):
    """Checks if a file strictly exceeds the 1.95 GB safe limit."""
    if message.media and hasattr(message.media, 'document'):
        file_size_gb = message.media.document.size / (1024 * 1024 * 1024)
        if file_size_gb > MAX_FILE_SIZE_GB:
            return True, file_size_gb
    return False, 0

def log_skipped(message_id, file_size_gb):
    """Logs oversized files to a text file for your records."""
    global skipped_count
    skipped_count += 1
    print(f"[SKIPPED] Msg ID {message_id} ({file_size_gb:.2f} GB). Too large.")
    with open(LOG_FILE, "a") as f:
        f.write(f"Message ID: {message_id} | Size: {file_size_gb:.2f} GB\n")

# ==========================================
# CORE FORWARDING LOGIC
# ==========================================
async def forward_album(album_messages):
    """Processes a grouped album/collage as a single entity."""
    global forwarded_count
    valid_messages = []
    
    # Filter out oversized items from the album
    for msg in album_messages:
        oversized, size = is_file_oversized(msg)
        if oversized:
            log_skipped(msg.id, size)
        else:
            valid_messages.append(msg)
            
    if valid_messages:
        while True:
            try:
                # Forward all valid album items together
                await client.forward_messages(DESTINATION_GROUP, valid_messages)
                forwarded_count += len(valid_messages)
                highest_id = max(msg.id for msg in album_messages)
                
                print(f"[ALBUM] Forwarded {len(valid_messages)} items. Up to ID: {highest_id}")
                save_progress(highest_id)
                
                await asyncio.sleep(4) # Safe delay for albums
                break # Break retry loop on success
                
            except errors.FloodWaitError as e:
                print(f"\n[RATE LIMIT] Telegram paused us. Sleeping for {e.seconds} seconds...")
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                print(f"[ERROR] Failed to forward album: {e}")
                break

async def forward_single_message(message):
    """Processes a standard individual message or file."""
    global forwarded_count
    
    oversized, size = is_file_oversized(message)
    if oversized:
        log_skipped(message.id, size)
        save_progress(message.id)
        return

    while True:
        try:
            await client.forward_messages(DESTINATION_GROUP, message)
            forwarded_count += 1
            print(f"[FORWARDED] Msg ID {message.id} | Total Processed: {forwarded_count}")
            save_progress(message.id)
            
            await asyncio.sleep(2.5) # Safe delay for single messages
            break # Break retry loop on success
            
        except errors.FloodWaitError as e:
            print(f"\n[RATE LIMIT] Telegram paused us. Sleeping for {e.seconds} seconds...")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"[ERROR] Failed Msg ID {message.id}: {e}")
            break

# ==========================================
# BULK MIGRATION ENGINE
# ==========================================
async def run_bulk_migration():
    """Iterates through the source group history to migrate 20k+ files safely."""
    last_id = get_last_processed_id()
    if last_id > 0:
        print(f"Resuming migration from Message ID: {last_id}")
    else:
        print("Starting new bulk migration from the oldest message...")

    current_album = []
    current_grouped_id = None

    # reverse=True starts from the oldest message and moves to the newest
    async for message in client.iter_messages(SOURCE_GROUP, reverse=True, min_id=last_id):
        
        # 1. Handle Grouped Albums (Collages)
        if message.grouped_id:
            if current_grouped_id == message.grouped_id:
                current_album.append(message)
            else:
                # A new album started. Process the previous one first.
                if current_album:
                    await forward_album(current_album)
                
                # Start collecting the new album
                current_album = [message]
                current_grouped_id = message.grouped_id
                
        # 2. Handle Single Messages
        else:
            # If we had an album pending, send it before this single message
            if current_album:
                await forward_album(current_album)
                current_album = []
                current_grouped_id = None
                
            await forward_single_message(message)

    # 3. Clean up: send the final album if the loop ends while holding one
    if current_album:
        await forward_album(current_album)
        
    print("\n✅ BULK MIGRATION COMPLETE! All historical messages have been processed.")

# ==========================================
# MAIN EXECUTION
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
        
    print("\n🚀 Starting Continuous Sync Mode...")
    print("Press Ctrl+C at any time to safely pause and save progress.")
    
    while True:
        print("\n--- Scanning for new messages ---")
        await run_bulk_migration()
        
        print("\n💤 Sync complete. Going into deep sleep for 60 minutes...")
        await asyncio.sleep(3600) 

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n" + "="*40)
        print("MIGRATION PAUSED BY USER")
        print("="*40)
        print(f"Total items forwarded this session: {forwarded_count}")
        print(f"Total large files skipped this session: {skipped_count}")
        print("Progress is saved. Run the script again to resume.")
        print("="*40)
        sys.exit()