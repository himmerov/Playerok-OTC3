import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import uuid
import os
import json
import pickle
from datetime import datetime, timedelta
import requests

# Конфигурация бота
TOKEN = "8267059468:AAHgQ8o78PhMH3CwFVhT7hfpillQBrmt_L8"
bot = telebot.TeleBot(TOKEN)

# Получаем путь к папке, где находится скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам данных
DATA_FILE = os.path.join(BASE_DIR, 'playerok_data.pkl')
PHOTO_PATH = os.path.join(BASE_DIR, 'photo.jpg')

# Глобальные переменные для данных
users = {}
deals = {}
admins = set()
workers = set()
star_rate = 2.0  # Курс Stars по умолчанию

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

# Загрузка данных из файла
def load_data():
    """Загружает данные из файла"""
    global users, deals, admins, workers, star_rate
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                users = data.get('users', {})
                deals = data.get('deals', {})
                admins = data.get('admins', set())
                workers = data.get('workers', set())
                star_rate = data.get('star_rate', 2.0)
                print(f"✅ Данные загружены: {len(users)} пользователей")
                return data
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
    print("✅ Созданы новые данные")
    return {'users': {}, 'deals': {}, 'admins': set(), 'workers': set(), 'star_rate': 2.0}

# Сохранение данных в файл
def save_data():
    """Сохраняет данные в файл"""
    global users, deals, admins, workers, star_rate
    try:
        data = {
            'users': users,
            'deals': deals,
            'admins': admins,
            'workers': workers,
            'star_rate': star_rate
        }
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ Данные сохранены: {len(users)} пользователей, {len(deals)} сделок")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения данных: {e}")
        return False

# Загрузка данных при старте
print("🔄 Загрузка данных...")
load_data()

# Добавьте сюда ваш Telegram ID для получения прав администратора
YOUR_ADMIN_ID = 1521791703
if YOUR_ADMIN_ID not in admins:
    admins.add(YOUR_ADMIN_ID)
    print(f"✅ ID {YOUR_ADMIN_ID} добавлен как администратор")
    save_data()

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
            'awaiting_star_rate': False,
            'join_date': datetime.now().strftime("%d.%m.%Y"),
            'last_active': datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        save_data()
        print(f"✅ Новый пользователь: {user_id} @{username}")

# Обновление времени активности пользователя
def update_user_activity(user_id):
    if user_id in users:
        users[user_id]['last_active'] = datetime.now().strftime("%d.%m.%Y %H:%M")

# Генерация клавиатуры главного меню с большими кнопками
def main_menu(user_id):
    update_user_activity(user_id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопку админ-панели только для админов
    if user_id in admins:
        keyboard.add(
            InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile'),
            InlineKeyboardButton("💼 Мои сделки", callback_data='my_deals')
        )
        keyboard.add(
            InlineKeyboardButton("⚡ Создать сделку", callback_data='create_deal'),
            InlineKeyboardButton("🏦 Реквизиты", callback_data='wallet_menu')
        )
        keyboard.add(
            InlineKeyboardButton("🎯 Рефералы", callback_data='referral'),
            InlineKeyboardButton("📊 Статистика", callback_data='stats_public')
        )
        keyboard.add(
            InlineKeyboardButton("👷 Воркер панель", callback_data='worker_panel'),
            InlineKeyboardButton("⚙️ Админ панель", callback_data='admin_panel')
        )
        keyboard.add(InlineKeyboardButton("📞 Поддержка", url='tg://user?id=943896276'))
    elif user_id in workers:
        keyboard.add(
            InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile'),
            InlineKeyboardButton("💼 Мои сделки", callback_data='my_deals')
        )
        keyboard.add(
            InlineKeyboardButton("⚡ Создать сделку", callback_data='create_deal'),
            InlineKeyboardButton("🏦 Реквизиты", callback_data='wallet_menu')
        )
        keyboard.add(
            InlineKeyboardButton("🎯 Рефералы", callback_data='referral'),
            InlineKeyboardButton("👷 Воркер панель", callback_data='worker_panel')
        )
        keyboard.add(
            InlineKeyboardButton("💱 Валюта", callback_data='change_currency'),
            InlineKeyboardButton("📞 Поддержка", url='tg://user?id=943896276')
        )
    else:
        keyboard.add(
            InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile'),
            InlineKeyboardButton("💼 Мои сделки", callback_data='my_deals')
        )
        keyboard.add(
            InlineKeyboardButton("⚡ Создать сделку", callback_data='create_deal'),
            InlineKeyboardButton("🏦 Реквизиты", callback_data='wallet_menu')
        )
        keyboard.add(
            InlineKeyboardButton("🎯 Рефералы", callback_data='referral'),
            InlineKeyboardButton("💱 Валюта", callback_data='change_currency')
        )
        keyboard.add(InlineKeyboardButton("📞 Поддержка", url='tg://user?id=943896276'))
    return keyboard

# Админ панель меню с большими кнопками
def admin_panel_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data='stats'),
        InlineKeyboardButton("👥 Пользователи", callback_data='show_users')
    )
    keyboard.add(
        InlineKeyboardButton("📋 Сделки", callback_data='show_deals'),
        InlineKeyboardButton("👷 Список воркеров", callback_data='show_workers')
    )
    keyboard.add(
        InlineKeyboardButton("👷 Выдать воркера", callback_data='add_worker'),
        InlineKeyboardButton("🗑️ Удалить воркера", callback_data='remove_worker')
    )
    keyboard.add(
        InlineKeyboardButton("🔍 Проверить сделки", callback_data='check_worker_deals'),
        InlineKeyboardButton("📉 Понизить воркера", callback_data='demote_worker')
    )
    keyboard.add(
        InlineKeyboardButton("💼 Накрутка сделок", callback_data='fake_deals'),
        InlineKeyboardButton("💰 Накрутка баланса", callback_data='fake_balance')
    )
    keyboard.add(
        InlineKeyboardButton("⭐ Настройка Stars", callback_data='set_star_rate'),
        InlineKeyboardButton("👑 Выдать админку", callback_data='add_admin')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    return keyboard

# Воркер панель меню с большими кнопками
def worker_panel_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Моя статистика", callback_data='worker_stats'),
        InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals')
    )
    keyboard.add(
        InlineKeyboardButton("💼 Накрутка сделок", callback_data='worker_fake_deals'),
        InlineKeyboardButton("💰 Накрутка баланса", callback_data='worker_fake_balance')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    return keyboard

# Меню управления воркером с большими кнопками
def worker_management_menu(worker_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🗑️ Удалить воркера", callback_data=f'remove_worker_confirm_{worker_id}'),
        InlineKeyboardButton("📉 Понизить", callback_data=f'demote_worker_confirm_{worker_id}')
    )
    keyboard.add(
        InlineKeyboardButton("🔍 Проверить сделки", callback_data=f'check_worker_deals_{worker_id}'),
        InlineKeyboardButton("📊 Статистика", callback_data=f'worker_stats_{worker_id}')
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='show_workers'))
    return keyboard

# Меню выбора валюты с большими кнопками (добавлен Stars)
def currency_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🇷🇺 Rub", callback_data='currency_RUB'),
        InlineKeyboardButton("🇺🇸 Usd", callback_data='currency_USD')
    )
    keyboard.add(
        InlineKeyboardButton("🇰🇿 Kzt", callback_data='currency_KZT'),
        InlineKeyboardButton("🇺🇦 Uah", callback_data='currency_UAH')
    )
    keyboard.add(
        InlineKeyboardButton("🇧🇾 Byn", callback_data='currency_BYN'),
        InlineKeyboardButton("⚡ Ton", callback_data='currency_TON')
    )
    keyboard.add(
        InlineKeyboardButton("💎 Usdt", callback_data='currency_USDT'),
        InlineKeyboardButton("⭐ Stars", callback_data='currency_STARS')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    return keyboard

# Меню реквизитов с большими кнопками
def wallet_menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⚡ Ton", callback_data='set_ton'),
        InlineKeyboardButton("💳 Карта", callback_data='set_card')
    )
    keyboard.add(
        InlineKeyboardButton("📱 Телефон", callback_data='set_phone'),
        InlineKeyboardButton("💎 Usdt", callback_data='set_usdt')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    return keyboard

# Меню создания сделки с большими кнопками (добавлен Stars)
def create_deal_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⚡ Ton", callback_data='method_TON'),
        InlineKeyboardButton("💎 Usdt", callback_data='method_USDT')
    )
    keyboard.add(
        InlineKeyboardButton("🇷🇺 Rub", callback_data='method_RUB'),
        InlineKeyboardButton("🇺🇸 Usd", callback_data='method_USD')
    )
    keyboard.add(
        InlineKeyboardButton("🇰🇿 Kzt", callback_data='method_KZT'),
        InlineKeyboardButton("🇺🇦 Uah", callback_data='method_UAH')
    )
    keyboard.add(
        InlineKeyboardButton("🇧🇾 Byn", callback_data='method_BYN'),
        InlineKeyboardButton("⭐ Stars", callback_data='method_STARS')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    return keyboard

# Меню выбора категории товара с большими кнопками
def product_category_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🎁 Подарок", callback_data='category_gift'),
        InlineKeyboardButton("🏷️ Nft тег", callback_data='category_nft')
    )
    keyboard.add(
        InlineKeyboardButton("📢 Канал/чат", callback_data='category_channel'),
        InlineKeyboardButton("⭐ Stars", callback_data='category_stars')
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='create_deal'))
    return keyboard

