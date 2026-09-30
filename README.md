# Telegram Toolkit: Migration, Download & Data Intelligence Suite

A modular, asynchronous Python suite built on the Telethon framework for migrating, archiving, downloading, and analyzing Telegram chat data. Designed to handle massive groups, channels, personal chats, and Saved Messages, this toolkit provides resilient data pipelines with built-in rate-limit protection, stateful auto-resuming, and structured machine-learning-ready exports.

---

## 🌟 Suite Overview

This repository contains **four standalone modules**, each optimized for a specific stage of chat processing:

1. **`forwarder.py` (Live & Bulk Migrator):** Forwards messages, media, and grouped albums from a source chat/channel to a target destination while preserving message sequence and album layouts.
2. **`media_downloader.py` (Categorized Downloader):** Downloads all attachments into organized subdirectories with custom, collision-free naming (`{type}_{message_id}_{timestamp}.ext`) and size-based dynamic pacing to prevent API bans.
3. **`chat_analyzer.py` (Dataset Generator & Large Chat Analyzer):** Ingests and extracts detailed metadata from chat histories. Generates structured datasets (`.jsonl`) for training machine learning models/chatbots, and analyzing massive group chats for key insights.
4. **`user_scraper.py` (Member & Privilege Profiler):** Scrapes user profiles, roles, permissions, badges, custom admin titles, and activity statuses across public and private groups/channels.

---

## 🚀 Key Features

* **Massive Scale Support:** Tested with 20,000+ files. Regulates its own speed to prevent account bans and handles Telegram `FloodWaitError` exceptions automatically by pausing and safely resuming execution.
* **Stateful Execution (Auto-Resume):** Uses localized bookmarking to track progress in dedicated tracking folders (`tracking/`). If execution is interrupted or your internet drops, scripts pick up exactly where they left off.
* **Smart Album & Media Preservation:** Forwards grouped media together in their original order. For downloads, assigns unique, deterministic filenames to prevent file collision or duplicate naming (e.g., `(1).jpg`).
* **Oversized File Filtering:** Automatically skips files strictly larger than 1.95 GB during processing and logs them to ensure uninterrupted execution.
* **ML-Ready JSON Lines (`.jsonl`) Outputs:** Memory-efficient stream exports allow training data loaders to read records line-by-line without loading entire datasets into RAM.
* **Privilege Awareness:** Automatically detects caller status (Admin vs. Regular Member) and adjusts data extraction parameters to maximize information retrieval within Telegram's permission boundaries.
* **Terminal QR Authentication:** No need to type passwords or SMS codes. Authenticate securely by scanning a QR code drawn directly in your terminal.

---

## 📋 Prerequisites

* **Python:** Version 3.10 or higher. *(Note: Python 3.14+ users may see a harmless `DeprecationWarning` regarding Windows event loops).*
* **Telegram API Credentials:** You must obtain your own `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).

---

## 🛠️ Installation & Setup

1. **Clone or Download the Repository:**
   Clone this repository or download the project files into a dedicated local directory.

```bash
   git clone https://github.com/YashanGarg/Telegram-toolkit.git
   cd Telegram-toolkit
```

2. **Create and Activate a Virtual Environment (Recommended):**

```bash
   python -m venv venv

   # On Windows:
   venv\Scripts\activate

   # On macOS/Linux:
   source venv/bin/activate
```

3. **Install Dependencies:**

```bash
   pip install -r requirements.txt
```

---

## ⚙️ Configure Credentials

1. Create your `config.py` file by copying the provided template `config.example.py` (or open `config.py` if it already exists) in your root directory:

```bash
   # On Windows:
   copy config.example.py config.py

   # On macOS/Linux:
   cp config.example.py config.py
```

2. Insert your Telegram API credentials and target chat identifiers in `config.py`:

```python
   API_ID = 12345678  # Your API ID integer
   API_HASH = "your_api_hash_here"
   PHONE_NUMBER = '+919876543210'  # Replace with your phone number with country code
   SOURCE_GROUP = "source_chat_username_or_id"
   DESTINATION_GROUP = "destination_chat_username_or_id"  # Required for forwarder.py
