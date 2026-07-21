import asyncio
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://kamran-life.kamranbek.chatgpt.site")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
DATABASE_PATH = os.getenv("DATABASE_PATH", "kamran_life_bot.sqlite3")
REMINDERS = {
    "08:00": "Доброе утро! Внесите сон, вес, самочувствие и планы на день.",
    "14:00": "Дневной чек-ин: внесите расходы, питание и воду за первую половину дня.",
    "21:30": "Вечерний чек-ин: внесите тренировку, питание, настроение и итог дня.",
}

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def db():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, reminders INTEGER NOT NULL DEFAULT 1)")
    connection.execute("CREATE TABLE IF NOT EXISTS sent (chat_id INTEGER, day TEXT, time TEXT, PRIMARY KEY(chat_id, day, time))")
    return connection


def app_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Открыть Kamran Life", web_app=WebAppInfo(url=WEB_APP_URL))]])


@dp.message(CommandStart())
async def start(message: Message):
    with db() as connection:
        connection.execute("INSERT OR IGNORE INTO users(chat_id) VALUES (?)", (message.chat.id,))
    await message.answer("Личный трекер финансов, здоровья и привычек.", reply_markup=app_keyboard())


@dp.message(Command("app"))
async def open_app(message: Message):
    await message.answer("Открыть приложение:", reply_markup=app_keyboard())


@dp.message(Command("reminders_on"))
async def reminders_on(message: Message):
    with db() as connection:
        connection.execute("INSERT INTO users(chat_id, reminders) VALUES (?, 1) ON CONFLICT(chat_id) DO UPDATE SET reminders=1", (message.chat.id,))
    await message.answer("Напоминания включены: 08:00, 14:00 и 21:30.")


@dp.message(Command("reminders_off"))
async def reminders_off(message: Message):
    with db() as connection:
        connection.execute("INSERT INTO users(chat_id, reminders) VALUES (?, 0) ON CONFLICT(chat_id) DO UPDATE SET reminders=0", (message.chat.id,))
    await message.answer("Напоминания выключены.")


@dp.message(F.web_app_data)
async def web_app_data(message: Message):
    await message.answer("Данные сохранены в приложении.")


async def send_due_reminders():
    now = datetime.now(ZoneInfo(TIMEZONE))
    time_key, day_key = now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
    text = REMINDERS.get(time_key)
    if not text:
        return
    with db() as connection:
        users = connection.execute("SELECT chat_id FROM users WHERE reminders=1").fetchall()
        for (chat_id,) in users:
            already_sent = connection.execute("SELECT 1 FROM sent WHERE chat_id=? AND day=? AND time=?", (chat_id, day_key, time_key)).fetchone()
            if already_sent:
                continue
            try:
                await bot.send_message(chat_id, text, reply_markup=app_keyboard())
                connection.execute("INSERT INTO sent(chat_id, day, time) VALUES (?, ?, ?)", (chat_id, day_key, time_key))
            except Exception:
                pass


async def main():
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_due_reminders, "interval", minutes=1, max_instances=1)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