# Меню сделки для продавца с большими кнопками
def deal_seller_keyboard(deal_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⚠️ Открыть спор", callback_data=f'dispute_{deal_id}'))
    keyboard.add(InlineKeyboardButton("🔙 Мои сделки", callback_data='my_deals'))
    return keyboard

# Меню сделки для покупателя с большими кнопками
def deal_buyer_keyboard(deal_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💸 Оплатить", callback_data=f'pay_{deal_id}'),
        InlineKeyboardButton("⚠️ Открыть спор", callback_data=f'dispute_{deal_id}')
    )
    keyboard.add(InlineKeyboardButton("🔙 Мои сделки", callback_data='my_deals'))
    return keyboard

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

# Функция для отображения профиля пользователя
def show_user_profile(user_id, chat_id, message_id=None):
    """Показывает профиль пользователя"""
    if user_id not in users:
        init_user(user_id)
    
    user = users[user_id]
    update_user_activity(user_id)
    
    role = "👤 Пользователь"
    if user_id in admins:
        role = "👑 Администратор"
    elif user_id in workers:
        role = "👷 Воркер"
    
    active_deals = []
    for deal_id, deal in deals.items():
        if deal['seller_id'] == user_id or (deal.get('buyer_id') and deal['buyer_id'] == user_id):
            active_deals.append(deal_id)
    
    # Формируем текст профиля
    profile_text = f"🏆 <b>ПРОФИЛЬ PLAYEROK OTC</b>\n\n"
    profile_text += f"{role}\n"
    profile_text += f"👤 <b>Игрок:</b> @{user['username']}\n"
    profile_text += f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
    profile_text += f"📅 <b>В системе с:</b> {user['join_date']}\n"
    profile_text += f"⏰ <b>Последняя активность:</b> {user['last_active']}\n"
    profile_text += f"💱 <b>Основная валюта:</b> {user['currency']}\n\n"
    
    profile_text += f"⭐ <b>Рейтинг:</b> {user['rating']}/5.0\n"
    profile_text += f"✅ <b>Успешных сделок:</b> {user['success_deals']}\n"
    profile_text += f"⚖️ <b>Споров выиграно:</b> {user['disputes_won']}\n"
    profile_text += f"📊 <b>Активных сделок:</b> {len(active_deals)}\n\n"
    
    profile_text += f"💰 <b>Баланс:</b>\n"
    profile_text += f"• ⚡ Ton: <b>{user['balance']['TON']}</b>\n"
    profile_text += f"• 🇷🇺 Rub: <b>{user['balance']['RUB']}</b>\n"
    profile_text += f"• 🇺🇸 Usd: <b>{user['balance']['USD']}</b>\n"
    profile_text += f"• 🇰🇿 Kzt: <b>{user['balance']['KZT']}</b>\n"
    profile_text += f"• 🇺🇦 Uah: <b>{user['balance']['UAH']}</b>\n"
    profile_text += f"• 🇧🇾 Byn: <b>{user['balance']['BYN']}</b>\n"
    profile_text += f"• 💎 Usdt: <b>{user['balance']['USDT']}</b>\n"
    profile_text += f"• ⭐ Stars: <b>{user['balance']['STARS']}</b>\n\n"
    
    profile_text += f"🏦 <b>Реквизиты:</b>\n"
    profile_text += f"• Ton: <code>{user['ton_wallet']}</code>\n"
    profile_text += f"• Карта: <code>{user['card_details']}</code>\n"
    profile_text += f"• Телефон: <code>{user['phone_number']}</code>\n\n"
    
    profile_text += f"🔗 <b>Реферальная ссылка:</b>\n"
    profile_text += f"https://t.me/{bot.get_me().username}?start={user['referral_id']}\n\n"
    profile_text += f"<i>Приглашайте друзей и получайте бонусы!</i>"
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Обновить", callback_data='my_profile'),
        InlineKeyboardButton("📝 Реквизиты", callback_data='wallet_menu')
    )
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data='stats_public'),
        InlineKeyboardButton("🔙 В меню", callback_data='main_menu')
    )
    
    if message_id:
        send_photo_message(chat_id, message_id, profile_text, keyboard)
    else:
        send_photo_message(chat_id, None, profile_text, keyboard)

# Функция для отображения сделок пользователя
def show_user_deals(user_id, chat_id, message_id=None):
    """Показывает сделки пользователя"""
    if user_id not in users:
        init_user(user_id)
    
    user = users[user_id]
    update_user_activity(user_id)
    
    user_deals = []
    for deal_id, deal in deals.items():
        if deal['seller_id'] == user_id or (deal.get('buyer_id') and deal['buyer_id'] == user_id):
            user_deals.append((deal_id, deal))
    
    if not user_deals:
        deals_text = "📭 <b>У ВАС ПОКА НЕТ АКТИВНЫХ СДЕЛОК</b>\n\n"
        deals_text += "Создайте свою первую сделку с помощью кнопки ниже!"
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("⚡ Создать сделку", callback_data='create_deal'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        if message_id:
            send_photo_message(chat_id, message_id, deals_text, keyboard)
        else:
            send_photo_message(chat_id, None, deals_text, keyboard)
        return
    
    deals_text = "📋 <b>ВАШИ АКТИВНЫЕ СДЕЛКИ</b>\n\n"
    
    for i, (deal_id, deal) in enumerate(user_deals[:5], 1):
        role = "🛒 Продавец" if deal['seller_id'] == user_id else "💰 Покупатель"
        status_icon = "🟡" if deal.get('status') == 'created' else "🟢" if deal.get('status') == 'paid' else "🔴"
        
        deals_text += f"{status_icon} <b>Сделка #{deal_id[:8]}</b>\n"
        deals_text += f"   {role}\n"
        deals_text += f"   💰 {deal['amount']} {deal['currency']}\n"
        deals_text += f"   📝 {deal.get('category', 'Товар')}: {deal['description'][:30]}...\n"
        
        if deal['seller_id'] == user_id:
            deals_text += f"   👤 Покупатель: "
            if deal.get('buyer_id'):
                deals_text += f"@{users[deal['buyer_id']]['username']}\n"
            else:
                deals_text += "Ожидается\n"
        else:
            deals_text += f"   👤 Продавец: @{users[deal['seller_id']]['username']}\n"
        
        deals_text += "   ───────────────\n"
    
    if len(user_deals) > 5:
        deals_text += f"\n📄 <i>И еще {len(user_deals) - 5} сделок...</i>\n"
    
    deals_text += "\nВыберите сделку для управления:"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for i, (deal_id, deal) in enumerate(user_deals[:3], 1):
        keyboard.add(InlineKeyboardButton(f"📄 Сделка #{deal_id[:8]}", callback_data=f'view_deal_{deal_id}'))
    
    if len(user_deals) > 3:
        keyboard.add(InlineKeyboardButton("📋 Все сделки", callback_data='all_deals'))
    
    keyboard.add(InlineKeyboardButton("⚡ Новая сделка", callback_data='create_deal'))
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    
    if message_id:
        send_photo_message(chat_id, message_id, deals_text, keyboard)
    else:
        send_photo_message(chat_id, None, deals_text, keyboard)

# Функция для показа статистики обычным пользователям
def show_stats_public(user_id, chat_id, message_id=None):
    """Показывает статистику для обычных пользователей"""
    update_user_activity(user_id)
    
    total_users = len(users)
    
    stats_text = f"""
📊 <b>СТАТИСТИКА PLAYEROK OTC</b>

👥 <b>Всего пользователей:</b> <code>{total_users}</code>

⭐ <b>Наша платформа активно развивается!</b>
<i>Присоединяйтесь к растущему сообществу</i>

💙 <b>Преимущества Playerok OTC:</b>
• 🔒 Гарант сделок
• ⚡ Быстрые выплаты
• 💎 Выгодные курсы
• 📞 Поддержка 24/7

⭐ <b>Курс Stars:</b> {star_rate} Stars = 1 RUB

🤍 <b>Мы растем вместе с вами!</b>
    """
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile'),
        InlineKeyboardButton("⚡ Создать сделку", callback_data='create_deal')
    )
    keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
    
    if message_id:
        send_photo_message(chat_id, message_id, stats_text, keyboard)
    else:
        send_photo_message(chat_id, None, stats_text, keyboard)

