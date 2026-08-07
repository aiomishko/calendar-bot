import telebot
from telebot import types
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATA_FILE = "events.json"
EVENTS_PER_PAGE = 5

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}
file_lock = threading.Lock()

MSK = timezone(timedelta(hours=3))


def now_msk():
    return datetime.now(MSK)


def load_events():
    with file_lock:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}


def save_events(events):
    with file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)


def get_user_events(user_id):
    events = load_events()
    uid = str(user_id)
    if uid not in events:
        events[uid] = []
        save_events(events)
    return events[uid]


def add_user_event(user_id, event):
    events = load_events()
    uid = str(user_id)
    if uid not in events:
        events[uid] = []
    for e in events[uid]:
        if e["text"] == event["text"] and e["created"] == event["created"]:
            return
    events[uid].append(event)
    save_events(events)


def remove_user_event(user_id, index):
    events = load_events()
    uid = str(user_id)
    if uid in events and 0 <= index < len(events[uid]):
        removed = events[uid].pop(index)
        save_events(events)
        return removed
    return None


def get_delta(interval_type, interval_value):
    if interval_type == "минута":
        return timedelta(minutes=interval_value)
    elif interval_type == "час":
        return timedelta(hours=interval_value)
    elif interval_type == "день":
        return timedelta(days=interval_value)
    elif interval_type == "неделя":
        return timedelta(weeks=interval_value)
    elif interval_type == "месяц":
        return timedelta(days=30 * interval_value)
    elif interval_type == "год":
        return timedelta(days=365 * interval_value)
    return timedelta(days=interval_value)


def parse_next_reminder(event):
    dt = datetime.strptime(event["next_reminder"], "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=MSK)


def advance_reminder(event):
    delta = get_delta(event["interval_type"], event["interval_value"])
    now = now_msk()
    next_dt = parse_next_reminder(event)
    while next_dt <= now:
        next_dt += delta
    event["next_reminder"] = next_dt.strftime("%Y-%m-%d %H:%M:%S")
    return next_dt


def format_interval(event):
    val = event["interval_value"]
    typ = event["interval_type"]

    if typ == "минута":
        if val % 10 == 1 and val % 100 != 11:
            word = "минуту"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "минуты"
        else:
            word = "минут"
    elif typ == "час":
        if val % 10 == 1 and val % 100 != 11:
            word = "час"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "часа"
        else:
            word = "часов"
    elif typ == "день":
        if val % 10 == 1 and val % 100 != 11:
            word = "день"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "дня"
        else:
            word = "дней"
    elif typ == "неделя":
        if val % 10 == 1 and val % 100 != 11:
            word = "неделю"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "недели"
        else:
            word = "недель"
    elif typ == "месяц":
        if val % 10 == 1 and val % 100 != 11:
            word = "месяц"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "месяца"
        else:
            word = "месяцев"
    elif typ == "год":
        if val % 10 == 1 and val % 100 != 11:
            word = "год"
        elif 2 <= val % 10 <= 4 and not (12 <= val % 100 <= 14):
            word = "года"
        else:
            word = "лет"
    else:
        word = typ

    return f"{val} {word}"


def format_time_left(delta):
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "сейчас"

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days} дн.")
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0:
        parts.append(f"{minutes} мин.")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек.")

    return " ".join(parts)


def parse_custom_interval(text):
    text = text.strip().lower()
    parts = text.split()
    if len(parts) != 2:
        return None, None
    try:
        value = int(parts[0])
    except ValueError:
        return None, None
    if value <= 0:
        return None, None

    word = parts[1]
    if word in ["минута", "минуты", "минут", "мин"]:
        return "минута", value
    elif word in ["час", "часа", "часов", "ч"]:
        return "час", value
    elif word in ["день", "дня", "дней", "д"]:
        return "день", value
    elif word in ["неделя", "недели", "недель", "неделю", "нед"]:
        return "неделя", value
    elif word in ["месяц", "месяца", "месяцев", "мес"]:
        return "месяц", value
    elif word in ["год", "года", "лет", "г"]:
        return "год", value
    return None, None


def parse_start_date(text):
    text = text.strip().lower()

    if text in ["сейчас", "now"]:
        return now_msk()

    if text in ["завтра"]:
        tomorrow = now_msk() + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

    if text in ["послезавтра"]:
        day = now_msk() + timedelta(days=2)
        return day.replace(hour=0, minute=0, second=0, microsecond=0)

    # через N минут/часов/дней/недель/месяцев/лет
    if text.startswith("через "):
        rest = text[6:].strip()
        typ, val = parse_custom_interval(rest)
        if typ and val:
            return now_msk() + get_delta(typ, val)
        return None

    # дд.мм.гггг
    for fmt in ["%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=MSK)
        except ValueError:
            continue

    # дд.мм.гг
    for fmt in ["%d.%m.%y %H:%M:%S", "%d.%m.%y %H:%M", "%d.%m.%y"]:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=MSK)
        except ValueError:
            continue

    return None


