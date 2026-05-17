import os
import re
import asyncio
import logging
import yt_dlp
import shutil
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import (
    BOT_TOKEN,
    REQUIRED_CHANNEL_ID,
    REQUIRED_CHANNEL_USERNAME,
    DOWNLOAD_DIR,
    ADMIN_IDS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("FFMPEG:", shutil.which("ffmpeg"))

# ───────── PLATFORM ─────────

PLATFORMS = {
    "tiktok": r"tiktok\.com|vm\.tiktok\.com",
    "instagram": r"instagram\.com",
    "youtube": r"youtube\.com|youtu\.be",
    "pinterest": r"pinterest\.com|pin\.it",
    "twitter": r"x\.com|twitter\.com"
}

def detect_platform(url):
    for k, v in PLATFORMS.items():
        if re.search(v, url):
            return k
    return None

def extract_url(text):
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None


# ───────── MEMBERSHIP ─────────

async def check_membership(user_id, context):
    try:
        member = await context.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL_ID,
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "📢 Kanala Katıl",
            url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"
        )],
        [InlineKeyboardButton("✅ Kontrol Et", callback_data="check")]
    ])


# ───────── YT-DLP CORE ─────────

def run_ydl(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info


def base_opts(output, audio=False):
    opts = {
        "outtmpl": output,
        "quiet": True,
        "no_warnings": True,
    }

    if audio:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["format"] = "bestvideo+bestaudio/best"

    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"

    return opts


async def download(url, platform, audio=False):
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
    output = f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"

    opts = base_opts(output, audio)

    try:
        filename, info = await asyncio.to_thread(run_ydl, url, opts)
        return filename, info.get("title", "video")
    except Exception as e:
        return None, str(e)


# ───────── BOT HANDLERS ─────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await check_membership(user.id, context):
        await update.message.reply_text(
            "🔒 Bu botu kullanmak için kanalımıza katılman gerekiyor!",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        f"""👋 Merhaba {user.first_name}!

🎬 Sosyal Medya İndirici Bot

📥 Kullanım:
Link gönder yeter.
MP3 için: mp3 https://...
"""
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if not await check_membership(user.id, context):
        await update.message.reply_text(
            "🔒 Kanal zorunlu",
            reply_markup=join_keyboard()
        )
        return

    audio = False
    if text.lower().startswith("mp3 "):
        audio = True
        text = text[4:].strip()

    url = extract_url(text)
    if not url:
        await update.message.reply_text("❌ Link yok")
        return

    platform = detect_platform(url)
    if not platform:
        await update.message.reply_text("❌ Desteklenmiyor")
        return

    msg = await update.message.reply_text("⏳ İndiriliyor...")

    filepath, title = await download(url, platform, audio)

    if not filepath or not os.path.exists(filepath):
        await msg.edit_text(f"❌ Hata: {title}")
        return

    await msg.edit_text("📤 Yükleniyor...")

    try:
        with open(filepath, "rb") as f:
            if audio:
                await update.message.reply_audio(audio=f, title=title[:64])
            else:
                await update.message.reply_video(video=f, caption=title[:100])

        await msg.delete()

    finally:
        try:
            os.remove(filepath)
        except:
            pass


async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if await check_membership(q.from_user.id, context):
        await q.edit_message_text("✅ Kullanabilirsin")
    else:
        await q.answer("🔒 Önce kanala katıl", show_alert=True)


# ───────── MAIN ─────────

def main():
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