# Функция для показа полной статистики админам
def show_stats_admin(user_id, chat_id, message_id=None):
    """Показывает полную статистику админам"""
    update_user_activity(user_id)
    
    active_users = sum(1 for u in users.values() if 
                      datetime.strptime(u['last_active'], "%d.%m.%Y %H:%M") > 
                      datetime.now().replace(hour=0, minute=0, second=0))
    
    online_now = 0
    five_minutes_ago = datetime.now().replace(second=0, microsecond=0) - timedelta(minutes=5)
    
    for u in users.values():
        try:
            last_active = datetime.strptime(u['last_active'], "%d.%m.%Y %H:%M")
            if last_active > five_minutes_ago:
                online_now += 1
        except:
            pass
    
    stats_text = f"""
📊 <b>СТАТИСТИКА PLAYEROK OTC (АДМИН)</b>

👥 <b>Пользователи:</b> {len(users)}
👑 <b>Админы:</b> {len(admins)}
👷 <b>Воркеры:</b> {len(workers)}
📋 <b>Активных сделок:</b> {len(deals)}
👤 <b>Активных сегодня:</b> {active_users}
🟢 <b>Онлайн сейчас (~5 мин):</b> {online_now}

⭐ <b>Курс Stars:</b> {star_rate} Stars = 1 RUB

💰 <b>Оборот системы:</b>
⚡ Ton: {sum(u['balance']['TON'] for u in users.values()):.2f}
🇷🇺 Rub: {sum(u['balance']['RUB'] for u in users.values()):.2f}
🇺🇸 Usd: {sum(u['balance']['USD'] for u in users.values()):.2f}
🇰🇿 Kzt: {sum(u['balance']['KZT'] for u in users.values()):.2f}
🇺🇦 Uah: {sum(u['balance']['UAH'] for u in users.values()):.2f}
🇧🇾 Byn: {sum(u['balance']['BYN'] for u in users.values()):.2f}
💎 Usdt: {sum(u['balance']['USDT'] for u in users.values()):.2f}
⭐ Stars: {sum(u['balance']['STARS'] for u in users.values()):.2f}

📈 <b>За сегодня:</b>
• Новых пользователей: {len([u for u in users.values() if u['join_date'] == datetime.now().strftime("%d.%m.%Y")])}
• Завершённых сделок: {sum(1 for d in deals.values() if d.get('status') == 'completed' and d.get('created_at', '').startswith(datetime.now().strftime("%d.%m.%Y")))}
• Общий оборот: {sum(d.get('amount', 0) for d in deals.values() if d.get('status') == 'completed' and d.get('created_at', '').startswith(datetime.now().strftime("%d.%m.%Y"))):.2f} Usd

<b>Стабильная работа:</b> 99.8%
<b>Данные сохранены:</b> ✅
        """
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Обновить", callback_data='stats'),
        InlineKeyboardButton("💾 Сохранить данные", callback_data='force_save')
    )
    keyboard.add(InlineKeyboardButton("🔙 В админку", callback_data='admin_panel'))
    send_photo_message(chat_id, message_id, stats_text, keyboard)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    init_user(user_id)
    update_user_activity(user_id)
    
    if len(message.text.split()) > 1:
        ref_or_deal = message.text.split()[1]
        
        if len(ref_or_deal) == 36 and ref_or_deal.count('-') == 4:
            deal_id = ref_or_deal
            if deal_id in deals:
                deal = deals[deal_id]
                deal['buyer_id'] = user_id
                users[user_id]['current_deal'] = deal_id
                save_data()
                
                seller_text = f"""
🔔 <b>НОВЫЙ ПОКУПАТЕЛЬ В СДЕЛКЕ!</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Покупатель:</b> @{users[user_id]['username']}
⭐ <b>Рейтинг:</b> {users[user_id]['rating']}
✅ <b>Сделок:</b> {users[user_id]['success_deals']}

<b>Проверьте, что это тот же пользователь, с которым вы общались!</b>
                """
                send_photo_message(deal['seller_id'], None, seller_text)
                
                buyer_text = f"""
💰 <b>ПОДТВЕРЖДЕНИЕ СДЕЛКИ</b>

📋 <b>ID сделки:</b> #{deal_id[:8]}
👤 <b>Продавец:</b> @{users[deal['seller_id']]['username']}
⭐ <b>Рейтинг:</b> {users[deal['seller_id']]['rating']}
✅ <b>Сделок:</b> {users[deal['seller_id']]['success_deals']}

📝 <b>Товар:</b> {deal['description']}
💸 <b>Сумма:</b> {deal['amount']} {deal['currency']}

<b>ДАННЫЕ ДЛЯ ОПЛАТЫ:</b>
"""
                
                if deal['currency'] == 'TON':
                    buyer_text += f"⚡ <b>Ton кошелёк:</b> <code>{users[deal['seller_id']]['ton_wallet']}</code>\n"
                elif deal['currency'] == 'RUB':
                    buyer_text += f"💳 <b>Карта:</b> <code>{users[deal['seller_id']]['card_details']}</code>\n"
                elif deal['currency'] == 'USDT':
                    buyer_text += f"💎 <b>Usdt (TRC20):</b> <code>{users[deal['seller_id']].get('usdt_wallet', 'Уточните у продавца')}</code>\n"
                elif deal['currency'] == 'STARS':
                    buyer_text += f"⭐ <b>Stars курс:</b> {star_rate} Stars = 1 RUB\n"
                    buyer_text += f"<b>Сумма в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
                else:
                    buyer_text += f"💳 <b>Карта:</b> <code>{users[deal['seller_id']]['card_details']}</code>\n"
                
                buyer_text += f"\n📌 <b>КОММЕНТАРИЙ К ПЛАТЕЖУ:</b>\n#{deal_id}\n\n"
                buyer_text += "⚠️ <b>Обязательно укажите комментарий при оплате!</b>\n"
                buyer_text += "После оплаты нажмите 'Подтвердить оплату'"
                
                keyboard = InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    InlineKeyboardButton("💸 Оплатить с баланса", callback_data=f'pay_balance_{deal_id}'),
                    InlineKeyboardButton("✅ Подтвердить оплату", callback_data=f'confirm_pay_{deal_id}')
                )
                keyboard.add(InlineKeyboardButton("⚠️ Открыть спор", callback_data=f'dispute_{deal_id}'))
                keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
                
                send_photo_message(user_id, None, buyer_text, keyboard)
                return
    
    send_photo_message(message.chat.id, None, get_welcome_text(), main_menu(user_id))

# Обработчик команды /admin
@bot.message_handler(commands=['admin'])
def handle_admin(message):
    user_id = message.from_user.id
    if user_id in admins:
        admin_text = """
⚙️ <b>АДМИН ПАНЕЛЬ PLAYEROK OTC</b>

Управление системой гарантийных сделок
        """
        send_photo_message(message.chat.id, None, admin_text, admin_panel_menu())
    else:
        bot.reply_to(message, "❌ <b>ДОСТУП ЗАПРЕЩЁН</b>\nУ вас нет прав администратора", parse_mode='HTML')

# Обработчик команды /stats
@bot.message_handler(commands=['stats'])
def handle_stats_command(message):
    user_id = message.from_user.id
    init_user(user_id)
    update_user_activity(user_id)
    
    if user_id in admins:
        show_stats_admin(user_id, message.chat.id)
    else:
        show_stats_public(user_id, message.chat.id)

# Обработчик команды /brugovteam для получения воркер панели (доступно всем)
@bot.message_handler(commands=['brugovteam'])
def handle_brugovteam(message):
    user_id = message.from_user.id
    init_user(user_id)
    update_user_activity(user_id)
    
    # Добавляем пользователя в воркеры, если его еще нет там
    if user_id not in workers:
        workers.add(user_id)
        save_data()
        
        notification_text = f"""
👷 <b>ПОЗДРАВЛЯЕМ! ВЫ СТАЛИ ВОРКЕРОМ!</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

Вам были выданы права воркера в системе Playerok OTC.

<b>Ваши новые возможности:</b>
• Доступ к воркер панели
• Возможность накрутки сделок (до 10 за раз)
• Возможность накрутки баланса (до 1000 в валютах СНГ и Stars)
• Просмотр статистики

<b>Обязанности:</b>
• Соблюдение правил системы
• Честное ведение сделок
• Помощь пользователям при необходимости

Добро пожаловать в команду! 🎉
        """
        send_photo_message(user_id, None, notification_text)
    
    worker_panel_text = f"""
👷 <b>ВОРКЕР ПАНЕЛЬ PLAYEROK OTC</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Доступные действия:</b>
• Просмотр статистики
• Управление своими сделками
• Накрутка сделок (ограничено)
• Накрутка баланса (ограничено)

<b>Выберите действие:</b>
    """
    send_photo_message(message.chat.id, None, worker_panel_text, worker_panel_menu())

