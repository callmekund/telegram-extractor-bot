import telebot
import os
import requests
import yt_dlp
import re
from telebot import types

BOT_TOKEN = 'BOT_TOKEN'
bot = telebot.TeleBot(BOT_TOKEN)
DOWNLOAD_DIR = 'downloads'

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

user_quality = {}
user_file_path = {}
user_course_name = {}
user_name = "Anonymous"  # You can customize this if needed

# Start message handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Send me a .txt file with titles + video/pdf links.")

# Handle document (txt file)
@bot.message_handler(content_types=['document'])
def handle_file(message):
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    file_path = os.path.join(DOWNLOAD_DIR, f"{message.chat.id}_links.txt")
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)

    user_file_path[message.chat.id] = file_path
    bot.send_message(message.chat.id, "Please enter the course name:")
    bot.register_next_step_handler(message, process_course_name)

# Process course name
def process_course_name(message):
    user_course_name[message.chat.id] = message.text
    markup = types.InlineKeyboardMarkup()
    for quality in ['144', '360', '480', '720', '1080']:
        markup.add(types.InlineKeyboardButton(f"{quality}p", callback_data=f"quality_{quality}"))
    
    bot.send_message(message.chat.id, "Choose video quality for this file:", reply_markup=markup)

# Quality selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("quality_"))
def quality_selected(call):
    quality = call.data.split("_")[1]
    user_quality[call.message.chat.id] = quality
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"Selected quality: {quality}p. Starting download...")

    file_path = user_file_path.get(call.message.chat.id)
    if file_path:
        process_links(call.message.chat.id, file_path, quality)

# Extract URL from line in the txt file
def extract_url_from_line(line):
    match = re.search(r'https?://\S+', line)
    return match.group() if match else None

# Process the links in the txt file
def process_links(chat_id, file_path, quality):
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            url = extract_url_from_line(line)
            if url:
                title = line.replace(url, '').strip(" \n:-")
                try:
                    if url.endswith('.pdf'):
                        download_pdf(chat_id, url, title)
                    else:
                        download_video(chat_id, url, title, quality)
                except Exception as e:
                    bot.send_message(chat_id, f"❌ Error with link:\n{url}\n{str(e)}")

# Download PDF
def download_pdf(chat_id, url, title):
    filename = os.path.basename(url)
    save_path = os.path.join(DOWNLOAD_DIR, filename)
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        raise Exception("Failed to download PDF")

    total = int(response.headers.get('content-length', 0))
    downloaded = 0
    chunk_size = 1024
    progress_msg = bot.send_message(chat_id, f"📥 Downloading **{title}**...\n[░░░░░░░░░░] 0%", parse_mode="Markdown")

    def make_bar(percent):
        filled = int(percent / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}] {percent}%"

    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                percent = int((downloaded / total) * 100)
                if percent % 10 == 0:
                    try:
                        bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id,
                                              text=f"📥 Downloading **{title}**...\n{make_bar(percent)}",
                                              parse_mode="Markdown")
                    except:
                        pass

    with open(save_path, 'rb') as f:
        caption = f"📘 {title}\nDownloaded by {user_name}\nCourse: {user_course_name.get(chat_id, 'Unknown')}"
        bot.send_document(chat_id, f, caption=caption)

    bot.delete_message(chat_id, progress_msg.message_id)

# Download Video (supports m3u8)
def download_video(chat_id, url, title, quality):
    filename = f"{title.replace(' ', '_')}.mp4"
    save_path = os.path.join(DOWNLOAD_DIR, filename)

    progress_msg = bot.send_message(chat_id, f"📥 Downloading **{title}**...\n[░░░░░░░░░░] 0%", parse_mode="Markdown")

    def hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip().replace('%', '')
            try:
                bar = make_bar(int(float(percent)))
                bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id,
                                      text=f"📥 Downloading **{title}**...\n{bar}",
                                      parse_mode="Markdown")
            except:
                pass

    def make_bar(percent):
        filled = int(percent / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}] {percent}%"

    ydl_opts = {
        'outtmpl': save_path,
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best',
        'progress_hooks': [hook],
        'quiet': True,
        'merge_output_format': 'mp4',
        'noplaylist': True,
        'ignoreerrors': True,
        'retries': 10,
        'hls_prefer_native': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0',
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        upload_file_with_progress(chat_id, save_path, 'video', title)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Failed to download **{title}**\nError: {str(e)}")
        bot.delete_message(chat_id, progress_msg.message_id)

# Upload File with Progress
def upload_file_with_progress(chat_id, file_path, file_type, title):
    progress_msg = bot.send_message(chat_id, f"📤 Uploading **{title}**...\n[░░░░░░░░░░] 0%", parse_mode="Markdown")

    total_size = os.path.getsize(file_path)
    uploaded = 0
    chunk_size = 1024

    def make_bar(percent):
        filled = int(percent / 10)
        empty = 10 - filled
        return f"[{'█' * filled}{'░' * empty}] {percent}%"

    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            uploaded += len(chunk)
            percent = int((uploaded / total_size) * 100)
            if percent % 10 == 0:
                try:
                    bot.edit_message_text(chat_id=chat_id, message_id=progress_msg.message_id,
                                          text=f"📤 Uploading **{title}**...\n{make_bar(percent)}", parse_mode="Markdown")
                except:
                    pass

        f.seek(0)
        if file_type == 'video':
            bot.send_video(chat_id, f, caption=f"🎥 {title}\nDownloaded by {user_name}\nCourse: {user_course_name.get(chat_id, 'Unknown')}")
        else:
            bot.send_document(chat_id, f, caption=f"📘 {title}\nDownloaded by {user_name}\nCourse: {user_course_name.get(chat_id, 'Unknown')}")
        bot.delete_message(chat_id, progress_msg.message_id)

# Start polling
print("Bot is running...")
bot.infinity_polling()
