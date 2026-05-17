import os import re import asyncio import logging import yt_dlp from pathlib import Path from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember from telegram.ext import ( Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler ) from config import ( BOT_TOKEN, REQUIRED_CHANNEL_ID, REQUIRED_CHANNEL_USERNAME, DOWNLOAD_DIR, ADMIN_IDS )

logging.basicConfig( format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO, handlers=[ logging.FileHandler("bot.log"), logging.StreamHandler() ] ) logger = logging.getLogger(name)

─── Platform Detection ────────────────────────────────────────────────

PLATFORM_PATTERNS = { "tiktok": r"(tiktok.com|vm.tiktok.com)", "instagram": r"(instagram.com|instagr.am)", "youtube": r"(youtube.com|youtu.be)", "pinterest": r"(pinterest.(com|ca|co.uk|fr|de|es|it)|pin.it)", "twitter": r"(twitter.com|x.com|t.co)", }

def detect_platform(url: str): for k, v in PLATFORM_PATTERNS.items(): if re.search(v, url, re.IGNORECASE): return k return None

def extract_url(text: str): match = re.search(r"https?://[^\s]+", text) return match.group(0) if match else None

─── Membership ────────────────────────────────────────────────

async def check_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE): try: member = await context.bot.get_chat_member( chat_id=REQUIRED_CHANNEL_ID, user_id=user_id ) return member.status in ["member", "administrator", "creator"] except Exception as e: logger.error(f"membership error: {e}") return False

def membership_keyboard(): return InlineKeyboardMarkup([ [InlineKeyboardButton( f"📢 Kanal Katıl", url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME.lstrip('@')}" )], [InlineKeyboardButton("✅ Kontrol Et", callback_data="check")] ])

─── YT-DLP CORE ────────────────────────────────────────────────

def run_ydl(url, opts): with yt_dlp.YoutubeDL(opts) as ydl: info = ydl.extract_info(url, download=True) filename = ydl.prepare_filename(info) return filename, info

def base_opts(output, audio=False): opts = { "outtmpl": output, "quiet": True, "no_warnings": True, "format": "bestaudio/best" if audio else "best", }

if os.path.exists("cookies.txt"):
    opts["cookiefile"] = "cookies.txt"

return opts

async def download_url(url: str, audio_only: bool = False): Path(DOWNLOAD_DIR).mkdir(exist_ok=True) output = f"{DOWNLOAD_DIR}/%(id)s.%(ext)s" opts = base_opts(output, audio_only)

try:
    filename, info = await asyncio.to_thread(run_ydl, url, opts)
    title = info.get("title", "video")
    return filename, title
except Exception as e:
    return None, str(e)

─── HANDLERS ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text( "🎬 Media Downloader Bot\nLink gönder indiriyim" )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text( "📌 Desteklenen: TikTok, Instagram, YouTube, Pinterest, X\n" "📥 Link gönder yeter" )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id text = update.message.text

# membership check
if not await check_membership(user_id, context):
    await update.message.reply_text(
        "🔒 Kanala katılmadan kullanamazsın",
        reply_markup=membership_keyboard()
    )
    return

# mp3 mode
audio_only = False
if text.lower().startswith("mp3 "):
    audio_only = True
    text = text[4:]

url = extract_url(text)
if not url:
    await update.message.reply_text("❌ Link yok")
    return

platform = detect_platform(url)
if not platform:
    await update.message.reply_text("❌ Desteklenmiyor")
    return

status = await update.message.reply_text("⏳ İndiriliyor...")

filepath, title = await download_url(url, audio_only)

if not filepath or not os.path.exists(filepath):
    await status.edit_text(f"❌ Hata: {title}")
    return

await status.edit_text("📤 Yükleniyor...")

try:
    with open(filepath, "rb") as f:
        if audio_only:
            await update.message.reply_audio(audio=f, title=title[:64])
        elif filepath.endswith((".jpg", ".png", ".webp")):
            await update.message.reply_photo(photo=f, caption=title[:100])
        else:
            await update.message.reply_video(video=f, caption=title[:100])

    await status.delete()

except Exception as e:
    await status.edit_text(f"❌ Upload error: {e}")

finally:
    try:
        os.remove(filepath)
    except:
        pass

async def check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): q = update.callback_query await q.answer()

if await check_membership(q.from_user.id, context):
    await q.edit_message_text("✅ Kullanabilirsin")
else:
    await q.answer("❌ Katılmadın", show_alert=True)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.effective_user.id not in ADMIN_IDS: return await update.message.reply_text("📊 Stats yakında")

─── MAIN ────────────────────────────────────────────────

def main(): Path(DOWNLOAD_DIR).mkdir(exist_ok=True)

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CallbackQueryHandler(check_callback, pattern="check"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

logger.info("Bot running...")
app.run_polling(drop_pending_updates=True)

if name == "main": main()