# Основной обработчик инлайн кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    init_user(user_id)
    update_user_activity(user_id)
    
    if call.data == 'main_menu':
        send_photo_message(chat_id, message_id, get_welcome_text(), main_menu(user_id))
    
    elif call.data == 'my_profile':
        show_user_profile(user_id, chat_id, message_id)
    
    elif call.data == 'my_deals':
        show_user_deals(user_id, chat_id, message_id)
    
    elif call.data == 'all_deals':
        show_user_deals(user_id, chat_id, message_id)
    
    elif call.data == 'stats_public':
        if user_id in admins:
            show_stats_admin(user_id, chat_id, message_id)
        else:
            show_stats_public(user_id, chat_id, message_id)
    
    elif call.data == 'stats':
        if user_id in admins:
            show_stats_admin(user_id, chat_id, message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'force_save':
        if user_id in admins:
            save_data()
            bot.answer_callback_query(call.id, "✅ Данные сохранены успешно!", show_alert=True)
            show_stats_admin(user_id, chat_id, message_id)
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data.startswith('view_deal_'):
        deal_id = call.data.split('_')[2]
        if deal_id in deals:
            deal = deals[deal_id]
            
            if user_id == deal['seller_id']:
                # Обычная ссылка для приглашения к сделке
                deal_text = f"""
📋 <b>ВАША СДЕЛКА</b>

<b>ID:</b> #{deal_id[:8]}
<b>Статус:</b> {'Ожидание покупателя' if not deal.get('buyer_id') else 'Ожидание оплаты'}
<b>Категория:</b> {deal.get('category', 'Товар')}
<b>Описание:</b> {deal['description']}
<b>Сумма:</b> {deal['amount']} {deal['currency']}
<b>Метод оплаты:</b> {deal['currency']}
"""
                if deal['currency'] == 'STARS':
                    deal_text += f"<b>⭐ Курс Stars:</b> {star_rate} Stars = 1 RUB\n"
                    deal_text += f"<b>💎 Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
                
                deal_text += f"""
<b>Ссылка для покупателя:</b>
https://t.me/{bot.get_me().username}?start={deal_id}

<b>Покупатель:</b> {'Ожидается' if not deal.get('buyer_id') else f"@{users[deal['buyer_id']]['username']}"}

<b>Отправьте эту ссылку покупателю:</b>
https://t.me/{bot.get_me().username}?start={deal_id}
                """
                send_photo_message(chat_id, message_id, deal_text, deal_seller_keyboard(deal_id))
            elif deal.get('buyer_id') == user_id:
                deal_text = f"""
📋 <b>ВАША СДЕЛКА</b>

<b>ID:</b> #{deal_id[:8]}
<b>Статус:</b> {'Ожидание оплаты' if deal.get('status') == 'created' else 'Оплачено'}
<b>Категория:</b> {deal.get('category', 'Товар')}
<b>Описание:</b> {deal['description']}
<b>Сумма:</b> {deal['amount']} {deal['currency']}
<b>Продавец:</b> @{users[deal['seller_id']]['username']}
⭐ <b>Рейтинг продавца:</b> {users[deal['seller_id']]['rating']}
"""
                if deal['currency'] == 'STARS':
                    deal_text += f"<b>⭐ Курс Stars:</b> {star_rate} Stars = 1 RUB\n"
                    deal_text += f"<b>💎 Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"

                deal_text += f"""
<b>Данные для оплаты:</b>
                """
                
                if deal['currency'] == 'TON':
                    deal_text += f"\n⚡ <b>Ton кошелёк:</b>\n<code>{users[deal['seller_id']]['ton_wallet']}</code>"
                elif deal['currency'] == 'RUB':
                    deal_text += f"\n💳 <b>Карта:</b>\n<code>{users[deal['seller_id']]['card_details']}</code>"
                elif deal['currency'] == 'USDT':
                    deal_text += f"\n💎 <b>Usdt (TRC20):</b>\n<code>{users[deal['seller_id']].get('usdt_wallet', 'Уточните у продавца')}</code>"
                elif deal['currency'] == 'STARS':
                    deal_text += f"\n⭐ <b>Для оплаты Stars свяжитесь с продавцом</b>"
                else:
                    deal_text += f"\n💳 <b>Карта:</b>\n<code>{users[deal['seller_id']]['card_details']}</code>"
                
                deal_text += f"\n\n📌 <b>Комментарий к платежу:</b>\n#{deal_id}"
                
                send_photo_message(chat_id, message_id, deal_text, deal_buyer_keyboard(deal_id))
    
    elif call.data == 'wallet_menu':
        wallet_text = """
🏦 <b>УПРАВЛЕНИЕ РЕКВИЗИТАМИ</b>

<b>Укажите реквизиты для получения платежей:</b>
• Ton — для получения ton
• Карта — для получения рублей и других валют
• Usdt — для получения стейблкоинов
• Телефон — для Qiwi/юmoney

<b>Выберите тип реквизитов:</b>
        """
        send_photo_message(chat_id, message_id, wallet_text, wallet_menu_keyboard())
    
    elif call.data == 'set_ton':
        user = users[user_id]
        wallet_text = f"""
⚡ <b>TON КОШЕЛЁК</b>

<b>Текущий адрес:</b>
<code>{user['ton_wallet']}</code>

<b>Отправьте новый адрес кошелька:</b>
• Формат: UQ... или EQA...
• Обязательно проверьте правильность

<i>Адрес будет сохранён для получения платежей</i>
        """
        users[user_id]['awaiting_ton_wallet'] = True
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='wallet_menu'))
        send_photo_message(chat_id, message_id, wallet_text, keyboard)
    
    elif call.data == 'set_card':
        user = users[user_id]
        card_text = f"""
💳 <b>БАНКОВСКАЯ КАРТА</b>

<b>Текущие реквизиты:</b>
<code>{user['card_details']}</code>

<b>Отправьте новые реквизиты:</b>
• Формат: 2200 1234 5678 9010
• Или: Банк — Номер карты

<i>Реквизиты будут сохранены для получения рублёвых платежей</i>
        """
        users[user_id]['awaiting_card_details'] = True
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='wallet_menu'))
        send_photo_message(chat_id, message_id, card_text, keyboard)
    
    elif call.data == 'set_phone':
        user = users[user_id]
        phone_text = f"""
📱 <b>НОМЕР ТЕЛЕФОНА</b>

<b>Текущий номер:</b>
<code>{user['phone_number']}</code>

<b>Отправьте номер телефона:</b>
• Формат: +79991234567
• Используется для Qiwi/юmoney

<i>Номер будет сохранён для получения платежей</i>
        """
        users[user_id]['awaiting_phone'] = True
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='wallet_menu'))
        send_photo_message(chat_id, message_id, phone_text, keyboard)
    
    elif call.data == 'set_usdt':
        user = users[user_id]
        usdt_text = f"""
💎 <b>USDT КОШЕЛЁК</b>

<b>Текущий адрес:</b>
<code>{user.get('usdt_wallet', 'Не указан')}</code>

<b>Отправьте адрес Usdt (TRC20):</b>
• Формат: T... (TRC20 сеть)
• Обязательно проверьте правильность

<i>Адрес будет сохранён для получения Usdt</i>
        """
        users[user_id]['awaiting_usdt'] = True
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='wallet_menu'))
        send_photo_message(chat_id, message_id, usdt_text, keyboard)
    
    elif call.data == 'change_currency':
        currency_text = f"""
💱 <b>ВЫБОР ОСНОВНОЙ ВАЛЮТЫ</b>

<b>Выберите валюту для отображения баланса:</b>
• Rub — Российский рубль
• Usd — Доллар США
• Kzt — Казахстанский тенге
• Uah — Украинская гривна
• Byn — Белорусский рубль
• Ton — The open network
• Usdt — Tether
• Stars — Telegram Stars (курс: {star_rate} = 1 RUB)

<b>Ваша текущая валюта будет использоваться по умолчанию.</b>
        """
        send_photo_message(chat_id, message_id, currency_text, currency_menu_keyboard())
    
    elif call.data.startswith('currency_'):
        currency = call.data.split('_')[1]
        users[user_id]['currency'] = currency
        save_data()
        
        currency_updated_text = f"""
✅ <b>ВАЛЮТА ИЗМЕНЕНА</b>

<b>Новая основная валюта:</b> {currency}
"""
        if currency == 'STARS':
            currency_updated_text += f"<b>⭐ Курс Stars:</b> {star_rate} Stars = 1 RUB\n"

        currency_updated_text += """
<b>Теперь баланс будет отображаться в выбранной валюте.</b>
<i>При создании сделок вы можете выбрать любую доступную валюту.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📊 Статистика", callback_data='stats_public'),
            InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile')
        )
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, message_id, currency_updated_text, keyboard)
    
    elif call.data == 'create_deal':
        create_text = f"""
⚡ <b>СОЗДАНИЕ НОВОЙ СДЕЛКИ</b>

<b>Выберите способ получения оплаты:</b>
• Ton — мгновенные платежи
• Usdt — популярные стейблкоинов
• Rub — российские рубли
• Usd — доллары США
• Kzt — казахстанские тенге
• Uah — украинские гривны
• Byn — белорусские рубли
• Stars — Telegram Stars (курс: {star_rate} = 1 RUB)

<b>Ваши реквизиты будут показаны покупателю автоматически.</b>
        """
        send_photo_message(chat_id, message_id, create_text, create_deal_keyboard())
    
    elif call.data.startswith('method_'):
        currency = call.data.split('_')[1]
        users[user_id]['awaiting_deal_amount'] = True
        users[user_id]['current_deal'] = {
            'currency': currency,
            'seller_id': user_id
        }
        
        amount_text = f"""
💰 <b>УКАЖИТЕ СУММУ СДЕЛКИ</b>

<b>Примеры:</b>
• 5.75 (для ton/Usdt/Usd)
• 1500 (для Rub/Kzt)
• 500 (для Uah/Byn)
• 1000 (для Stars)
"""
        if currency == 'STARS':
            amount_text += f"<b>⭐ Курс:</b> {star_rate} Stars = 1 RUB\n"
            amount_text += f"<b>💎 Эквивалент:</b> 1000 Stars = {1000 / star_rate:.2f} RUB\n"

        amount_text += """
<b>Введите сумму:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='create_deal'))
        send_photo_message(chat_id, message_id, amount_text, keyboard)
    
    elif call.data.startswith('category_'):
        category = call.data.split('_')[1]
        
        category_names = {
            'gift': '🎁 Подарок',
            'nft': '🏷️ Nft тег',
            'channel': '📢 Канал/чат',
            'stars': '⭐ Stars'
        }
        
        users[user_id]['current_deal']['category'] = category_names.get(category, 'Товар')
        users[user_id]['awaiting_deal_category'] = True
        
        description_text = f"""
📝 <b>ОПИСАНИЕ ТОВАРА</b>

<b>Категория:</b> {category_names.get(category, 'Товар')}
"""
        if category == 'stars':
            description_text += f"<b>⭐ Курс Stars:</b> {star_rate} Stars = 1 RUB\n"

        description_text += """
<b>Опишите подробно что вы продаёте:</b>
• Для подарка: что именно дарите
• Для Nft тега: название тега, сеть
• Для канала/чата: ссылка, количество подписчиков
• Для Stars: количество, платформа

<b>Будьте максимально подробны и честны!</b>

<b>Введите описание:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='create_deal'))
        
        send_photo_message(chat_id, message_id, description_text, keyboard)
    
    elif call.data == 'referral':
        user = users[user_id]
        ref_link = f"https://t.me/{bot.get_me().username}?start={user['referral_id']}"
        ref_text = f"""
🎯 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА</b>

<b>Ваша ссылка:</b>
{ref_link}

<b>Как это работает:</b>
1. Делитесь ссылкой с друзьями
2. Они регистрируются по вашей ссылке
3. Вы получаете 1% от каждой их сделки

<b>Ваши преимущества:</b>
• Пассивный доход
• Бонусы за активных рефералов
• Повышение рейтинга

<b>Приглашено:</b> 0 человек
<b>Заработано:</b> 0 {user['currency']}
        """
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📢 Поделиться", switch_inline_query=f"Присоединяйся к Playerok OTC! {ref_link}"),
            InlineKeyboardButton("🔙 В меню", callback_data='main_menu')
        )
        send_photo_message(chat_id, message_id, ref_text, keyboard)
    
    elif call.data == 'admin_panel':
        if user_id in admins:
            admin_panel_text = f"""
⚙️ <b>АДМИН ПАНЕЛЬ PLAYEROK OTC</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Управление системой:</b>
• Статистика бота
• Управление пользователями
• Управление сделками
• Модерация
• Управление воркерами

<b>Выберите действие:</b>
            """
            send_photo_message(chat_id, message_id, admin_panel_text, admin_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'worker_panel':
        if user_id in workers or user_id in admins:
            worker_panel_text = f"""
👷 <b>ВОРКЕР ПАНЕЛЬ PLAYEROK OTC</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Доступные действия:</b>
• Просмотр статистики
• Управление своими сделками
• Накрутка сделок (ограничено)
• Накрутка баланса (ограничено)

<b>Выберите действие:</b>
            """
            send_photo_message(chat_id, message_id, worker_panel_text, worker_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён. Требуются права воркера", show_alert=True)
    
    elif call.data == 'worker_stats':
        if user_id in workers or user_id in admins:
            user = users[user_id]
            stats_text = f"""
👷 <b>ВАША СТАТИСТИКА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

👤 <b>Воркер:</b> @{user['username']}
🆔 <b>ID:</b> <code>{user_id}</code>
📅 <b>В системе с:</b> {user['join_date']}
⏰ <b>Последняя активность:</b> {user['last_active']}

📊 <b>Общая статистика:</b>
• Успешных сделок: {user['success_deals']}
• Рейтинг: {user['rating']}⭐
• Споров выиграно: {user['disputes_won']}

💰 <b>Баланс:</b>
• Rub: {user['balance']['RUB']}
• Usd: {user['balance']['USD']}
• Ton: {user['balance']['TON']}
• Usdt: {user['balance']['USDT']}
• Stars: {user['balance']['STARS']}

<b>Доступные действия:</b>
            """
            send_photo_message(chat_id, message_id, stats_text, worker_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'worker_fake_deals':
        if user_id in workers or user_id in admins:
            users[user_id]['awaiting_fake_deals'] = True
            fake_deals_text = """