def build_date_text(user_id, page=0):
    now = now_msk()

    days_of_week = {
        0: "Понедельник", 1: "Вторник", 2: "Среда",
        3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
    }
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
    }

    text = f"{days_of_week[now.weekday()]}, {now.day} {months[now.month]} {now.year}\n"
    text += f"Время: {now.strftime('%H:%M:%S')}\n"

    events = get_user_events(user_id)

    if events:
        total = len(events)
        total_pages = (total + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE

        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0

        start = page * EVENTS_PER_PAGE
        end = min(start + EVENTS_PER_PAGE, total)

        text += f"\nСобытия ({total}):"
        if total_pages > 1:
            text += f" [{page + 1}/{total_pages}]"
        text += "\n"

        for i in range(start, end):
            event = events[i]
            next_remind = parse_next_reminder(event)
            time_left = next_remind - now
            text += f"\n{i + 1}. {event['text']}\n"
            text += f"   Повтор: каждые {format_interval(event)}\n"
            text += f"   Следующее: {next_remind.strftime('%d.%m.%Y %H:%M:%S')}\n"
            text += f"   Осталось: {format_time_left(time_left)}\n"
    else:
        text += "\nСобытий нет."

    return text


def build_date_markup(user_id, page=0):
    events = get_user_events(user_id)
    markup = types.InlineKeyboardMarkup()

    if events:
        total = len(events)
        total_pages = (total + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE

        if total_pages > 1:
            nav = []
            if page > 0:
                nav.append(types.InlineKeyboardButton("<", callback_data=f"page_{page - 1}"))
            nav.append(types.InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav.append(types.InlineKeyboardButton(">", callback_data=f"page_{page + 1}"))
            markup.row(*nav)

    markup.add(types.InlineKeyboardButton("Добавить событие", callback_data="add_event"))
    if events:
        markup.add(types.InlineKeyboardButton("Удалить событие", callback_data=f"delete_event_{page}"))

    return markup


def send_date_message(chat_id, user_id, page=0):
    text = build_date_text(user_id, page)
    markup = build_date_markup(user_id, page)
    bot.send_message(chat_id, text, reply_markup=markup)


def edit_to_date(chat_id, message_id, user_id, page=0):
    text = build_date_text(user_id, page)
    markup = build_date_markup(user_id, page)
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    except Exception:
        try:
            bot.send_message(chat_id, text, reply_markup=markup)
        except Exception:
            pass


@bot.message_handler(commands=["date"])
def cmd_date(message):
    uid = message.from_user.id
    if uid in user_data:
        del user_data[uid]
    send_date_message(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: call.data == "noop")
def callback_noop(call):
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("page_"))
def callback_page(call):
    page = int(call.data.split("_")[1])
    edit_to_date(call.message.chat.id, call.message.message_id, call.from_user.id, page)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "back")
def callback_back(call):
    uid = call.from_user.id
    if uid in user_data:
        del user_data[uid]
    edit_to_date(call.message.chat.id, call.message.message_id, call.from_user.id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "add_event")
def callback_add_event(call):
    uid = call.from_user.id
    user_data[uid] = {"step": "waiting_text"}

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))

    bot.edit_message_text(
        "Какое событие хочешь добавить?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_event_"))
def callback_delete_event(call):
    page = int(call.data.split("_")[2])
    events = get_user_events(call.from_user.id)
    if not events:
        bot.answer_callback_query(call.id, "Событий нет.")
        return

    total = len(events)
    total_pages = (total + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE
    if page >= total_pages:
        page = total_pages - 1

    start = page * EVENTS_PER_PAGE
    end = min(start + EVENTS_PER_PAGE, total)

    markup = types.InlineKeyboardMarkup()
    for i in range(start, end):
        event = events[i]
        label = f"{event['text']} ({format_interval(event)})"
        if len(label) > 60:
            label = label[:57] + "..."
        markup.add(types.InlineKeyboardButton(label, callback_data=f"del_{i}"))

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton("<", callback_data=f"delpage_{page - 1}"))
        nav.append(types.InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(types.InlineKeyboardButton(">", callback_data=f"delpage_{page + 1}"))
        markup.row(*nav)

    markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))

    bot.edit_message_text(
        "Какое событие удалить?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delpage_"))
