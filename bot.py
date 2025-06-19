from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import requests

TOKEN = "ТВОЙ_ТОКЕН"
API_URL = "http://IP_ТВОЕГО_СЕРВЕРА:8000/check_driver/"

async def handle_message(update: Update, context):
    text = update.message.text
    try:
        series, date = text.split()  # Пример: "123456 2020-01-01"
        response = requests.get(f"{API_URL}?series={series}&date={date}").json()
        await update.message.reply_text(str(response))
    except:
        await update.message.reply_text("Ошибка. Введи серию и дату через пробел.")

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.run_polling()