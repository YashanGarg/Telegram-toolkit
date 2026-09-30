import os
import sys
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.tl.types import (
    ChannelParticipantAdmin,
    ChannelParticipantCreator,
    ChannelParticipantBanned,
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth
)

# Import shared credentials from config.py
from config import API_ID, API_HASH, SOURCE_GROUP

# ==========================================
# 1. DIRECTORY & SCRIPT CONFIGURATION
# ==========================================
DATA_EXPORT_DIR = "data_exports"
TRACKING_DIR = os.path.join("tracking", "scraper")

EXPORT_FILE = os.path.join(DATA_EXPORT_DIR, "users_info.jsonl")
LOG_FILE = os.path.join(TRACKING_DIR, "scraper_errors.log")

MAX_RETRIES = 3

scraped_count = 0
skipped_count = 0

client = TelegramClient('forwarder_session', API_ID, API_HASH)

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def setup_directories():
    """Ensures necessary export and tracking folders exist."""
    os.makedirs(DATA_EXPORT_DIR, exist_ok=True)
    os.makedirs(TRACKING_DIR, exist_ok=True)

def log_error(user_identifier, error_msg):
    """Logs scraping errors to a text log file."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"User/Target: {user_identifier} | Error: {error_msg}\n")

def parse_user_status(status):
    """Converts Telethon status objects into clean, readable JSON attributes."""
    if not status:
        return {"type": "hidden_or_unknown"}
    if isinstance(status, UserStatusOnline):
        return {
            "type": "online",
            "expires": status.expires.isoformat() if status.expires else None
        }
    if isinstance(status, UserStatusOffline):
        return {
            "type": "offline",
            "last_seen": status.was_online.isoformat() if status.was_online else None
        }
    if isinstance(status, UserStatusRecently):
        return {"type": "recently"}
    if isinstance(status, UserStatusLastWeek):
        return {"type": "last_week"}
    if isinstance(status, UserStatusLastMonth):
        return {"type": "last_month"}
    return {"type": "unknown"}

def parse_participant_info(participant):
    """Extracts role, permissions, custom titles, and admin history."""
    if not participant:
        return {"role": "member", "joined_date": None, "custom_title": None, "promoted_by": None}

    info = {
        "role": "member",
        "joined_date": None,
        "custom_title": None,
        "promoted_by": None
    }

    if isinstance(participant, ChannelParticipantCreator):
        info["role"] = "creator"
        info["custom_title"] = getattr(participant, 'rank', None)
    elif isinstance(participant, ChannelParticipantAdmin):
        info["role"] = "admin"
        info["custom_title"] = getattr(participant, 'rank', None)
        info["promoted_by"] = getattr(participant, 'promoted_by', None)
    elif isinstance(participant, ChannelParticipantBanned):
        info["role"] = "banned_or_restricted"

    # Extract member join date if available
    if hasattr(participant, 'date') and participant.date:
        info["joined_date"] = participant.date.isoformat()

    return info

def format_user_data(user):
    """Extracts all user attributes into a single dictionary."""
    participant = getattr(user, 'participant', None)
    part_data = parse_participant_info(participant)
    status_data = parse_user_status(getattr(user, 'status', None))

    return {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "phone_number": getattr(user, 'phone', None),  # Visible if contact or allowed by privacy settings
        "is_bot": bool(user.bot),
        "is_verified": getattr(user, 'verified', False),
        "is_restricted": getattr(user, 'restricted', False),
        "is_scam": getattr(user, 'scam', False),
        "is_fake": getattr(user, 'fake', False),
        "is_premium": getattr(user, 'premium', False),
        "online_status": status_data,
        "role": part_data["role"],
        "custom_title": part_data["custom_title"],
        "joined_date": part_data["joined_date"],
        "promoted_by_user_id": part_data["promoted_by"],
        "has_profile_photo": bool(user.photo),
        "language_code": getattr(user, 'lang_code', None),
        "scraped_at": datetime.utcnow().isoformat() + "Z"
    }

# ==========================================
# 3. CORE SCRAPING ENGINE
# ==========================================
async def scrape_users():
    """Fetches user list and writes detailed records to JSONL."""
    global scraped_count, skipped_count
    
    setup_directories()
    
    try:
        entity = await client.get_entity(SOURCE_GROUP)
    except Exception as e:
        print(f"❌ Failed to resolve chat target '{SOURCE_GROUP}': {e}")
        return

    # Check caller privileges
    try:
        me = await client.get_me()
        permissions = await client.get_permissions(entity, me)
        is_admin = permissions.is_admin or permissions.is_creator
        print(f"📌 Target Chat: {getattr(entity, 'title', SOURCE_GROUP)}")
        print(f"🔑 Account Status: {'ADMIN (Full Access)' if is_admin else 'REGULAR MEMBER (Restricted Access)'}")
    except Exception:
        is_admin = False
        print("📌 Target Chat resolved. Proceeding with standard member permissions...")

    print("\n🚀 Fetching member details...")

    # Overwrite/Create export file
    with open(EXPORT_FILE, "w", encoding="utf-8") as file_out:
        try:
            # iter_participants fetches full user + participant objects
            async for user in client.iter_participants(entity):
                attempts = 0
                while attempts < MAX_RETRIES:
                    try:
                        user_data = format_user_data(user)
                        
                        json_string = json.dumps(user_data, ensure_ascii=False)
                        file_out.write(json_string + "\n")
                        
                        scraped_count += 1
                        
                        if scraped_count % 100 == 0:
                            print(f"[SCRAPING] Processed {scraped_count} users...")

                        await asyncio.sleep(0.01)  # API safety pause
                        break

                    except errors.FloodWaitError as e:
                        print(f"\n[RATE LIMIT] Telegram paused scraping. Sleeping for {e.seconds} seconds...")
                        await asyncio.sleep(e.seconds + 5)

                    except Exception as e:
                        attempts += 1
                        print(f"[ERROR] User ID {user.id}: {e}. Attempt {attempts}/{MAX_RETRIES}")
                        await asyncio.sleep(1)

                if attempts >= MAX_RETRIES:
                    log_error(user.id, "Failed to parse or write user data.")
                    skipped_count += 1

        except errors.ChatAdminRequiredError:
            print("\n❌ ACCESS DENIED BY TELEGRAM:")
            print("Telegram strictly forbids non-admins from scraping subscriber lists in Channels or Groups with hidden member lists.")
            print("To scrape users from this target, your logged-in account must be granted Admin privileges.")
            log_error(str(SOURCE_GROUP), "ChatAdminRequiredError: Non-admin account attempted channel/hidden group scraping.")
            return

        except Exception as e:
            print(f"\n❌ Unexpected error during user iteration: {e}")
            log_error(str(SOURCE_GROUP), f"Fatal Iteration Error: {e}")
            return

    print("\n✅ USER SCRAPING COMPLETE!")
    print(f"Total Users Exported: {scraped_count}")
    print(f"Skipped/Failed Records: {skipped_count}")
    print(f"Data saved to: {EXPORT_FILE}")

# ==========================================
# 4. MAIN EXECUTION
# ==========================================
async def main():
    await client.connect()

    if not await client.is_user_authorized():
        print("Client not authorized. Please run forwarder.py first to log in.")
        sys.exit()

    print("\n🚀 Starting User Scraper...")
    await scrape_users()

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n" + "="*40)
        print("SCRAPER PAUSED BY USER")
        print("="*40)
        print(f"Total users extracted this session: {scraped_count}")
        print("="*40)
        sys.exit()