def callback_delpage(call):
    page = int(call.data.split("_")[1])
    events = get_user_events(call.from_user.id)
    total = len(events)
    total_pages = (total + EVENTS_PER_PAGE - 1) // EVENTS_PER_PAGE
    if page >= total_pages:
        page = total_pages - 1

    start = page * EVENTS_PER_PAGE
    end = min(start + EVENTS_PER_PAGE, total)

    markup = types.InlineKeyboardMarkup()
    for i in range(start, end):
        event = events[i]
        label = f"{event['text']} ({format_interval(event)})"
        if len(label) > 60:
            label = label[:57] + "..."
        markup.add(types.InlineKeyboardButton(label, callback_data=f"del_{i}"))

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton("<", callback_data=f"delpage_{page - 1}"))
        nav.append(types.InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(types.InlineKeyboardButton(">", callback_data=f"delpage_{page + 1}"))
        markup.row(*nav)

    markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))

    bot.edit_message_text(
        "Какое событие удалить?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def callback_del(call):
    index = int(call.data.split("_")[1])
    removed = remove_user_event(call.from_user.id, index)
    if removed:
        text = f"Событие \"{removed['text']}\" удалено."
    else:
        text = "Ошибка при удалении."

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Назад", callback_data="back"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("interval_"))
def callback_interval(call):
    uid = call.from_user.id
    if uid not in user_data or user_data[uid].get("step") != "waiting_interval":
        bot.answer_callback_query(call.id, "Начни заново через /date")
        return

    choice = call.data.replace("interval_", "")

    if choice == "custom":
        user_data[uid]["step"] = "waiting_custom_interval"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))

        bot.edit_message_text(
            "Введи интервал.\n\nПримеры:\n30 минут\n2 часа\n5 дней\n2 недели\n3 месяца\n1488 дней\n1 год",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        return

    interval_map = {
        "minute": ("минута", 1),
        "hour": ("час", 1),
        "day": ("день", 1),
        "week": ("неделя", 1),
        "month": ("месяц", 1),
        "year": ("год", 1),
    }

    if choice in interval_map:
        typ, val = interval_map[choice]
        user_data[uid]["interval_type"] = typ
        user_data[uid]["interval_value"] = val
        ask_start_date(call.message, uid)
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("start_"))
def callback_start_date(call):
    uid = call.from_user.id
    if uid not in user_data or user_data[uid].get("step") != "waiting_start":
        bot.answer_callback_query(call.id, "Начни заново через /date")
        return

    choice = call.data.replace("start_", "")

    now = now_msk()

    if choice == "now":
        start = now
    elif choice == "tomorrow":
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif choice == "aftertomorrow":
        start = (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif choice == "custom":
        user_data[uid]["step"] = "waiting_custom_start"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))

        bot.edit_message_text(
            "Введи начальную дату.\n\nПримеры:\n"
            "сейчас\n"
            "завтра\n"
            "послезавтра\n"
            "через 5 дней\n"
            "через 2 часа\n"
            "через 30 минут\n"
            "15.09.2067\n"
            "15.09.2067 14:00\n"
            "15.09.2067 14:30:00",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        return
    else:
        bot.answer_callback_query(call.id, "Ошибка")
        return

    finish_event(call.message, uid, start)
    bot.answer_callback_query(call.id)


def ask_start_date(message, uid):
    user_data[uid]["step"] = "waiting_start"

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Сейчас", callback_data="start_now"),
        types.InlineKeyboardButton("Завтра", callback_data="start_tomorrow"),
    )
    markup.add(
        types.InlineKeyboardButton("Послезавтра", callback_data="start_aftertomorrow"),
        types.InlineKeyboardButton("Свой вариант", callback_data="start_custom"),
    )
    markup.add(
        types.InlineKeyboardButton("Отмена", callback_data="back"),
    )

    event_text = user_data[uid]["event_text"]
    interval_type = user_data[uid]["interval_type"]
    interval_value = user_data[uid]["interval_value"]
    interval_str = format_interval({"interval_type": interval_type, "interval_value": interval_value})

    bot.edit_message_text(
        f"Событие: \"{event_text}\"\n"
        f"Повтор: каждые {interval_str}\n\n"
        f"Когда первое напоминание?",
        message.chat.id,
        message.message_id,
        reply_markup=markup
    )