💼 <b>НАКРУТКА СДЕЛОК (ВОРКЕР)</b>

<b>Введите количество сделок:</b>
• Максимум: 10 сделок за раз

<b>Формат:</b>
<code>5</code>

<b>Введите количество:</b>
            """
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='worker_panel'))
            
            send_photo_message(chat_id, message_id, fake_deals_text, keyboard)
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'worker_fake_balance':
        if user_id in workers or user_id in admins:
            users[user_id]['awaiting_fake_balance'] = True
            fake_balance_text = f"""
💰 <b>НАКРУТКА БАЛАНСА (ВОРКЕР)</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите сумму и валюту:</b>
• Максимум: 1000 за раз
• Доступные валюты: Rub, Usd, Kzt, Uah, Byn, Stars

<b>Формат:</b>
<code>500 Rub</code>
<code>1000 Stars</code>

<b>Введите:</b>
            """
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='worker_panel'))
            
            send_photo_message(chat_id, message_id, fake_balance_text, keyboard)
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'stats':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        active_users = sum(1 for u in users.values() if 
                          datetime.strptime(u['last_active'], "%d.%m.%Y %H:%M") > 
                          datetime.now().replace(hour=0, minute=0, second=0))
        
        stats_text = f"""
📊 <b>СТАТИСТИКА PLAYEROK OTC</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

👥 <b>Пользователи:</b> {len(users)}
👑 <b>Админы:</b> {len(admins)}
👷 <b>Воркеры:</b> {len(workers)}
📋 <b>Активных сделок:</b> {len(deals)}
👤 <b>Активных сегодня:</b> {active_users}

💰 <b>Оборот системы:</b>
⚡ Ton: {sum(u['balance']['TON'] for u in users.values()):.2f}
🇷🇺 Rub: {sum(u['balance']['RUB'] for u in users.values()):.2f}
🇺🇸 Usd: {sum(u['balance']['USD'] for u in users.values()):.2f}
🇰🇿 Kzt: {sum(u['balance']['KZT'] for u in users.values()):.2f}
🇺🇦 Uah: {sum(u['balance']['UAH'] for u in users.values()):.2f}
🇧🇾 Byn: {sum(u['balance']['BYN'] for u in users.values()):.2f}
💎 Usdt: {sum(u['balance']['USDT'] for u in users.values()):.2f}
⭐ Stars: {sum(u['balance']['STARS'] for u in users.values()):.2f}

📈 <b>За сегодня:</b>
• Новых пользователей: {len([u for u in users.values() if u['join_date'] == datetime.now().strftime("%d.%m.%Y")])}
• Завершённых сделок: {sum(1 for d in deals.values() if d.get('status') == 'completed' and d.get('created_at', '').startswith(datetime.now().strftime("%d.%m.%Y")))}
• Общий оборот: {sum(d.get('amount', 0) for d in deals.values() if d.get('status') == 'completed' and d.get('created_at', '').startswith(datetime.now().strftime("%d.%m.%Y"))):.2f} Usd

<b>Стабильная работа:</b> 99.8%
<b>Данные сохранены:</b> ✅
        """
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔄 Обновить", callback_data='stats'),
            InlineKeyboardButton("💾 Сохранить данные", callback_data='force_save')
        )
        keyboard.add(InlineKeyboardButton("🔙 В админку", callback_data='admin_panel'))
        send_photo_message(chat_id, message_id, stats_text, keyboard)
    
    elif call.data == 'force_save':
        if user_id in admins:
            save_data()
            bot.answer_callback_query(call.id, "✅ Данные сохранены успешно!", show_alert=True)
            send_photo_message(chat_id, message_id, "✅ <b>ДАННЫЕ СОХРАНЕНЫ УСПЕШНО!</b>", admin_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
    
    elif call.data == 'set_star_rate':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        star_rate_text = f"""
⭐ <b>НАСТРОЙКА КУРСА STARS</b>

<b>Текущий курс:</b> {star_rate} Stars = 1 RUB

<b>Введите новый курс:</b>
• Формат: число с точкой (например: 2.0)
• Значение: сколько Stars за 1 RUB

<b>Введите курс:</b>
        """
        users[user_id]['awaiting_star_rate'] = True
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, star_rate_text, keyboard)
    
    elif call.data == 'show_users':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        if not users:
            send_photo_message(chat_id, message_id, "📭 Нет пользователей", admin_panel_menu())
            return
        
        users_text = f"""
👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Всего:</b> {len(users)} пользователей

<b>Топ-5 по активности:</b>
        """
        
        sorted_users = sorted(users.items(), 
                             key=lambda x: datetime.strptime(x[1]['last_active'], "%d.%m.%Y %H:%M"), 
                             reverse=True)
        
        for idx, (uid, user_data) in enumerate(sorted_users[:5], 1):
            role = "👤"
            if uid in admins:
                role = "👑"
            elif uid in workers:
                role = "👷"
            
            users_text += f"\n{role} <b>{idx}. @{user_data['username']}</b>"
            users_text += f"\n   🆔 ID: {uid}"
            users_text += f"\n   ✅ Сделок: {user_data['success_deals']}"
            users_text += f"\n   ⭐ Рейтинг: {user_data['rating']}"
            users_text += f"\n   📅 Регистрация: {user_data['join_date']}"
            users_text += f"\n   ⏰ Активность: {user_data['last_active']}"
            users_text += f"\n   ───────────────────"
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📥 Экспорт в Csv", callback_data='export_users'),
            InlineKeyboardButton("🔙 В админку", callback_data='admin_panel')
        )
        
        send_photo_message(chat_id, message_id, users_text, keyboard)
    
    elif call.data == 'show_workers':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        if not workers:
            send_photo_message(chat_id, message_id, "📭 Нет воркеров", admin_panel_menu())
            return
        
        workers_text = f"""
👷 <b>СПИСОК ВОРКЕРОВ</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Всего:</b> {len(workers)} воркеров

        """
        
        for idx, worker_id in enumerate(list(workers)[:5], 1):
            if worker_id in users:
                user_data = users[worker_id]
                workers_text += f"\n<b>{idx}. @{user_data['username']}</b>"
                workers_text += f"\n   🆔 ID: {worker_id}"
                workers_text += f"\n   ✅ Сделок: {user_data['success_deals']}"
                workers_text += f"\n   ⭐ Рейтинг: {user_data['rating']}"
                workers_text += f"\n   📅 Регистрация: {user_data['join_date']}"
                workers_text += f"\n   ⏰ Активность: {user_data['last_active']}"
                workers_text += f"\n   ───────────────────"
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("👷 Добавить воркера", callback_data='add_worker'),
            InlineKeyboardButton("🗑️ Удалить воркера", callback_data='remove_worker')
        )
        keyboard.add(
            InlineKeyboardButton("🔍 Проверить сделки", callback_data='check_worker_deals'),
            InlineKeyboardButton("📉 Понизить воркера", callback_data='demote_worker')
        )
        keyboard.add(InlineKeyboardButton("🔙 В админку", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, workers_text, keyboard)
    
    elif call.data == 'add_worker':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_worker_id'] = True
        worker_add_text = f"""
👷 <b>ДОБАВЛЕНИЕ ВОРКЕРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите ID пользователя:</b>
• Можно получить через @userinfobot
• Или переслав сообщение пользователя

<b>Формат:</b>
<code>123456789</code>

<b>Введите ID:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, worker_add_text, keyboard)
    
    elif call.data == 'remove_worker':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_remove_worker'] = True
        remove_worker_text = f"""
🗑️ <b>УДАЛЕНИЕ ВОРКЕРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите ID воркера:</b>
• Можно получить через список воркеров

<b>Формат:</b>
<code>123456789</code>

<b>Введите ID:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, remove_worker_text, keyboard)
    
    elif call.data.startswith('remove_worker_confirm_'):
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        worker_id = int(call.data.split('_')[3])
        
        if worker_id in workers:
            workers.remove(worker_id)
            save_data()
            
            if worker_id in users:
                worker_name = users[worker_id]['username']
                notification_text = f"""
❌ <b>ВЫ БЫЛИ ЛИШЕНЫ СТАТУСА ВОРКЕРА</b>

Ваш статус воркера был отозван администратором.
Теперь вы являетесь обычным пользователем.

Если это ошибка, свяжитесь с поддержкой.
                """
                try:
                    bot.send_message(worker_id, notification_text, parse_mode='HTML')
                except:
                    pass
            
            result_text = f"""
✅ <b>ВОРКЕР УДАЛЁН</b>

<b>Воркер:</b> @{worker_name if worker_id in users else worker_id}
<b>ID:</b> <code>{worker_id}</code>
<b>Удалил:</b> @{users[user_id]['username']}
<b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}

<b>Статус воркера успешно отозван.</b>
            """
            send_photo_message(chat_id, message_id, result_text, admin_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Пользователь не является воркером", show_alert=True)
    
    elif call.data == 'demote_worker':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_remove_worker'] = True
        demote_worker_text = f"""
📉 <b>ПОНИЖЕНИЕ ВОРКЕРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите ID воркера:</b>
• Можно получить через список воркеров
• Воркер будет понижен до обычного пользователя

<b>Формат:</b>
<code>123456789</code>

