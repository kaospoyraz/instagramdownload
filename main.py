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
    ADMIN_IDS
)

# ───────────────── LOG ─────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ───────────────── PLATFORM DETECT ─────────────────

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

# ───────────────── MEMBERSHIP SYSTEM ─────────────────

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
        [
            InlineKeyboardButton(
                "📢 Kanala Katıl",
                url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"
            )
        ],
        [
            InlineKeyboardButton("✅ Kontrol Et", callback_data="check")
        ]
    ])

# ───────────────── YT-DLP CORE ─────────────────

def run_ydl(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info), info


def base_opts(output):
    opts = {
        "outtmpl": output,
        "quiet": True,
        "no_warnings": True,
        "format": "best"
    }

    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"

    return opts


def ig_opts(output):
    opts = base_opts(output)
    opts["http_headers"] = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.instagram.com/"
    }
    return opts


def pin_opts(output):
    opts = base_opts(output)
    opts["http_headers"] = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.pinterest.com/"
    }
    return opts


async def download(url, platform):
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
    output = f"{DOWNLOAD_DIR}/%(id)s.%(ext)s"

    if platform == "instagram":
        opts = ig_opts(output)
    elif platform == "pinterest":
        opts = pin_opts(output)
    else:
        opts = base_opts(output)

    try:
        filename, info = await asyncio.to_thread(run_ydl, url, opts)
        return filename, info.get("title", "video")
    except Exception as e:
        return None, str(e)
        # ───────────────── HANDLERS ─────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_membership(user_id, context):
        await update.message.reply_text(
            "🔒 Botu kullanmak için kanala katılmalısın!",
            reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        "🎬 Media Bot\nLink gönder indiriyim"
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    # 🔒 ZORUNLU KANAL KONTROL
    if not await check_membership(user_id, context):
        await update.message.reply_text(
            "🔒 Kanala katılmadan kullanamazsın",
            reply_markup=join_keyboard()
        )
        return

    url = extract_url(text)
    if not url:
        await update.message.reply_text("❌ Link yok")
        return

    platform = detect_platform(url)
    if not platform:
        await update.message.reply_text("❌ Desteklenmiyor")
        return

    msg = await update.message.reply_text("⏳ İndiriliyor...")

    filepath, title = await download(url, platform)

    if not filepath or not os.path.exists(filepath):
        await msg.edit_text(f"❌ Hata: {title}")
        return

    await msg.edit_text("📤 Yükleniyor...")

    try:
        with open(filepath, "rb") as f:
            if filepath.endswith((".jpg", ".png", ".webp")):
                await update.message.reply_photo(photo=f, caption=title[:100])
            else:
                await update.message.reply_video(video=f, caption=title[:100])

        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ Upload error: {e}")

    finally:
        try:
            os.remove(filepath)
        except:
            pass


async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if await check_membership(q.from_user.id, context):
        await q.edit_message_text("✅ Artık kullanabilirsin")
    else:
        await q.answer("❌ Önce kanala katıl", show_alert=True)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    await update.message.reply_text("📊 Stats yakında")


# ───────────────── MAIN ─────────────────

def main():
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))

    logger.info("Bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
