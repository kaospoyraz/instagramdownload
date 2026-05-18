import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

REQUIRED_CHANNEL_ID = int(os.getenv("REQUIRED_CHANNEL_ID"))
REQUIRED_CHANNEL_USERNAME = os.getenv("REQUIRED_CHANNEL_USERNAME")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")


admins = os.getenv("ADMIN_IDS", "")

ADMIN_IDS = [
    int(x) for x in admins.split(",") if x.strip()
]
