from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiomysql
import requests
from collections import defaultdict

# Параметры базы данных
DB_CONFIG = {
    "host": "rwssi.h.filess.io",
    "port": 61002,  # Добавленный порт
    "user": "sch_bridgehide",
    "password": "a5e0928f92faebd534f182a98cd68fb97f034866",
    "db": "sch_bridgehide",
}

# URL сервера авторизации
AUTH_SERVER_URL = "https://0204-213-232-244-22.ngrok-free.app/generate-token.php"
WEB_APP_URL = "https://0204-213-232-244-22.ngrok-free.app/auth.php?token="

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("📱 Отправить номер телефона", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text("Для авторизации отправьте свой номер телефона:", reply_markup=reply_markup)

# Функция запроса данных о детях и их предметах
async def get_children_and_subjects(phone_number: str):
    query = """
        SELECT DISTINCT
        CONCAT(user_parent.lastname, ' ', user_parent.firstname, ' ', user_parent.patronymic) AS parent_name, 
        CONCAT(user_child.lastname, ' ', user_child.firstname, ' ', user_child.patronymic) AS child_name, 
        subject.name AS subject_name,
        balance.count AS subject_count
        FROM parent 
        JOIN user AS user_parent ON parent.user_id = user_parent.user_id
        JOIN user AS user_child ON parent.child_id = user_child.user_id
        JOIN balance ON balance.user_id = user_child.user_id
        JOIN subject ON balance.subject_id = subject.subject_id
        WHERE user_parent.login = %s
    """
    try:
        conn = await aiomysql.connect(**DB_CONFIG)
        async with conn.cursor() as cursor:
            await cursor.execute(query, (phone_number,))
            result = await cursor.fetchall()
        await conn.ensure_closed()

        return result

    except Exception as e:
        return f"Ошибка базы данных: {str(e)}"

# Функция для получения токена авторизации
async def get_auth_token(phone_number: str):
    try:
        response = requests.post(AUTH_SERVER_URL, json={"login": phone_number}, timeout=5)
        if response.status_code != 200:
            return None, f"Ошибка сервера: {response.status_code}"

        data = response.json()
        token = data.get("token")
        if not token:
            return None, "Ошибка: токен не получен"

        return token, None

    except requests.exceptions.RequestException as e:
        return None, f"Ошибка соединения: {str(e)}"

# Обработчик получения номера телефона
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact
    phone_number = contact.phone_number

    if phone_number.startswith("+7"):
        phone_number = "8" + phone_number[2:]
    elif phone_number.startswith("7"):
        phone_number = "8" + phone_number[1:]

    # Получаем данные о детях
    children_data = await get_children_and_subjects(phone_number)

    if isinstance(children_data, str):
        await update.message.reply_text(children_data)  # Ошибка базы данных
        return

    if not children_data:
        await update.message.reply_text("Нет данных о ребенке, привязанном к этому номеру.")
        return

    # Получаем токен авторизации
    token, error = await get_auth_token(phone_number)
    if error:
        await update.message.reply_text(error)
        return

    # Группируем данные по каждому ребенку
    children_subjects = defaultdict(list)
    parent_name = children_data[0][0]  # ФИО родителя

    for row in children_data:
        child_name, subject_name, subject_count = row[1], row[2], row[3]
        children_subjects[child_name].append(f"📌 {subject_name}: {subject_count} шт.")

    # Формируем сообщение
    message = f"👨‍👩‍👧 Родитель: {parent_name}\n\n"

    for child, subjects in children_subjects.items():
        message += f"👦 Ребенок: {child}\n" + "\n".join(subjects) + "\n\n"

    message += "🔑 Для входа в систему нажмите кнопку ниже:"

    # Кнопка авторизации через WebApp
    keyboard = [[InlineKeyboardButton("🔑 Авторизация через WebApp", web_app=WebAppInfo(url=WEB_APP_URL + token))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message, reply_markup=reply_markup)

# Запуск бота
def main() -> None:
    application = Application.builder().token("7209804074:AAHD2anxD8XBdCSpF-QpCZZiZZwn5YIk_t0").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))  

    application.run_polling()

if __name__ == "__main__":
    main()
