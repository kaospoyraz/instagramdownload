import os
import re
import asyncio
import logging
import yt_dlp
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
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────── DEBUG ─────────
import shutil
print("FFMPEG:", shutil.which("ffmpeg"))

# ───────── URL ─────────

def extract_url(text):
    match = re.search(r"https?://\S+", text)
    return match.group(0) if match else None


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


# ───────── YT-DLP ─────────

def run_ydl(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        print("🔥 DOWNLOAD START:", url)
        info = ydl.extract_info(url, download=True)
        print("✅ DOWNLOAD DONE")
        return ydl.prepare_filename(info), info


def base_opts(output, audio=False):
    opts = {
        "outtmpl": output,
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
    }

    if audio:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        opts["format"] = "bv*+ba/b"

    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"

    return opts


async def download(url, audio=False):
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

    output = str(Path(DOWNLOAD_DIR) / "%(id)s.%(ext)s")
    opts = base_opts(output, audio)

    try:
        filename, info = await asyncio.to_thread(run_ydl, url, opts)
        return filename, info.get("title", "video")

    except Exception as e:
        print("❌ DOWNLOAD ERROR:", repr(e))
        return None, str(e)


# ───────── HANDLERS ─────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.message.reply_text(
        f"""👋 Merhaba {user.first_name}

📥 Link gönder indiririm
🎵 mp3 link = ses indir

Destek: YouTube / TikTok / Instagram / Twitter"""
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    audio = False
    if text.lower().startswith("mp3 "):
        audio = True
        text = text[4:].strip()

    url = extract_url(text)

    if not url:
        await update.message.reply_text("❌ Link yok")
        return

    msg = await update.message.reply_text("⏳ İndiriliyor...")

    filepath, title = await download(url, audio)

    if not filepath or not os.path.exists(filepath):
        await msg.edit_text(f"❌ Hata: {title}")
        return

    await msg.edit_text("📤 Gönderiliyor...")

    try:
        with open(filepath, "rb") as f:
            if audio:
                await update.message.reply_audio(audio=f, title=title[:64])
            else:
                await update.message.reply_video(video=f, caption=title[:100])

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Upload hata: {e}")

    finally:
        try:
            os.remove(filepath)
        except:
            pass


async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    await q.edit_message_text("✅ Sistem aktif")


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
