import os
import io
import time
import asyncio
import httpx
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from yt_dlp import YoutubeDL
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8733776616:AAEDPLDwuxLrm_1FoakNny48nvB6R03fiec"
GEMINI_API_KEY = "AQ.Ab8RN6LL_DI91NMurxQyqGUP9X8BDsNAhkp0emtwkqAWOFv2kw"

keyboard = [[KeyboardButton("Help")]]
reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

executor = ThreadPoolExecutor(max_workers=4)

IMAGE_TRIGGER_WORDS = [
    "нарисуй", "сделай фото", "сделай картинку", "создай картинку", 
    "создай фото", "сгенерируй", "draw", "generate photo", "picture of",
    "нарисуй мне", "покажи фото", "создай 3d", "нарисуй 3d", "создай"
]

MUSIC_TRIGGER_WORDS = [
    "скачай музыку", "скачай песню", "найди песню", "скачай трек",
    "найди музыку", "музыка", "скачай аудио", "скачай", "найти музыку", "найти песню"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я твой ИИ-помощник Gemini.\n\n"
        "💬 Задавай мне любые вопросы.\n"
        "🎨 Генерируй картинки (*создай кота в космосе*).\n"
        "🎵 Скачивай музыку (*найти музыку камина*).",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def translate_to_english(text):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": f"Translate this image prompt to English precisely. Output ONLY the English translation: {text}"}]
            }]
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                return data['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception:
        pass
    return text

def sync_download_audio(song_name):
    timestamp = int(time.time())
    out_filename = f"song_{timestamp}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1:',
        'outtmpl': f'{out_filename}.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'socket_timeout': 10,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=True)
            if info and 'entries' in info and len(info['entries']) > 0:
                entry = info['entries'][0]
                title = entry.get('title', song_name)
                expected_mp3 = f"{out_filename}.mp3"
                if os.path.exists(expected_mp3):
                    return expected_mp3, title
                downloaded = ydl.prepare_filename(entry)
                return downloaded, title
    except Exception as e:
        print("Ошибка загрузки музыки:", e)
    return None, None

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    lower_text = user_text.lower()

    if lower_text == "help":
        help_message = "🛠 Если у вас возникли проблемы или вопросы, пожалуйста, напишите владельцу бота."
        await update.message.reply_text(help_message, reply_markup=reply_markup)
        return

    is_music = any(lower_text.startswith(trigger) for trigger in MUSIC_TRIGGER_WORDS)
    if is_music:
        await update.message.chat.send_action("upload_voice")
        
        song_query = user_text
        for trigger in MUSIC_TRIGGER_WORDS:
            if lower_text.startswith(trigger):
                song_query = user_text[len(trigger):].strip(" :,-")
                break
        
        if not song_query:
            await update.message.reply_text("Пожалуйста, укажите название. Например: `найти музыку камина`", parse_mode="Markdown")
            return

        status_msg = await update.message.reply_text(f"🔍 Ищу и скачиваю: **{song_query}**...", parse_mode="Markdown")
        
        loop = asyncio.get_event_loop()
        try:
            file_path, song_title = await asyncio.wait_for(
                loop.run_in_executor(executor, sync_download_audio, song_query),
                timeout=25.0
            )
        except asyncio.TimeoutError:
            await status_msg.edit_text("⏱️ Поиск трека занял слишком много времени. Попробуйте уточнить название.")
            return

        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as audio:
                    await update.message.reply_audio(audio=audio, title=song_title, caption=f"🎵 {song_title}", reply_markup=reply_markup)
                os.remove(file_path)
                await status_msg.delete()
                return
            except Exception as e:
                await update.message.reply_text(f"Ошибка отправки: {e}")
        else:
            await status_msg.edit_text("Не удалось найти или скачать этот трек.")
        return

    is_draw = any(trigger in lower_text for trigger in IMAGE_TRIGGER_WORDS)
    if is_draw:
        await update.message.chat.send_action("upload_photo")
        
        prompt = user_text
        for trigger in IMAGE_TRIGGER_WORDS:
            if trigger in lower_text:
                start_idx = lower_text.find(trigger)
                prompt = user_text[start_idx + len(trigger):].strip(" :,-")
                break
        
        if not prompt:
            prompt = user_text

        english_prompt = await translate_to_english(prompt)
        encoded_prompt = urllib.parse.quote(english_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={int(time.time())}"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                img_res = await client.get(image_url)
                if img_res.status_code == 200:
                    image_bytes = io.BytesIO(img_res.content)
                    image_bytes.name = 'generated.jpg'
                    await update.message.reply_photo(photo=image_bytes, caption=f"🎨 Готово: {prompt}", reply_markup=reply_markup)
                    return
        except Exception as e:
            await update.message.reply_text(f"Ошибка при генерации картинки: {e}", reply_markup=reply_markup)
            return

    await update.message.chat.send_action("typing")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "system_instruction": {
            "parts": [{"text": "Ты многоязычный ассистент. Отвечай пользователю строго на том языке, на котором он пишет."}]
        },
        "contents": [{
            "parts": [{"text": user_text}]
        }]
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(2):
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    answer = data['candidates'][0]['content']['parts'][0]['text']
                    await update.message.reply_text(answer, reply_markup=reply_markup)
                    return
            except httpx.TimeoutException:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                await update.message.reply_text("⏱️ Сервер Gemini временно недоступен. Попробуйте ещё раз.", reply_markup=reply_markup)
                return
            except Exception as e:
                await update.message.reply_text(f"Произошла ошибка: {e}", reply_markup=reply_markup)
                return

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))
    print("Бот успешно запущен!")
    app.run_polling()


