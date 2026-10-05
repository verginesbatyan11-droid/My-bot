import os
import re
import logging
import imageio_ffmpeg
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для скачивания музыки.\n\n"
        "1. Отправь мне ссылку на YouTube или TikTok.\n"
        "2. Или просто напиши название песни (например: EMIN JONY Камин)."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Инструкция:\n"
        "• Отправь прямую ссылку на видео/трек.\n"
        "• Или напиши название песни текстом.\n\n"
        "Если скачать не получается, попробуй прислать ссылку из TikTok!"
    )

def download_audio(query_or_url: str) -> tuple[str, str]:
    is_url = bool(re.match(r'https?://', query_or_url))
    search_query = query_or_url if is_url else f"ytsearch1:{query_or_url}"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': FFMPEG_PATH,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
    }

    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        
        title = info.get('title', 'audio')
        filename = ydl.prepare_filename(info)
        mp3_filename = os.path.splitext(filename)[0] + '.mp3'
        return mp3_filename, title

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    msg = await update.message.reply_text("🔎 Ищу и скачиваю трек, подождите...")

    try:
        file_path, title = download_audio(text)
        await update.message.reply_audio(
            audio=open(file_path, 'rb'),
            title=title,
            caption="Вот ваш трек! 🎵"
        )
        await msg.delete()
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logging.error(f"Error downloading: {e}")
        await msg.edit_text("❌ Не удалось найти или скачать этот трек. Попробуйте отправить прямую ссылку на видео!")

if __name__ == '__main__':
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"  # <--- сюда вставьте токен от @BotFather, если нужно

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