def finish_event(message, uid, start_date):
    if uid not in user_data or "event_text" not in user_data[uid]:
        return

    event_text = user_data[uid]["event_text"]
    interval_type = user_data[uid]["interval_type"]
    interval_value = user_data[uid]["interval_value"]
    del user_data[uid]

    now = now_msk()

    # если дата старта уже прошла, сдвигаем на будущее
    if start_date <= now:
        delta = get_delta(interval_type, interval_value)
        while start_date <= now:
            start_date += delta

    event = {
        "text": event_text,
        "interval_type": interval_type,
        "interval_value": interval_value,
        "created": now.strftime("%Y-%m-%d %H:%M:%S"),
        "next_reminder": start_date.strftime("%Y-%m-%d %H:%M:%S"),
    }

    add_user_event(uid, event)
    time_left = start_date - now

    interval_str = format_interval(event)

    text = (
        f"Событие добавлено.\n\n"
        f"{event_text}\n"
        f"Повтор: каждые {interval_str}\n"
        f"Первое напоминание: {start_date.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"Осталось: {format_time_left(time_left)}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Назад", callback_data="back"))

    try:
        bot.edit_message_text(text, message.chat.id, message.message_id, reply_markup=markup)
    except Exception:
        try:
            bot.send_message(message.chat.id, text, reply_markup=markup)
        except Exception:
            pass


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    uid = message.from_user.id

    if uid not in user_data:
        return

    step = user_data[uid].get("step")

    if step == "waiting_text":
        event_text = message.text.strip()
        if len(event_text) > 200:
            bot.send_message(message.chat.id, "Слишком длинный текст. Максимум 200 символов.")
            return

        user_data[uid]["event_text"] = event_text
        user_data[uid]["step"] = "waiting_interval"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Минута", callback_data="interval_minute"),
            types.InlineKeyboardButton("Час", callback_data="interval_hour"),
        )
        markup.add(
            types.InlineKeyboardButton("День", callback_data="interval_day"),
            types.InlineKeyboardButton("Неделя", callback_data="interval_week"),
        )
        markup.add(
            types.InlineKeyboardButton("Месяц", callback_data="interval_month"),
            types.InlineKeyboardButton("Год", callback_data="interval_year"),
        )
        markup.add(
            types.InlineKeyboardButton("Свой вариант", callback_data="interval_custom"),
        )
        markup.add(
            types.InlineKeyboardButton("Отмена", callback_data="back"),
        )

        bot.send_message(
            message.chat.id,
            f"Событие: \"{event_text}\"\n\nКак часто напоминать?",
            reply_markup=markup
        )
        return

    if step == "waiting_custom_interval":
        interval_type, interval_value = parse_custom_interval(message.text)
        if interval_type is None:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))
            bot.send_message(
                message.chat.id,
                "Неверный формат. Напиши число и единицу.\n\nПримеры:\n30 минут\n2 часа\n1488 дней\n2 недели\n6 месяцев\n1 год",
                reply_markup=markup
            )
            return

        user_data[uid]["interval_type"] = interval_type
        user_data[uid]["interval_value"] = interval_value

        event_text = user_data[uid]["event_text"]
        interval_str = format_interval({"interval_type": interval_type, "interval_value": interval_value})

        user_data[uid]["step"] = "waiting_start"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Сейчас", callback_data="start_now"),
            types.InlineKeyboardButton("Завтра", callback_data="start_tomorrow"),
        )
        markup.add(
            types.InlineKeyboardButton("Послезавтра", callback_data="start_aftertomorrow"),
            types.InlineKeyboardButton("Свой вариант", callback_data="start_custom"),
        )
        markup.add(
            types.InlineKeyboardButton("Отмена", callback_data="back"),
        )

        bot.send_message(
            message.chat.id,
            f"Событие: \"{event_text}\"\n"
            f"Повтор: каждые {interval_str}\n\n"
            f"Когда первое напоминание?",
            reply_markup=markup
        )
        return

    if step == "waiting_custom_start":
        start = parse_start_date(message.text)
        if start is None:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Отмена", callback_data="back"))
            bot.send_message(
                message.chat.id,
                "Неверный формат даты.\n\nПримеры:\n"
                "сейчас\n"
                "завтра\n"
                "послезавтра\n"
                "через 5 дней\n"
                "через 2 часа\n"
                "через 30 минут\n"
                "15.09.2025\n"
                "15.09.2025 14:00\n"
                "15.09.2025 14:30:00",
                reply_markup=markup
            )
            return

        finish_event(message, uid, start)
        return


def reminder_checker():
    while True:
        try:
            events = load_events()
            now = now_msk()
            changed = False

            for uid, user_events in events.items():
                for event in user_events:
                    next_remind = parse_next_reminder(event)
                    if now >= next_remind:
                        try:
                            bot.send_message(
                                int(uid),
                                f"Напоминание: {event['text']}\n(каждые {format_interval(event)})"
                            )
                        except Exception as e:
                            print(f"Ошибка отправки для {uid}: {e}")
                        advance_reminder(event)
                        changed = True

            if changed:
                save_events(events)

        except Exception as e:
            print(f"Ошибка в reminder_checker: {e}")

        time.sleep(1)


if __name__ == "__main__":
    print("Бот запущен")
    t = threading.Thread(target=reminder_checker, daemon=True)
    t.start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