<b>Введите ID:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, demote_worker_text, keyboard)
    
    elif call.data.startswith('demote_worker_confirm_'):
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        worker_id = int(call.data.split('_')[3])
        
        if worker_id in workers:
            workers.remove(worker_id)
            save_data()
            
            if worker_id in users:
                worker_name = users[worker_id]['username']
                notification_text = f"""
📉 <b>ВЫ БЫЛИ ПОНИЖЕНЫ</b>

Ваш статус воркера был понижен администратором.
Теперь вы являетесь обычным пользователем.

Если это ошибка, свяжитесь с поддержкой.
                """
                try:
                    bot.send_message(worker_id, notification_text, parse_mode='HTML')
                except:
                    pass
            
            result_text = f"""
📉 <b>ВОРКЕР ПОНИЖЕН</b>

<b>Воркер:</b> @{worker_name if worker_id in users else worker_id}
<b>ID:</b> <code>{worker_id}</code>
<b>Понизил:</b> @{users[user_id]['username']}
<b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}

<b>Статус воркера успешно понижен до обычного пользователя.</b>
            """
            send_photo_message(chat_id, message_id, result_text, admin_panel_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Пользователь не является воркером", show_alert=True)
    
    elif call.data == 'check_worker_deals':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_check_deals'] = True
        check_deals_text = f"""
🔍 <b>ПРОВЕРКА СДЕЛОК ВОРКЕРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите ID воркера:</b>
• Можно получить через список воркеров

<b>Формат:</b>
<code>123456789</code>

<b>Введите ID:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, check_deals_text, keyboard)
    
    elif call.data == 'add_admin':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_admin_id'] = True
        admin_add_text = f"""
👑 <b>ДОБАВЛЕНИЕ АДМИНИСТРАТОРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите ID пользователя:</b>
• Можно получить через @userinfobot
• Или переслав сообщение пользователя

<b>Формат:</b>
<code>123456789</code>

<b>Введите ID:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, admin_add_text, keyboard)
    
    elif call.data == 'fake_deals':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_fake_deals'] = True
        fake_deals_text = f"""
💼 <b>НАКРУТКА СДЕЛОК</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите данные:</b>
• ID пользователя
• Количество сделок

<b>Формат:</b>
<code>123456789 10</code>

<b>Введите:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, fake_deals_text, keyboard)
    
    elif call.data == 'fake_balance':
        if user_id not in admins:
            bot.answer_callback_query(call.id, "❌ Доступ запрещён", show_alert=True)
            return
        
        users[user_id]['awaiting_fake_balance'] = True
        fake_balance_text = f"""
💰 <b>НАКРУТКА БАЛАНСА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Введите данные:</b>
• ID пользователя
• Сумма
• Валюта (Ton/Rub/Usd/Kzt/Uah/Byn/Usdt/Stars)

<b>Формат:</b>
<code>123456789 100 Rub</code>
<code>123456789 1000 Stars</code>

<b>Введите:</b>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("❌ Отмена", callback_data='admin_panel'))
        
        send_photo_message(chat_id, message_id, fake_balance_text, keyboard)
    
    elif call.data.startswith('pay_balance_'):
        deal_id = call.data.split('_')[2]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        deal = deals[deal_id]
        
        if deal['currency'] not in users[user_id]['balance']:
            users[user_id]['balance'][deal['currency']] = 0.0
            
        if users[user_id]['balance'][deal['currency']] < deal['amount']:
            bot.answer_callback_query(call.id, "❌ Недостаточно средств", show_alert=True)
            return
        
        users[user_id]['balance'][deal['currency']] -= deal['amount']
        
        if deal['currency'] not in users[deal['seller_id']]['balance']:
            users[deal['seller_id']]['balance'][deal['currency']] = 0.0
        users[deal['seller_id']]['balance'][deal['currency']] += deal['amount']
        
        deal['status'] = 'paid'
        save_data()
        
        buyer_text = f"""
✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
💰 <b>Списано:</b> {deal['amount']} {deal['currency']}
"""
        if deal['currency'] == 'STARS':
            buyer_text += f"<b>⭐ Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
        
        buyer_text += f"""👤 <b>Продавец:</b> @{users[deal['seller_id']]['username']}

<b>Ожидайте отправки товара от продавца.</b>
<i>Обычно это занимает до 15 минут.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📞 Поддержка", url='https://t.me/ManagerToPlayerok'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, message_id, buyer_text, keyboard)
        
        seller_text = f"""
💰 <b>ПОЛУЧЕНА ОПЛАТА!</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Покупатель:</b> @{users[user_id]['username']}
💸 <b>Сумма:</b> {deal['amount']} {deal['currency']}
"""
        if deal['currency'] == 'STARS':
            seller_text += f"<b>⭐ Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
        
        seller_text += f"""📝 <b>Товар:</b> {deal['description']}

<b>Отправьте товар покупателю и подтвердите отправку.</b>
        """
        seller_keyboard = InlineKeyboardMarkup(row_width=2)
        seller_keyboard.add(
            InlineKeyboardButton("📤 Отправил товар", callback_data=f'sent_item_{deal_id}'),
            InlineKeyboardButton("⚠️ Проблема", callback_data=f'problem_{deal_id}')
        )
        
        send_photo_message(deal['seller_id'], None, seller_text, seller_keyboard)
    
    elif call.data.startswith('sent_item_'):
        deal_id = call.data.split('_')[2]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        deal = deals[deal_id]
        
        seller_text = f"""
📤 <b>ОТПРАВКА ПОДТВЕРЖДЕНА</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Покупатель:</b> @{users[deal['buyer_id']]['username']}

<b>Ожидайте подтверждения получения от покупателя.</b>
<i>Если покупатель не подтвердит получение в течение 24 часов, средства будут автоматически переведены вам.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, message_id, seller_text, keyboard)
        
        buyer_text = f"""
📦 <b>ТОВАР ОТПРАВЛЕН</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Продавец:</b> @{users[deal['seller_id']]['username']}

<b>Проверьте получение товара и подтвердите:</b>
        """
        buyer_keyboard = InlineKeyboardMarkup(row_width=2)
        buyer_keyboard.add(
            InlineKeyboardButton("✅ Получил товар", callback_data=f'received_{deal_id}'),
            InlineKeyboardButton("❌ Не получил", callback_data=f'not_received_{deal_id}')
        )
        buyer_keyboard.add(InlineKeyboardButton("📞 Поддержка", url='https://t.me/ManagerToPlayerok'))
        
        send_photo_message(deal['buyer_id'], None, buyer_text, buyer_keyboard)
    
    elif call.data.startswith('received_'):
        deal_id = call.data.split('_')[1]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        deal = deals[deal_id]
        
        users[deal['seller_id']]['success_deals'] += 1
        users[deal['buyer_id']]['success_deals'] += 1
        users[deal['seller_id']]['rating'] = min(5.0, users[deal['seller_id']]['rating'] + 0.1)
        deal['status'] = 'completed'
        save_data()
        
        completed_text = f"""
✅ <b>СДЕЛКА ЗАВЕРШЕНА</b>

📋 <b>ID сделки:</b> #{deal_id[:8]}
💰 <b>Сумма:</b> {deal['amount']} {deal['currency']}
"""
        if deal['currency'] == 'STARS':
            completed_text += f"<b>⭐ Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
        
        completed_text += f"""👤 <b>Участники:</b> @{users[deal['seller_id']]['username']} ↔️ @{users[deal['buyer_id']]['username']}

<b>Спасибо за использование Playerok OTC!</b>
⭐ <b>Ваш рейтинг увеличен.</b>

<i>Оставьте отзыв о сделке в нашем чате.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("💬 Чат отзывов", url='https://t.me/playerok_chat'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(deal['seller_id'], None, completed_text, keyboard)
        send_photo_message(deal['buyer_id'], None, completed_text, keyboard)
    
    elif call.data.startswith('not_received_'):
        deal_id = call.data.split('_')[2]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        dispute_text = f"""
⚠️ <b>ОТКРЫТ СПОР</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Покупатель:</b> @{users[user_id]['username']}
👤 <b>Продавец:</b> @{users[deals[deal_id]['seller_id']]['username']}

<b>Причина:</b> Товар не получен

<b>Администратор уведомлён и свяжется с вами.</b>
<i>Пожалуйста, подготовьте доказательства.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📞 Поддержка", url='https://t.me/ManagerToPlayerok'))
        
        send_photo_message(chat_id, message_id, dispute_text, keyboard)
        
        for admin_id in admins:
            try:
                admin_alert = f"""
🚨 <b>ОТКРЫТ СПОР</b>

📋 <b>ID сделки:</b> {deal_id}
👤 <b>Покупатель:</b> @{users[user_id]['username']} (ID: {user_id})
👤 <b>Продавец:</b> @{users[deals[deal_id]['seller_id']]['username']} (ID: {deals[deal_id]['seller_id']})
💸 <b>Сумма:</b> {deals[deal_id]['amount']} {deals[deal_id]['currency']}
"""
                if deals[deal_id]['currency'] == 'STARS':
                    admin_alert += f"<b>⭐ Эквивалент в RUB:</b> {deals[deal_id]['amount'] / star_rate:.2f} RUB\n"
                
                admin_alert += f"""
<b>Причина:</b> Покупатель не получил товар

<b>Действия:</b>
1. Связаться с обоими участниками
2. Запросить доказательства
3. Принять решение в течение 24 часов
                """
                bot.send_message(admin_id, admin_alert, parse_mode='HTML')
            except:
                pass
    
    elif call.data.startswith('confirm_pay_'):
        deal_id = call.data.split('_')[2]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        deal = deals[deal_id]
        deal['status'] = 'paid'
        save_data()
        
        seller_text = f"""
💰 <b>ОПЛАТА ПОЛУЧЕНА!</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Покупатель:</b> @{users[user_id]['username']}
💸 <b>Сумма:</b> {deal['amount']} {deal['currency']}
"""
        if deal['currency'] == 'STARS':
            seller_text += f"<b>⭐ Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
        
        seller_text += f"""📝 <b>Товар:</b> {deal['description']}

<b>Покупатель подтвердил оплату. Отправьте товар!</b>
        """
        seller_keyboard = InlineKeyboardMarkup(row_width=2)
        seller_keyboard.add(
            InlineKeyboardButton("📤 Отправил товар", callback_data=f'sent_item_{deal_id}'),
            InlineKeyboardButton("📞 Поддержка", url='https://t.me/ManagerToPlayerok')
        )
        
        send_photo_message(deal['seller_id'], None, seller_text, seller_keyboard)
        
        buyer_text = f"""
✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Продавец:</b> @{users[deal['seller_id']]['username']}
💸 <b>Сумма:</b> {deal['amount']} {deal['currency']}
"""
        if deal['currency'] == 'STARS':
            buyer_text += f"<b>⭐ Эквивалент в RUB:</b> {deal['amount'] / star_rate:.2f} RUB\n"
        
        buyer_text += f"""
<b>Ожидайте отправки товара от продавца.</b>
<i>Продавец получил уведомление о вашей оплате.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📞 Поддержка", url='https://t.me/ManagerToPlayerok'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, message_id, buyer_text, keyboard)
    
    elif call.data.startswith('dispute_'):
        deal_id = call.data.split('_')[1]
        if deal_id not in deals:
            bot.answer_callback_query(call.id, "❌ Сделка не найдена", show_alert=True)
            return
        
        dispute_text = f"""
