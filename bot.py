from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import secrets
import requests
# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text("Для авторизации отправьте свой номер телефона:", reply_markup=reply_markup)

# Обработчик получения номера телефона
import requests

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact
    phone_number = contact.phone_number

    if phone_number.startswith("+7"):
        phone_number = "8" + phone_number[2:]
    elif phone_number.startswith("7"):
        phone_number = "8" + phone_number[1:]

    # Запрос токена у сервера
    try:
        response = requests.post("https://5fd2-213-232-244-22.ngrok-free.app/generate-token.php", json={"login": phone_number}, timeout=5)

        if response.status_code != 200:
            await update.message.reply_text(f"Ошибка сервера: {response.status_code}")
            return

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            await update.message.reply_text("Ошибка сервера: некорректный JSON-ответ")
            return

        token = data.get("token")
        if not token:
            await update.message.reply_text("Ошибка: токен не получен")
            return

        web_app_url = f"https://5fd2-213-232-244-22.ngrok-free.app/auth.php?token={token}"
        keyboard = [[InlineKeyboardButton("🔑 Авторизация через WebApp", web_app=WebAppInfo(url=web_app_url))]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(f"Ваш номер: {phone_number}\n\nНажмите кнопку ниже для входа:", reply_markup=reply_markup)

    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Ошибка соединения: {str(e)}")
# Запуск бота
def main() -> None:
    application = Application.builder().token("7209804074:AAHD2anxD8XBdCSpF-QpCZZiZZwn5YIk_t0").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))  # Обработчик контакта
    
    application.run_polling()

if __name__ == "__main__":
    main()
