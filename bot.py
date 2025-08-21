import os
import yt_dlp
from tqdm import tqdm
import socket
import urllib.request
import http.client

# Увеличение тайм-аута
socket.setdefaulttimeout(30)

def read_proxy_list(proxy_file):
    """Чтение списка прокси из файла."""
    proxies = []
    try:
        with open(proxy_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split(':')
                    if len(parts) >= 3:
                        proxies.append({
                            'host': parts[0],
                            'port': int(parts[1]),
                            'protocol': parts[2]
                        })
        return proxies
    except Exception as e:
        print(f"Ошибка чтения файла прокси: {str(e)}")
        return []

def check_proxy(proxy_host, proxy_port, protocol="https", timeout=5):
    """Проверка, открыт ли прокси."""
    try:
        if protocol.lower() == "socks5":
            import socks  # Требуется PySocks
            sock = socks.socksocket()
            sock.set_proxy(socks.SOCKS5, proxy_host, proxy_port)
            sock.settimeout(timeout)
            sock.connect(("www.youtube.com", 443))
            sock.close()
            print(f"Прокси {proxy_host}:{proxy_port} ({protocol}) активен.")
            return True
        else:
            conn = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=timeout)
            conn.request("HEAD", "https://www.youtube.com")
            response = conn.getresponse()
            conn.close()
            if response.status in (200, 301, 302):
                print(f"Прокси {proxy_host}:{proxy_port} ({protocol}) активен.")
                return True
            else:
                print(f"Прокси {proxy_host}:{proxy_port} ({protocol}) вернул код {response.status}.")
                return False
    except (socket.timeout, socket.gaierror, http.client.HTTPException, ImportError) as e:
        print(f"Ошибка проверки прокси {proxy_host}:{proxy_port} ({protocol}): {str(e)}")
        return False

def check_cookies_file(cookie_file):
    """Проверка валидности файла cookies."""
    try:
        if not os.path.exists(cookie_file):
            print(f"Файл cookies {cookie_file} не найден.")
            return False
        with open(cookie_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    fields = line.strip().split('\t')
                    if len(fields) != 7:
                        print(f"Неверный формат cookies в строке: {line.strip()}")
                        return False
        print(f"Файл cookies {cookie_file} валиден.")
        return True
    except Exception as e:
        print(f"Ошибка чтения файла cookies: {str(e)}")
        return False

def on_progress(d):
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
    elif d['status'] == 'finished':
        if progress_bar:
            progress_bar.close()

def check_internet_connection():
    """Проверка интернет-соединения."""
    try:
        urllib.request.urlopen("https://www.google.com", timeout=5)
        return True
    except urllib.error.URLError:
        return False

def main():
    global progress_bar
    progress_bar = None
    try:
        # Проверка интернет-соединения
        if not check_internet_connection():
            print("Ошибка: Нет интернет-соединения. Проверьте подключение и попробуйте снова.")
            return

        # Проверка файла cookies
        cookie_file = os.path.join('D:\\Youtube-bot-main', 'cookies.txt')
        if not check_cookies_file(cookie_file):
            print("Продолжаем без cookies. Это может ограничить доступ к видео.")

        # Чтение и проверка прокси
        proxy_file = os.path.join('D:\\Youtube-bot-main', 'proxy_list.txt')
        proxies = read_proxy_list(proxy_file)
        proxy_url = None
        for proxy in proxies:
            print(f"Проверяем прокси {proxy['host']}:{proxy['port']} ({proxy['protocol']})...")
            if check_proxy(proxy['host'], proxy['port'], proxy['protocol']):
                proxy_url = f"{proxy['protocol'].lower()}://{proxy['host']}:{proxy['port']}/"
                break
        if not proxy_url:
            print("Не найдено активных прокси. Продолжаем без прокси.")

        # Запрос URL
        url = input("Введите URL видео с YouTube: ").strip()
        if not url:
            raise ValueError("URL не может быть пустым.")

        # Настройки yt-dlp
        ydl_opts = {
            'format': 'bestvideo[height>=1080]+bestaudio/best',  # Предпочтение 1080p и выше
            'outtmpl': os.path.join('downloads', '%(title)s.%(ext)s'),
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'progress_hooks': [on_progress],
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookie_file if os.path.exists(cookie_file) else None,
            'retries': 5,  # Увеличение количества попыток
        }
        if proxy_url:
            ydl_opts['proxy'] = proxy_url

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получение информации о видео
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'video')

            # Проверка длительности (> 2 часов)
            if duration <= 2 * 3600:
                print("Предупреждение: Видео короче 2 часов. Продолжить загрузку? (да/нет): ")
                if input().lower() != "да":
                    return

            # Получение всех форматов
            formats = info.get('formats', [])
            valid_formats = []
            for fmt in formats:
                if fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none':
                    valid_formats.append(fmt)

            if not valid_formats:
                raise ValueError("Нет доступных форматов для этого видео.")

            # Вывод доступных форматов
            print("\nДоступные форматы для скачивания:")
            options = []
            for i, fmt in enumerate(valid_formats, start=1):
                fmt_desc = ""
                if fmt.get('vcodec') != 'none' and fmt.get('height'):
                    fmt_desc = f"Видео {fmt['height']}p"
                    if fmt.get('acodec') != 'none':
                        fmt_desc += " (с аудио)"
                    else:
                        fmt_desc += " (без аудио, будет добавлено)"
                elif fmt.get('acodec') != 'none':
                    fmt_desc = f"Аудио {fmt.get('abr', 'неизвестно')}kbps"
                else:
                    continue
                size_mb = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                size_mb = size_mb / (1024 * 1024) if size_mb else 0
                print(f"{i}. {fmt_desc} - Примерный размер: {size_mb:.2f} MB")
                options.append(fmt)

            if not options:
                raise ValueError("Нет подходящих форматов (видео или аудио).")

            # Запрос выбора
            choice = int(input("\nВыберите номер формата: ")) - 1
            if choice < 0 or choice >= len(options):
                raise ValueError("Неверный выбор.")

            selected_format = options[choice]['format_id']
            ydl_opts['format'] = f"{selected_format}+bestaudio/best" if options[choice].get('acodec') == 'none' else selected_format

            # Создание папки
            os.makedirs('downloads', exist_ok=True)
            print(f"\nЗагружаем: {title}")

            # Загрузка
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            print(f"Файл сохранен в папке: downloads")

    except yt_dlp.DownloadError as e:
        print(f"Ошибка загрузки: {str(e)}. Возможно, видео ограничено по региону или требует cookies. Проверьте cookies.txt или используйте VPN.")
    except urllib.error.URLError as e:
        print(f"Ошибка соединения: {str(e)}. Проверьте сеть, прокси или используйте VPN.")
    except ValueError as e:
        print(f"Ошибка ввода: {str(e)}")
    except Exception as e:
        print(f"Неожиданная ошибка: {str(e)}")
    finally:
        if progress_bar:
            progress_bar.close()

if __name__ == "__main__":
    main()
