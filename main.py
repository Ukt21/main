
from __future__ import annotations

import os
import asyncio
import secrets
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import load_dotenv

from db import init_db, get_conn
from keyboards import rating_kb, skip_comment_kb

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MANAGERS_CHAT_ID = int(os.getenv("MANAGERS_CHAT_ID", "0"))
PROMO_VALID_DAYS = int(os.getenv("PROMO_VALID_DAYS", "30"))
DB_PATH = os.getenv("DB_PATH", "./bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty: укажите токен в .env")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# --- FSM ---
class FeedbackSG(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()

# --- Utils ---
def gen_promo_code(n: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(n))

async def send_manager_card(user: Message | CallbackQuery, rating: int, comment: str, promo_code: str, expires_at: datetime):
    uid = user.from_user.id
    uname = user.from_user.username or "-"
    text = (f"<b>Новый отзыв</b>\n"
            f"Гость: <code>{uid}</code> (@{uname})\n"
            f"Оценка: <b>{rating} ⭐️</b>\n"
            f"Комментарий: {comment if comment else '—'}\n"
            f"Промокод: <code>{promo_code}</code>\n"
            f"Действует до: <b>{expires_at.strftime('%Y-%m-%d')}</b>")
    if MANAGERS_CHAT_ID != 0:
        await bot.send_message(MANAGERS_CHAT_ID, text)

# --- Handlers ---
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! Оцените, пожалуйста, ваше посещение ресторана «Рибамбель».\n"
        "Выберите количество звёзд ⭐️ от 1 до 5:",
        reply_markup=rating_kb()
    )
    await state.set_state(FeedbackSG.waiting_rating)

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Я собираю оценку и обратную связь и отправляю её менеджерам.\n\n"
        "<b>Команды:</b>\n"
        "/start — начать заново\n"
        "/help — помощь\n"
        "/stats — статистика за 7 дней (для менеджеров)"
    )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    # простая статистика за 7 дней
    since = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    from statistics import mean
    try:
        from db import get_conn
        with get_conn(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("SELECT rating FROM feedback WHERE created_at >= ?", (since,))
            rows = cur.fetchall()
        count = len(rows)
        avg = round(mean([r[0] for r in rows]), 2) if rows else 0
        await message.answer(f"За последние 7 дней: {count} отзыв(ов). Средняя оценка: {avg}")
    except Exception as e:
        await message.answer(f"Не удалось получить статистику: {e}")

@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(call: CallbackQuery, state: FSMContext):
    if not await state.get_state():
        await state.set_state(FeedbackSG.waiting_rating)
    try:
        rating = int(call.data.split(":")[1])
    except Exception:
        await call.answer("Ошибка рейтинга", show_alert=True)
        return

    await state.update_data(rating=rating)
    await call.message.edit_text(
        f"Спасибо за оценку: <b>{rating} ⭐️</b>\n"
        "Оставьте, пожалуйста, короткий комментарий (что понравилось/что улучшить).",
    )
    await call.message.answer("Если хотите пропустить комментарий — нажмите кнопку:", reply_markup=skip_comment_kb())
    await state.set_state(FeedbackSG.waiting_comment)
    await call.answer()

@router.callback_query(F.data == "skip_comment")
async def cb_skip_comment(call: CallbackQuery, state: FSMContext):
    await process_feedback_and_finish(call.message, state, comment="")
    await call.answer()

@router.message(FeedbackSG.waiting_comment)
async def got_comment(message: Message, state: FSMContext):
    comment = (message.text or "").strip()
    await process_feedback_and_finish(message, state, comment=comment)

async def process_feedback_and_finish(message_or_callmsg: Message, state: FSMContext, comment: str):
    data = await state.get_data()
    rating = data.get("rating")
    if rating is None:
        await message_or_callmsg.answer("Похоже, мы потеряли этап с оценкой. Нажмите /start и попробуем ещё раз.")
        return

    # генерируем промокод
    promo_code = gen_promo_code()
    expires_at = datetime.utcnow() + timedelta(days=PROMO_VALID_DAYS)

    # сохраняем в БД
    from db import get_conn
    with get_conn(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feedback (user_id, username, rating, comment, promo_code, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_or_callmsg.from_user.id,
                message_or_callmsg.from_user.username,
                rating,
                comment,
                promo_code,
                expires_at.strftime("%Y-%m-%d"),
            )
        )
        conn.commit()

    # отправляем менеджерам
    await send_manager_card(message_or_callmsg, rating, comment, promo_code, expires_at)

    # отвечаем гостю
    await message_or_callmsg.answer(
        "Спасибо за обратную связь! 💚\n"
        f"Ваш персональный промокод: <code>{promo_code}</code>\n"
        f"Срок действия до: <b>{expires_at.strftime('%Y-%m-%d')}</b>\n\n"
        "Покажите этот код вашему официанту при следующем посещении."
    )

    await state.clear()

async def on_startup():
    init_db(DB_PATH)

async def main():
    await on_startup()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
