import telebot

from config import TOKEN

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    welcome_text = (
        "Привет! Я бот для работы с whitelist/blacklist.\n"
        "Доступные команды:\n"
        "/start - показать это сообщение\n"
        "/get_whitelist - получить файл whitelist.json\n"
        "/get_blacklist - получить файл blacklist.json"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['get_whitelist'])
def handle_get_whitelist(message):
    """Отправить файл whitelist.json"""
    try:
        with open('whitelist.json', 'rb') as f:
            bot.send_document(message.chat.id, f)
    except FileNotFoundError:
        bot.reply_to(message, "Файл whitelist.json не найден")


@bot.message_handler(commands=['get_blacklist'])
def handle_get_whitelist(message):
    """Отправить файл blacklist.json"""
    try:
        with open('blacklist.json', 'rb') as f:
            bot.send_document(message.chat.id, f)
    except FileNotFoundError:
        bot.reply_to(message, "Файл blacklist.json не найден")


if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