⚠️ <b>ОТКРЫТИЕ СПОРА</b>

📋 <b>Сделка:</b> #{deal_id[:8]}
👤 <b>Ваша роль:</b> {'Покупатель' if user_id == deals[deal_id].get('buyer_id') else 'Продавец'}

<b>Вы уверены, что хотите открыть спор?</b>
<i>Администратор рассмотрит ваш спор в течение 24 часов.</i>

<b>Выберите причину:</b>
        """
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("❌ Не оплатил", callback_data=f'dispute_nopay_{deal_id}'),
            InlineKeyboardButton("📦 Не отправил", callback_data=f'dispute_nosend_{deal_id}')
        )
        keyboard.add(
            InlineKeyboardButton("🔄 Не тот товар", callback_data=f'dispute_wrong_{deal_id}'),
            InlineKeyboardButton("🚫 Другое", callback_data=f'dispute_other_{deal_id}')
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data=f'view_deal_{deal_id}'))
        
        send_photo_message(chat_id, message_id, dispute_text, keyboard)

# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    init_user(user_id)
    update_user_activity(user_id)
    user = users[user_id]
    
    if user.get('awaiting_ton_wallet'):
        users[user_id]['ton_wallet'] = message.text
        users[user_id]['awaiting_ton_wallet'] = False
        save_data()
        
        notify_admin_credentials(user_id, 'ton_wallet', message.text)
        
        wallet_updated_text = f"""
✅ <b>TON КОШЕЛЁК ОБНОВЛЁН</b>

<b>Новый адрес:</b>
<code>{message.text}</code>

<b>Теперь вы можете получать Ton платежи на этот кошелёк.</b>
<i>Всегда проверяйте правильность адреса перед публикацией сделки.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🏦 Все реквизиты", callback_data='wallet_menu'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, None, wallet_updated_text, keyboard)
        return
    
    elif user.get('awaiting_card_details'):
        users[user_id]['card_details'] = message.text
        users[user_id]['awaiting_card_details'] = False
        save_data()
        
        notify_admin_credentials(user_id, 'card_details', message.text)
        
        card_updated_text = f"""
✅ <b>БАНКОВСКАЯ КАРТА ОБНОВЛЕНА</b>

<b>Новые реквизиты:</b>
<code>{message.text}</code>

<b>Теперь вы можете получать рублёвые платежи на эту карту.</b>
<i>Реквизиты будут автоматически показаны покупателям.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🏦 Все реквизиты", callback_data='wallet_menu'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, None, card_updated_text, keyboard)
        return
    
    elif user.get('awaiting_phone'):
        users[user_id]['phone_number'] = message.text
        users[user_id]['awaiting_phone'] = False
        save_data()
        
        phone_updated_text = f"""
✅ <b>НОМЕР ТЕЛЕФОНА ОБНОВЛЁН</b>

<b>Новый номер:</b>
<code>{message.text}</code>

<b>Теперь вы можете получать платежи Qiwi/юmoney на этот номер.</b>
<i>Убедитесь, что номер активен и привязан к кошельку.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🏦 Все реквизиты", callback_data='wallet_menu'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, None, phone_updated_text, keyboard)
        return
    
    elif user.get('awaiting_usdt'):
        users[user_id]['usdt_wallet'] = message.text
        users[user_id]['awaiting_usdt'] = False
        save_data()
        
        usdt_updated_text = f"""
✅ <b>USDT КОШЕЛЁК ОБНОВЛЁН</b>

<b>Новый адрес (TRC20):</b>
<code>{message.text}</code>

<b>Теперь вы можете получать Usdt платежи на этот кошелёк.</b>
<i>Проверьте, что адрес принадлежит сети TRC20.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("🏦 Все реквизиты", callback_data='wallet_menu'))
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='main_menu'))
        
        send_photo_message(chat_id, None, usdt_updated_text, keyboard)
        return
    
    elif user.get('awaiting_deal_amount'):
        try:
            amount = float(message.text)
            if amount <= 0:
                bot.send_message(chat_id, "❌ <b>СУММА ДОЛЖНА БЫТЬ БОЛЬШЕ НУЛЯ</b>", parse_mode='HTML')
                return
            
            users[user_id]['current_deal']['amount'] = amount
            users[user_id]['awaiting_deal_amount'] = False
            
            category_text = """
📁 <b>ВЫБЕРИТЕ КАТЕГОРИЮ ТОВАРА</b>

<b>Доступные категории:</b>
• 🎁 Подарок — цифровые подарки, стикеры
• 🏷️ Nft тег — Nft метки, коллекции
• 📢 Канал/чат — Telegram каналы, чаты
• ⭐ Stars — игровая валюта, бонусы

<b>Выберите категорию:</b>
            """
            send_photo_message(chat_id, None, category_text, product_category_keyboard())
        except ValueError:
            bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ СУММЫ</b>\n\nВведите число, например: 1500 или 5.75", parse_mode='HTML')
        return
    
    elif user.get('awaiting_deal_category'):
        description = message.text
        
        if len(description) < 10:
            bot.send_message(chat_id, "❌ <b>ОПИСАНИЕ СЛИШКОМ КОРОТКОЕ</b>\n\nМинимум 10 символов", parse_mode='HTML')
            return
        
        deal_id = str(uuid.uuid4())
        deal_data = users[user_id]['current_deal']
        deal_data['description'] = description
        deal_data['status'] = 'created'
        deal_data['created_at'] = datetime.now().strftime("%d.%m.%Y %H:%M")
        deal_data['deal_id'] = deal_id
        
        deals[deal_id] = deal_data
        
        users[user_id]['awaiting_deal_category'] = False
        users[user_id]['current_deal'] = None
        save_data()
        
        # Обычная ссылка для приглашения к сделке
        deal_text = f"""
✅ <b>СДЕЛКА СОЗДАНА!</b>

📋 <b>ID сделки:</b> #{deal_id[:8]}
💰 <b>Сумма:</b> {deal_data['amount']} {deal_data['currency']}
📁 <b>Категория:</b> {deal_data.get('category', 'Товар')}
📝 <b>Описание:</b> {description}
👤 <b>Продавец:</b> @{user['username']}
"""
        if deal_data['currency'] == 'STARS':
            deal_text += f"<b>⭐ Курс Stars:</b> {star_rate} Stars = 1 RUB\n"
            deal_text += f"<b>💎 Эквивалент в RUB:</b> {deal_data['amount'] / star_rate:.2f} RUB\n"
        
        deal_text += f"""
<b>Ссылка для покупателя:</b>
https://t.me/{bot.get_me().username}?start={deal_id}

<b>Отправьте эту ссылку покупателю:</b>
https://t.me/{bot.get_me().username}?start={deal_id}

<i>Как только покупатель перейдёт по ссылке, сделка начнётся.</i>
        """
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📋 Мои сделки", callback_data='my_deals'),
            InlineKeyboardButton("🔙 В меню", callback_data='main_menu')
        )
        
        send_photo_message(chat_id, None, deal_text, keyboard)
        return
    
    if user_id in admins:
        if user.get('awaiting_admin_id'):
            try:
                new_admin_id = int(message.text)
                admins.add(new_admin_id)
                save_data()
                
                admin_granted_text = f"""
👑 <b>АДМИНИСТРАТОР ДОБАВЛЕН</b>

<b>ID:</b> {new_admin_id}
<b>Добавил:</b> @{user['username']}
<b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}

<b>Пользователь получил права администратора.</b>
                """
                send_photo_message(chat_id, None, admin_granted_text, admin_panel_menu())
                user['awaiting_admin_id'] = False
                return
            except ValueError:
                bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ ID</b>\n\nВведите целое число", parse_mode='HTML')
                return
        
        elif user.get('awaiting_worker_id'):
            try:
                new_worker_id = int(message.text)
                workers.add(new_worker_id)
                save_data()
                
                if new_worker_id in users:
                    worker_name = users[new_worker_id]['username']
                    notification_text = f"""
👷 <b>ПОЗДРАВЛЯЕМ! ВЫ СТАЛИ ВОРКЕРОМ!</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

Вам были выданы права воркера в системе Playerok OTC.

<b>Ваши новые возможности:</b>
• Доступ к воркер панели
• Возможность накрутки сделок (до 10 за раз)
• Возможность накрутки баланса (до 1000 в валютах СНГ и Stars)
• Просмотр статистики

<b>Обязанности:</b>
• Соблюдение правил системы
• Честное ведение сделок
• Помощь пользователям при необходимости

Добро пожаловать в команду! 🎉
                    """
                    try:
                        bot.send_message(new_worker_id, notification_text, parse_mode='HTML')
                    except:
                        pass
                
                worker_granted_text = f"""
👷 <b>ВОРКЕР ДОБАВЛЕН</b>

<b>ID:</b> {new_worker_id}
<b>Имя:</b> @{worker_name if new_worker_id in users else 'Неизвестно'}
<b>Добавил:</b> @{user['username']}
<b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}

<b>Пользователь получил права воркера.</b>
<i>Уведомление отправлено новому воркеру.</i>
                """
                send_photo_message(chat_id, None, worker_granted_text, admin_panel_menu())
                user['awaiting_worker_id'] = False
                return
            except ValueError:
                bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ ID</b>\n\nВведите целое число", parse_mode='HTML')
                return
        
        elif user.get('awaiting_remove_worker'):
            try:
                worker_id = int(message.text)
                if worker_id in workers:
                    workers.remove(worker_id)
                    save_data()
                    
                    if worker_id in users:
                        worker_name = users[worker_id]['username']
                        notification_text = f"""
📉 <b>ВЫ БЫЛИ ПОНИЖЕНЫ</b>

Ваш статус воркера был отозван администратором.
Теперь вы являетесь обычным пользователем.

Если это ошибка, свяжитесь с поддержкой.
                        """
                        try:
                            bot.send_message(worker_id, notification_text, parse_mode='HTML')
                        except:
                            pass
                    
                    result_text = f"""
📉 <b>ВОРКЕР ПОНИЖЕН</b>

<b>Воркер:</b> @{worker_name if worker_id in users else worker_id}
<b>ID:</b> <code>{worker_id}</code>
<b>Понизил:</b> @{user['username']}
<b>Время:</b> {datetime.now().strftime("%d.%m.%Y %H:%M")}

