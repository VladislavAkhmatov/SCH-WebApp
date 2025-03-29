from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import aiomysql
import requests
import re
from collections import defaultdict

# Параметры базы данных
DB_CONFIG = {
    "host": "rwssi.h.filess.io",
    "port": 61002,
    "user": "sch_bridgehide",
    "password": "a5e0928f92faebd534f182a98cd68fb97f034866",
    "db": "sch_bridgehide",
}

# URL сервера авторизации
AUTH_SERVER_URL = "https://7101-213-232-244-22.ngrok-free.app/generate-token.php"
WEB_APP_URL = "https://7101-213-232-244-22.ngrok-free.app/auth.php?token="

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [KeyboardButton("📱 Отправить номер телефона", request_contact=True)],
        [KeyboardButton("✏️ Ввести номер вручную")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        "Для авторизации отправьте свой номер телефона:\n\n"
        "Вы можете:\n"
        "1. Нажать кнопку '📱 Отправить номер телефона'\n"
        "2. Или ввести номер вручную в формате 87XXXXXXXXX",
        reply_markup=reply_markup
    )

# Функция для нормализации номера телефона
def normalize_phone_number(phone_number: str) -> str:
    # Удаляем все нецифровые символы
    digits = re.sub(r'\D', '', phone_number)
    
    # Приводим к формату 87XXXXXXXXX
    if digits.startswith('7') and len(digits) == 11:
        return '8' + digits[1:]
    elif digits.startswith('+7') and len(digits) == 12:
        return '8' + digits[2:]
    elif digits.startswith('8') and len(digits) == 11:
        return digits
    elif digits.startswith('7') and len(digits) == 10:
        return '8' + digits
    else:
        return digits  # Вернем как есть, валидация будет позже

# Функция для проверки валидности номера телефона
def is_valid_phone_number(phone_number: str) -> bool:
    # Проверяем, что номер соответствует формату 87XXXXXXXXX
    return re.fullmatch(r'87\d{9}', phone_number) is not None

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
        LEFT JOIN balance ON balance.user_id = user_child.user_id
        LEFT JOIN subject ON balance.subject_id = subject.subject_id
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

# Обработчик текстовых сообщений (для ручного ввода номера)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    
    # Если пользователь нажал кнопку "Ввести номер вручную"
    if text == "✏️ Ввести номер вручную":
        await update.message.reply_text(
            "Пожалуйста, введите номер телефона в формате 87XXXXXXXXX (11 цифр):",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("↩️ Назад")]], resize_keyboard=True)
        )
        return
    
    # Если пользователь нажал кнопку "Назад"
    if text == "↩️ Назад":
        await start(update, context)
        return
    
    # Нормализуем номер телефона
    normalized_phone = normalize_phone_number(text)
    
    # Проверяем валидность номера
    if not is_valid_phone_number(normalized_phone):
        await update.message.reply_text(
            "❌ Некорректный формат номера телефона.\n"
            "Пожалуйста, введите номер в формате 87XXXXXXXXX (11 цифр) или используйте кнопку отправки контакта."
        )
        return
    
    # Если номер валиден, обрабатываем его
    await process_phone_number(update, normalized_phone)

# Обработчик получения номера телефона (из контакта)
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact
    phone_number = contact.phone_number
    
    # Нормализуем номер телефона
    normalized_phone = normalize_phone_number(phone_number)
    
    # Проверяем валидность номера
    if not is_valid_phone_number(normalized_phone):
        await update.message.reply_text(
            "❌ Некорректный формат номера телефона в контакте.\n"
            "Пожалуйста, введите номер вручную или попробуйте отправить контакт еще раз."
        )
        return
    
    # Если номер валиден, обрабатываем его
    await process_phone_number(update, normalized_phone)

# Общая функция обработки номера телефона
async def process_phone_number(update: Update, phone_number: str) -> None:
    # Получаем токен авторизации
    token, error = await get_auth_token(phone_number)
    if error:
        await update.message.reply_text(error)
        return

    # Получаем данные о детях
    children_data = await get_children_and_subjects(phone_number)

    if isinstance(children_data, str):
        await update.message.reply_text(children_data)  # Ошибка базы данных
        return

    if not children_data:
        # Нет данных вообще - просто выводим кнопку авторизации
        message = "🔑 Для входа в систему нажмите кнопку ниже:"
    else:
        # Проверяем, есть ли записи с уроками (subject_name и subject_count не NULL)
        has_lessons = any(row[2] is not None and row[3] is not None for row in children_data)
        
        if not has_lessons:
            # Есть данные о детях, но нет уроков
            parent_name = children_data[0][0]
            child_names = set(row[1] for row in children_data if row[1])
            
            message = f"👨‍👩‍👧 Родитель: {parent_name}\n\n"
            message += "👦 Дети: " + ", ".join(child_names) + "\n\n"
            message += "ℹ️ Нет информации о доступных уроках\n\n"
            message += "🔑 Для входа в систему нажмите кнопку ниже:"
        else:
            # Есть данные с уроками - формируем полное сообщение
            children_subjects = defaultdict(list)
            parent_name = children_data[0][0]

            for row in children_data:
                if row[2] and row[3]:  # Только если есть subject_name и subject_count
                    child_name, subject_name, subject_count = row[1], row[2], row[3]
                    children_subjects[child_name].append(f"📌 {subject_name}: {subject_count} шт.")

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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    application.run_polling()

if __name__ == "__main__":
    main()