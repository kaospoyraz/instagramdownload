import os
import re
import asyncio
import logging
import yt_dlp
import requests
import instaloader
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from config import (
    BOT_TOKEN, REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_USERNAME,
    DOWNLOAD_DIR, ADMIN_IDS
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Platform Tespiti ───────────────────────────────────────────────────────

PLATFORM_PATTERNS = {
    "tiktok":    r"(tiktok\.com|vm\.tiktok\.com)",
    "instagram": r"(instagram\.com|instagr\.am)",
    "youtube":   r"(youtube\.com|youtu\.be)",
    "pinterest": r"(pinterest\.(com|ca|co\.uk|fr|de|es|it)|pin\.it)",
    "twitter":   r"(twitter\.com|x\.com|t\.co)",
}

def detect_platform(url: str) -> str | None:
    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return None

def extract_url(text: str) -> str | None:
    url_pattern = r"https?://[^\s]+"
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

# ─── Üyelik Kontrolü ────────────────────────────────────────────────────────

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member = await context.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL_ID,
            user_id=user_id
        )
        return member.status in [
            ChatMember.MEMBER,
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER
        ]
    except Exception as e:
        logger.error(f"Üyelik kontrolü hatası: {e}")
        return False

def membership_required_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"📢 Kanala Katıl → {REQUIRED_CHANNEL_USERNAME}",
            url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}"
        )],
        [InlineKeyboardButton("✅ Katıldım, Kontrol Et", callback_data="check_membership")]
    ])

# ─── İndirme Fonksiyonları ───────────────────────────────────────────────────

def get_ydl_opts(output_path: str, audio_only: bool = False) -> dict:
    """yt-dlp için ortak ayarlar"""
    if audio_only:
        return {
            "format": "bestaudio/best",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
        }
    return {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None,
    }

async def download_tiktok(url: str, audio_only: bool = False) -> tuple[str | None, str]:
    """TikTok - watermark'sız indir"""
    try:
        Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
        output = f"{DOWNLOAD_DIR}/tiktok_%(id)s.{'mp3' if audio_only else 'mp4'}"

        opts = get_ydl_opts(output, audio_only)
        # TikTok watermark kaldırma
        opts["format"] = "bestvideo[vcodec!=h265]+bestaudio/best" if not audio_only else opts["format"]
        opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
            "Referer": "https://www.tiktok.com/",
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "TikTok Video")
            filename = ydl.prepare_filename(info)
            if audio_only and not filename.endswith(".mp3"):
                filename = filename.rsplit(".", 1)[0] + ".mp3"
            return filename, title
    except Exception as e:
        logger.error(f"TikTok indirme hatası: {e}")
        return None, str(e)

async def download_instagram(url: str, audio_only: bool = False) -> tuple[str | None, str]:
    """Instagram - reels, post, hikaye"""
    try:
        Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
        output = f"{DOWNLOAD_DIR}/instagram_%(id)s.%(ext)s"
        opts = get_ydl_opts(output, audio_only)
        opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Instagram Post")
            filename = ydl.prepare_filename(info)
            if audio_only and not filename.endswith(".mp3"):
                filename = filename.rsplit(".", 1)[0] + ".mp3"
            return filename, title
    except Exception as e:
        logger.error(f"Instagram indirme hatası: {e}")
        return None, str(e)

async def download_youtube(url: str, audio_only: bool = False) -> tuple[str | None, str]:
    """YouTube video/ses"""
    try:
        Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
        output = f"{DOWNLOAD_DIR}/youtube_%(id)s.%(ext)s"
        opts = get_ydl_opts(output, audio_only)

        if not audio_only:
            opts["format"] = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "YouTube Video")
            filename = ydl.prepare_filename(info)
            if audio_only and not filename.endswith(".mp3"):
                filename = filename.rsplit(".", 1)[0] + ".mp3"
            return filename, title
    except Exception as e:
        logger.error(f"YouTube indirme hatası: {e}")
        return None, str(e)

async def download_pinterest(url: str) -> tuple[str | None, str]:
    """Pinterest - video ve resim"""
    try:
        Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
        output = f"{DOWNLOAD_DIR}/pinterest_%(id)s.%(ext)s"
        opts = {
            "format": "best",
            "outtmpl": output,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Pinterest")
            filename = ydl.prepare_filename(info)
            return filename, title
    except Exception as e:
        logger.error(f"Pinterest indirme hatası: {e}")
        return None, str(e)

async def download_twitter(url: str, audio_only: bool = False) -> tuple[str | None, str]:
    """X (Twitter) video"""
    try:
        Path(DOWNLOAD_DIR).mkdir(exist_ok=True)
        output = f"{DOWNLOAD_DIR}/twitter_%(id)s.%(ext)s"
        opts = get_ydl_opts(output, audio_only)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "X Post")
            filename = ydl.prepare_filename(info)
            if audio_only and not filename.endswith(".mp3"):
                filename = filename.rsplit(".", 1)[0] + ".mp3"
            return filename, title
    except Exception as e:
        logger.error(f"Twitter/X indirme hatası: {e}")
        return None, str(e)

# ─── Dispatcher ──────────────────────────────────────────────────────────────

async def process_download(url: str, platform: str, audio_only: bool) -> tuple[str | None, str]:
    handlers = {
        "tiktok":    lambda: download_tiktok(url, audio_only),
        "instagram": lambda: download_instagram(url, audio_only),
        "youtube":   lambda: download_youtube(url, audio_only),
        "pinterest": lambda: download_pinterest(url),
        "twitter":   lambda: download_twitter(url, audio_only),
    }
    handler = handlers.get(platform)
    if handler:
        return await handler()
    return None, "Desteklenmeyen platform"

