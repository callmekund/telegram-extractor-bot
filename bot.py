import telebot
import os
import requests
from yt_dlp import YoutubeDL
from zipfile import ZipFile

API_TOKEN = 'YOUR_BOT_API_TOKEN'
bot = telebot.TeleBot(API_TOKEN)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "Hi! Send me a .txt file with video & PDF links.")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = os.path.join(DOWNLOAD_DIR, "links.txt")
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.reply_to(message, "Processing your file...")

    process_links(message.chat.id, file_path)

def process_links(chat_id, file_path):
    video_links = []
    pdf_links = []

    with open(file_path, 'r') as f:
        for line in f:
            link = line.strip()
            if not link:
                continue
            if link.endswith(".pdf"):
                pdf_links.append(link)
            else:
                video_links.append(link)

    pdf_folder = os.path.join(DOWNLOAD_DIR, "pdfs")
    os.makedirs(pdf_folder, exist_ok=True)

    for link in pdf_links:
        try:
            filename = os.path.basename(link)
            pdf_path = os.path.join(pdf_folder, filename)
            r = requests.get(link)
            with open(pdf_path, 'wb') as f:
                f.write(r.content)
            bot.send_document(chat_id, open(pdf_path, 'rb'))
        except:
            bot.send_message(chat_id, f"Failed to download PDF: {link}")

    video_folder = os.path.join(DOWNLOAD_DIR, "videos")
    os.makedirs(video_folder, exist_ok=True)

    ydl_opts = {
        'outtmpl': os.path.join(video_folder, '%(title)s.%(ext)s'),
        'format': 'best'
    }

    with YoutubeDL(ydl_opts) as ydl:
        for link in video_links:
            try:
                ydl.download([link])
            except:
                bot.send_message(chat_id, f"Failed to download video: {link}")

    zip_path = os.path.join(DOWNLOAD_DIR, "videos.zip")
    with ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(video_folder):
            for file in files:
                zipf.write(os.path.join(root, file), arcname=file)

    if os.path.getsize(zip_path) < 2 * 1024 * 1024 * 1024:
        bot.send_document(chat_id, open(zip_path, 'rb'))
    else:
        bot.send_message(chat_id, "Videos zipped but file too large for Telegram. Upload manually.")

bot.polling()