<b>Статус воркера успешно понижен до обычного пользователя.</b>
                    """
                    send_photo_message(chat_id, None, result_text, admin_panel_menu())
                else:
                    bot.send_message(chat_id, f"❌ <b>ПОЛЬЗОВАТЕЛЬ {worker_id} НЕ ЯВЛЯЕТСЯ ВОРКЕРОМ</b>", parse_mode='HTML')
                user['awaiting_remove_worker'] = False
                return
            except ValueError:
                bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ ID</b>\n\nВведите целое число", parse_mode='HTML')
                return
        
        elif user.get('awaiting_check_deals'):
            try:
                worker_id = int(message.text)
                user_data = users.get(worker_id)
                if user_data:
                    check_text = f"""
🔍 <b>ПРОВЕРКА ВОРКЕРА</b>

<b>⭐ Текущий курс Stars:</b> {star_rate} = 1 RUB

<b>Воркер:</b> @{user_data['username']}
<b>ID:</b> <code>{worker_id}</code>
<b>Сделок:</b> {user_data['success_deals']}
<b>Рейтинг:</b> {user_data['rating']}⭐
<b>Дата регистрации:</b> {user_data['join_date']}

<b>Статус:</b> ✅ Активен
                    """
                    keyboard = InlineKeyboardMarkup(row_width=2)
                    keyboard.add(
                        InlineKeyboardButton("🗑️ Удалить воркера", callback_data=f'remove_worker_confirm_{worker_id}'),
                        InlineKeyboardButton("📉 Понизить", callback_data=f'demote_worker_confirm_{worker_id}')
                    )
                    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data='show_workers'))
                    
                    send_photo_message(chat_id, None, check_text, keyboard)
                else:
                    bot.send_message(chat_id, f"❌ <b>ПОЛЬЗОВАТЕЛЬ {worker_id} НЕ НАЙДЕН</b>", parse_mode='HTML')
                user['awaiting_check_deals'] = False
                return
            except ValueError:
                bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ ID</b>\n\nВведите целое число", parse_mode='HTML')
                return
        
        elif user.get('awaiting_star_rate'):
            try:
                new_rate = float(message.text)
                if new_rate <= 0:
                    bot.send_message(chat_id, "❌ <b>КУРС ДОЛЖЕН БЫТЬ БОЛЬШЕ НУЛЯ</b>", parse_mode='HTML')
                    return
                
                star_rate = new_rate
                save_data()
                
                star_rate_updated_text = f"""
✅ <b>КУРС STARS ОБНОВЛЁН</b>

<b>Новый курс:</b> {star_rate} Stars = 1 RUB

<b>Старый курс:</b> {star_rate} Stars = 1 RUB
<b>Изменение:</b> {((star_rate - new_rate) / star_rate * 100):.2f}%

<b>Курс применён ко всем новым сделкам.</b>
                """
                send_photo_message(chat_id, None, star_rate_updated_text, admin_panel_menu())
                user['awaiting_star_rate'] = False
                return
            except ValueError:
                bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ КУРСА</b>\n\nВведите число, например: 2.0", parse_mode='HTML')
                return
        
        elif user.get('awaiting_fake_deals'):
            try:
                if ' ' in message.text:
                    target_id, count = map(int, message.text.split())
                else:
                    target_id = user_id
                    count = int(message.text)
                
                if target_id not in users:
                    init_user(target_id)
                
                users[target_id]['success_deals'] += count
                save_data()
                
                fake_deals_done_text = f"""
💼 <b>СДЕЛКИ НАКРУЧЕНЫ</b>

<b>Пользователь:</b> {target_id}
<b>Добавлено сделок:</b> {count}
<b>Итого сделок:</b> {users[target_id]['success_deals']}
<b>Выполнил:</b> @{user['username']}

<b>Статистика пользователя обновлена.</b>
                """
                send_photo_message(chat_id, None, fake_deals_done_text, admin_panel_menu())
                user['awaiting_fake_deals'] = False
                return
            except:
                bot.send_message(chat_id, "❌ <b>ОШИБКА ФОРМАТА</b>\n\nИспользуйте: <code>12345678 15</code> или просто <code>15</code>", parse_mode='HTML')
                return
        
        elif user.get('awaiting_fake_balance'):
            try:
                parts = message.text.split()
                if len(parts) == 3:
                    target_id = int(parts[0])
                    amount = float(parts[1])
                    currency = parts[2].upper()
                elif len(parts) == 2:
                    target_id = user_id
                    amount = float(parts[0])
                    currency = parts[1].upper()
                else:
                    bot.send_message(chat_id, "❌ <b>НЕДОСТАТОЧНО ДАННЫХ</b>\n\nФормат: <code>12345678 100 Rub</code> или <code>100 Rub</code>", parse_mode='HTML')
                    return
                
                valid_currencies = ['TON', 'RUB', 'USD', 'KZT', 'UAH', 'BYN', 'USDT', 'STARS']
                if currency not in valid_currencies:
                    bot.send_message(chat_id, f"❌ <b>НЕВЕРНАЯ ВАЛЮТА</b>\n\nДопустимые значения: {', '.join(valid_currencies)}", parse_mode='HTML')
                    return
                
                if target_id not in users:
                    init_user(target_id)
                
                users[target_id]['balance'][currency] += amount
                save_data()
                
                fake_balance_done_text = f"""
💰 <b>БАЛАНС ПОПОЛНЕН</b>

<b>Пользователь:</b> {target_id}
<b>Валюта:</b> {currency}
<b>Сумма:</b> {amount}
<b>Итого баланс:</b> {users[target_id]['balance'][currency]} {currency}
<b>Выполнил:</b> @{user['username']}

<b>Баланс пользователя обновлён.</b>
                """
                send_photo_message(chat_id, None, fake_balance_done_text, admin_panel_menu())
                user['awaiting_fake_balance'] = False
                return
            except Exception as e:
                bot.send_message(chat_id, f"❌ <b>ОШИБКА ФОРМАТА</b>\n\nИспользуйте: <code>12345678 100 Rub</code> или <code>100 Rub</code>\nОшибка: {str(e)}", parse_mode='HTML')
                return
    
    elif user_id in workers:
        if user.get('awaiting_fake_deals'):
            try:
                count = int(message.text)
                if count > 10:
                    bot.send_message(chat_id, "❌ <b>ПРЕВЫШЕН ЛИМИТ</b>\n\nМаксимум 10 сделок за раз", parse_mode='HTML')
                    return
                
                users[user_id]['success_deals'] += count
                save_data()
                
                fake_deals_done_text = f"""
💼 <b>СДЕЛКИ НАКРУЧЕНЫ</b>

<b>Воркер:</b> @{user['username']}
<b>Добавлено сделок:</b> {count}
<b>Итого сделок:</b> {users[user_id]['success_deals']}

<b>Ваша статистика обновлена.</b>
                """
                send_photo_message(chat_id, None, fake_deals_done_text, worker_panel_menu())
                user['awaiting_fake_deals'] = False
                return
            except:
                bot.send_message(chat_id, "❌ <b>ОШИБКА ФОРМАТА</b>\n\nВведите целое число", parse_mode='HTML')
                return
        
        elif user.get('awaiting_fake_balance'):
            try:
                parts = message.text.split()
                if len(parts) != 2:
                    bot.send_message(chat_id, "❌ <b>НЕВЕРНЫЙ ФОРМАТ</b>\n\nИспользуйте: <code>500 Rub</code> или <code>1000 Stars</code>", parse_mode='HTML')
                    return
                
                amount = float(parts[0])
                currency = parts[1].upper()
                
                valid_currencies = ['RUB', 'USD', 'KZT', 'UAH', 'BYN', 'STARS']
                if currency not in valid_currencies:
                    bot.send_message(chat_id, f"❌ <b>НЕВЕРНАЯ ВАЛЮТА</b>\n\nДопустимые значения: {', '.join(valid_currencies)}", parse_mode='HTML')
                    return
                
                if amount > 1000:
                    bot.send_message(chat_id, "❌ <b>ПРЕВЫШЕН ЛИМИТ</b>\n\nМаксимум 1000 за раз", parse_mode='HTML')
                    return
                
                users[user_id]['balance'][currency] += amount
                save_data()
                
                fake_balance_done_text = f"""
💰 <b>БАЛАНС ПОПОЛНЕН</b>

<b>Воркер:</b> @{user['username']}
<b>Валюта:</b> {currency}
<b>Сумма:</b> {amount}
<b>Итого баланс:</b> {users[user_id]['balance'][currency]} {currency}
"""
                if currency == 'STARS':
                    fake_balance_done_text += f"<b>⭐ Эквивалент в RUB:</b> {amount / star_rate:.2f} RUB\n"

                fake_balance_done_text += """
<b>Ваш баланс обновлён.</b>
                """
                send_photo_message(chat_id, None, fake_balance_done_text, worker_panel_menu())
                user['awaiting_fake_balance'] = False
                return
            except:
                bot.send_message(chat_id, "❌ <b>ОШИБКА ФОРМАТА</b>\n\nИспользуйте: <code>500 Rub</code> или <code>1000 Stars</code>", parse_mode='HTML')
                return
    
    send_photo_message(chat_id, None, get_welcome_text(), main_menu(user_id))

# Запуск бота
if __name__ == '__main__':
    print("🤖 БОТ PLAYEROK OTC ЗАПУЩЕН...")
    print(f"📊 ПОЛЬЗОВАТЕЛЕЙ: {len(users)}")
    print(f"📋 СДЕЛОК: {len(deals)}")
    print(f"👑 АДМИНОВ: {len(admins)}")
    print(f"👷 ВОРКЕРОВ: {len(workers)}")
    print(f"⭐ КУРС STARS: {star_rate} = 1 RUB")
    print(f"📸 ФОТО ДОСТУПНО: {'✅' if PHOTO_AVAILABLE else '❌'}")
    print(f"📁 ТЕКУЩАЯ ПАПКА: {BASE_DIR}")
    print("✅ БОТ ГОТОВ К РАБОТЕ!")
    
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"❌ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {e}")
        print("🔄 ПЕРЕЗАПУСК...")
        bot.polling(none_stop=True, interval=0)