# ─── Bot Komutları ────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Merhaba *{user.first_name}*!\n\n"
        "🎬 *Medya İndirici Bot*\n\n"
        "Desteklenen platformlar:\n"
        "• 🎵 TikTok (watermark'sız)\n"
        "• 📸 Instagram (Reels, Post)\n"
        "• ▶️ YouTube (Video & MP3)\n"
        "• 📌 Pinterest\n"
        "• 🐦 X / Twitter\n\n"
        "📥 *Kullanım:*\n"
        "Sadece link at, gerisini ben hallederim!\n\n"
        "🎵 MP3 için: Linkin başına `mp3 ` yaz\n"
        "Örnek: `mp3 https://youtube.com/...`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Yardım Menüsü*\n\n"
        "*Video/Resim İndirme:*\n"
        "Linki direkt gönder → otomatik indirir\n\n"
        "*MP3 Dönüştürme:*\n"
        "`mp3 <link>` formatında gönder\n\n"
        "*Komutlar:*\n"
        "/start — Botu başlat\n"
        "/help — Bu menü\n"
        "/stats — İstatistikler (Admin)\n\n"
        "*Desteklenen:* TikTok, Instagram, YouTube, Pinterest, X\n\n"
        "⚡ Watermark otomatik kaldırılır!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    # Üyelik kontrolü
    is_member = await check_membership(user.id, context)
    if not is_member:
        await update.message.reply_text(
            "🔒 *Bu botu kullanmak için kanalımıza katılman gerekiyor!*\n\n"
            "Katıldıktan sonra ✅ butonuna bas.",
            parse_mode="Markdown",
            reply_markup=membership_required_keyboard()
        )
        return

    # MP3 modu kontrolü
    audio_only = False
    if text.lower().startswith("mp3 "):
        audio_only = True
        text = text[4:].strip()

    url = extract_url(text)
    if not url:
        await update.message.reply_text(
            "❌ Geçerli bir link bulunamadı.\n"
            "Lütfen desteklenen bir platform linki gönder."
        )
        return

    platform = detect_platform(url)
    if not platform:
        await update.message.reply_text(
            "❌ Bu platform desteklenmiyor.\n\n"
            "✅ Desteklenenler: TikTok, Instagram, YouTube, Pinterest, X"
        )
        return

    platform_emojis = {
        "tiktok": "🎵", "instagram": "📸", "youtube": "▶️",
        "pinterest": "📌", "twitter": "🐦"
    }
    emoji = platform_emojis.get(platform, "🔗")
    mode_text = "🎵 MP3" if audio_only else "📥 Video"

    status_msg = await update.message.reply_text(
        f"{emoji} *{platform.capitalize()}* linki algılandı\n"
        f"{mode_text} indiriliyor... ⏳",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_chat_action(update.effective_chat.id, "upload_document")

        filepath, title = await process_download(url, platform, audio_only)

        if not filepath or not os.path.exists(filepath):
            await status_msg.edit_text(
                f"❌ İndirme başarısız!\n\n"
                f"Hata: {title}\n\n"
                "💡 Link geçerli mi? Özel hesap değil mi?"
            )
            return

        file_size = os.path.getsize(filepath)
        max_size = 50 * 1024 * 1024  # 50 MB Telegram limiti

        if file_size > max_size:
            os.remove(filepath)
            await status_msg.edit_text(
                "❌ Dosya çok büyük! (50 MB üzeri)\n"
                "YouTube için daha kısa bir video dene."
            )
            return

        await status_msg.edit_text(f"📤 Yükleniyor... `{title[:50]}`", parse_mode="Markdown")

        caption = (
            f"{'🎵' if audio_only else emoji} *{title[:100]}*\n\n"
            f"Platform: {platform.capitalize()}\n"
            f"{'MP3 dönüşümü' if audio_only else '📵 Watermark kaldırıldı' if platform == 'tiktok' else ''}\n\n"
            f"🤖 @{(await context.bot.get_me()).username}"
        )

        with open(filepath, "rb") as f:
            if audio_only or filepath.endswith(".mp3"):
                await update.message.reply_audio(
                    audio=f,
                    caption=caption,
                    parse_mode="Markdown",
                    title=title[:64],
                    performer="MediaBot"
                )
            elif filepath.endswith((".jpg", ".jpeg", ".png", ".webp")):
                await update.message.reply_photo(photo=f, caption=caption, parse_mode="Markdown")
            else:
                await update.message.reply_video(
                    video=f,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True
                )

        await status_msg.delete()
        os.remove(filepath)

    except Exception as e:
        logger.error(f"Mesaj işleme hatası: {e}")
        await status_msg.edit_text(
            "❌ Bir hata oluştu. Lütfen tekrar dene.\n"
            f"`{str(e)[:100]}`",
            parse_mode="Markdown"
        )

async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    is_member = await check_membership(query.from_user.id, context)
    if is_member:
        await query.edit_message_text(
            "✅ *Harika! Artık botu kullanabilirsin!*\n\n"
            "Bir link gönder, indireyim 🚀",
            parse_mode="Markdown"
        )
    else:
        await query.answer("❌ Hâlâ kanala katılmadın!", show_alert=True)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    # İleride veritabanı ile genişletilebilir
    await update.message.reply_text("📊 *İstatistikler*\n\nYakında eklenecek!", parse_mode="Markdown")

# ─── Ana Fonksiyon ───────────────────────────────────────────────────────────

def main():
    Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="check_membership"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot başlatıldı!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
