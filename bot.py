import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
import logging
from tqdm import tqdm
import urllib.request

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация Telegram бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Установите в Render Environment Variables
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Путь к файлу cookies в контейнере
COOKIE_FILE = "/app/cookies.txt"

# Глобальная переменная для прогресс-бара
progress_bar = None
current_download = {}

def check_cookies_file(cookie_file):
    """Проверка валидности файла cookies."""
    try:
        if not os.path.exists(cookie_file):
            logger.warning(f"Файл cookies {cookie_file} не найден.")
            return False
        with open(cookie_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                logger.warning(f"Файл cookies {cookie_file} пуст.")
                return False
            if not (lines[0].startswith('# Netscape HTTP Cookie File') or lines[0].startswith('# HTTP Cookie File')):
                logger.warning(f"Неверный формат заголовка в файле cookies {cookie_file}.")
                return False
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    fields = line.strip().split('\t')
                    if len(fields) != 7:
                        logger.warning(f"Неверный формат cookies в строке: {line.strip()}")
                        return False
        logger.info(f"Файл cookies {cookie_file} валиден.")
        return True
    except Exception as e:
        logger.error(f"Ошибка чтения файла cookies: {str(e)}")
        return False

def check_internet_connection():
    """Проверка интернет-соединения."""
    try:
        urllib.request.urlopen("https://www.google.com", timeout=5)
        return True
    except urllib.error.URLError:
        return False

def on_progress(d, chat_id):
    """Callback-функция для прогресс-бара."""
    global progress_bar
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        downloaded_bytes = d.get('downloaded_bytes', 0)
        percentage = (downloaded_bytes / total_bytes * 100) if total_bytes else 0
        if not progress_bar:
            progress_bar = tqdm(total=total_bytes, unit="bytes", unit_scale=True, desc="Загрузка")
        progress_bar.n = downloaded_bytes
        progress_bar.set_postfix({"Скачано": f"{percentage:.1f}%"})
        progress_bar.refresh()
        if percentage > (current_download.get(chat_id, {}).get('last_percentage', 0) + 10):
            current_download[chat_id]['last_percentage'] = percentage
            asyncio.create_task(bot.send_message(chat_id, f"Прогресс загрузки: {percentage:.1f}%"))
    elif d['status'] == 'finished':
        if progress_bar:
            progress_bar.close()
            progress_bar = None
        asyncio.create_task(bot.send_message(chat_id, "Загрузка завершена!"))

async def download_video(url, chat_id, format_id=None):
    """Загрузка видео с YouTube."""
    try:
        ydl_opts = {
            'format': format_id or 'bestvideo[height>=1080]+bestaudio/best',
            'outtmpl': '/app/downloads/%(title)s.%(ext)s',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'progress_hooks': [lambda d: on_progress(d, chat_id)],
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'cookiefile': COOKIE_FILE if check_cookies_file(COOKIE_FILE) else None,
            'retries': 5,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'video')

            if duration <= 2 * 3600:
                await bot.send_message(chat_id, f"Предупреждение: Видео '{title}' короче 2 часов. Продолжить? (Ответьте 'да' или 'нет')")
                current_download[chat_id] = {'url': url, 'state': 'awaiting_duration_confirmation', 'info': info}
                return

            if not format_id:
                formats = info.get('formats', [])
                valid_formats = [fmt for fmt in formats if fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none']
                if not valid_formats:
                    await bot.send_message(chat_id, "Нет доступных форматов для этого видео.")
                    return

                message = "Доступные форматы:\n"
                current_download[chat_id] = {'url': url, 'formats': valid_formats, 'state': 'awaiting_format_selection'}
                for i, fmt in enumerate(valid_formats, start=1):
                    fmt_desc = ""
                    if fmt.get('vcodec') != 'none' and fmt.get('height'):
                        fmt_desc = f"Видео {fmt['height']}p"
                        if fmt.get('acodec') != 'none':
                            fmt_desc += " (с аудио)"
                        else:
                            fmt_desc += " (без аудио)"
                    elif fmt.get('acodec') != 'none':
                        fmt_desc = f"Аудио {fmt.get('abr', 'неизвестно')}kbps"
                    size_mb = (fmt.get('filesize') or fmt.get('filesize_approx', 0)) / (1024 * 1024) if fmt.get('filesize') else 0
                    message += f"{i}. {fmt_desc} - {size_mb:.2f} MB\n"
                await bot.send_message(chat_id, message + "\nВыберите номер формата:")
                return

            os.makedirs('/app/downloads', exist_ok=True)
            await bot.send_message(chat_id, f"Загружаем: {title}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            await bot.send_message(chat_id, f"Файл сохранен в /app/downloads/{title}.mp4")
            current_download.pop(chat_id, None)

    except yt_dlp.DownloadError as e:
        error_msg = str(e)
        await bot.send_message(chat_id, f"Ошибка загрузки: {error_msg}. Проверьте cookies или региональные ограничения.")
        logger.error(f"Download error: {error_msg}")
    except Exception as e:
        await bot.send_message(chat_id, f"Неожиданная ошибка: {str(e)}")
        logger.error(f"Unexpected error: {str(e)}")

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Отправьте URL видео с YouTube для загрузки.")

@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id
    text = message.text.strip()

    if chat_id in current_download:
        if current_download[chat_id].get('state') == 'awaiting_duration_confirmation':
            if text.lower() == 'да':
                await download_video(current_download[chat_id]['url'], chat_id)
            else:
                await message.answer("Загрузка отменена.")
                current_download.pop(chat_id, None)
            return
        elif current_download[chat_id].get('state') == 'awaiting_format_selection':
            try:
                choice = int(text) - 1
                formats = current_download[chat_id]['formats']
                if 0 <= choice < len(formats):
                    format_id = formats[choice]['format_id']
                    if formats[choice].get('acodec') == 'none':
                        format_id = f"{format_id}+bestaudio/best"
                    await download_video(current_download[chat_id]['url'], chat_id, format_id)
                else:
                    await message.answer("Неверный выбор. Выберите номер формата.")
            except ValueError:
                await message.answer("Введите число, соответствующее номеру формата.")
            return

    if text.startswith('http://') or text.startswith('https://'):
        if not check_internet_connection():
            await message.answer("Ошибка: Нет интернет-соединения.")
            return
        if not check_cookies_file(COOKIE_FILE):
            await message.answer("Файл cookies недействителен или отсутствует. Это может ограничить доступ.")
        current_download[chat_id] = {'last_percentage': 0}
        await download_video(text, chat_id)
    else:
        await message.answer("Пожалуйста, отправьте валидный URL видео с YouTube.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN не установлен.")
        exit(1)
    asyncio.run(main())