```

---

## 💻 Usage

Run each script independently based on your current objective. On the very first run of any script, you will be prompted to log in securely by scanning a terminal QR code. This generates a `forwarder_session.session` file that acts as your authentication token across the entire suite.

```bash
# Relocate messages to a new chat
python forwarder.py

# Download and categorize media files locally
python media_downloader.py

# Extract deep metadata for ML or chat analysis
python chat_analyzer.py

# Scrape user attributes, roles, and online statuses
python user_scraper.py
```

---

## 📁 Repository Structure

```text
Telegram-toolkit/
├── .gitignore
├── README.md
├── requirements.txt
├── config.py                     # API credentials and target configs
├── forwarder_session.session     # Shared Telethon authentication state
│
├── forwarder.py                  # Script 1: Message & Album Relocation Engine
├── media_downloader.py           # Script 2: Categorized Media Downloader
├── chat_analyzer.py              # Script 3: Chat Metadata & Text Dataset Generator
├── user_scraper.py               # Script 4: Member Metadata & Profile Scraper
│
├── downloads/                    # Media downloaded by media_downloader.py
│   ├── photos/
│   ├── videos/
│   ├── audio/
│   ├── voice_notes/
│   ├── documents/
│   └── stickers/
│
├── data_exports/                 # Datasets generated by analyzer & scraper
│   ├── chat_history.jsonl
│   └── users_info.jsonl
│
└── tracking/                     # Isolated state bookmarks and runtime logs
    ├── forwarder/
    │   ├── bookmark.txt
    │   └── skipped_files.log
    ├── downloader/
    │   ├── downloader_bookmark.txt
    │   └── download_errors.log
    ├── analyzer/
    │   ├── analyzer_bookmark.txt
    │   └── analyzer_errors.log
    └── scraper/
        └── scraper_errors.log
```

---

## 🛡️ Error Handling

* **Rate Limits (FloodWaitError):** Automatically pauses execution for the exact duration requested by Telegram's servers plus a safety buffer, then seamlessly resumes.
* **Network Faults & Timeouts:** Implements retry loops (`MAX_RETRIES = 3`) with exponential-like backoff delays before permanently logging unresolvable errors to prevent script termination.
* **Permission Errors (ChatAdminRequiredError):** Gracefully catches restricted access exceptions when attempting to scrape channels or hidden member lists without admin privileges, logging the event safely.

---

## 🔒 Security & Privacy

* **Local Storage:** All session files, logs, bookmarks, and downloads remain 100% local to your machine.
* **Phone Number Masking:** User phone numbers are subject to individual privacy rules set on Telegram. The scraper will extract them only if the user permits visibility or if they are stored in your contacts.
* **Ignored Secrets:** Sensitive files like `config.py`, tracking logs, and session files are excluded via `.gitignore` to prevent accidental public uploads.

---

## ⚠️ Important Notes / Limitations

* **Admin Rights Required:** Scraping user lists from large channels or supergroups with hidden member lists requires your authorized user account to hold administrator permissions in that chat.
* **File Size Caps:** Telegram client limits file downloads natively; files exceeding platform or local constraints are filtered or logged to prevent crashes.

---

## 📊 Module Summary

* **Migration:** Bulk forwarder with sequence integrity.
* **Media Management:** Categorized downloader with collision prevention.
* **Data Intelligence:** Streaming JSONL analyzer for NLP and machine learning.
* **User Profiling:** Deep permission and status extractor.

---

## 📄 License

Distributed under the MIT License. See the [LICENSE](LICENSE) file for more information.

Copyright (c) 2026 Yashan Garg

---

## 📌 Disclaimer

This tool is intended for personal archiving, data migration, and analytical research. Use responsibly and in accordance with Telegram's Terms of Service and local data privacy regulations.
