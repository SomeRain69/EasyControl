from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete
from datetime import datetime

from database.database import async_session_maker
from database.models import ItemModel

router = Router()


class AddItemState(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()


# 1. Кнопка "Добавить товар"
@router.callback_query(F.data == "add_item")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("✏️ Введите название товара:")
    await state.set_state(AddItemState.waiting_for_name)
    await callback.answer()


# 2. Получаем название и СРАЗУ проверяем на дубликаты
@router.message(AddItemState.waiting_for_name)
async def process_item_name(message: Message, state: FSMContext):
    item_name = message.text.strip()
    user_id = message.from_user.id

    async with async_session_maker() as session:
        result = await session.execute(
            select(ItemModel).where(ItemModel.user_id == user_id, ItemModel.name == item_name)
        )
        existing_item = result.scalar_one_or_none()

        if existing_item:
            await message.answer(
                f"❌ Товар с названием <b>«{item_name}»</b> уже есть в вашей базе!",
                parse_mode="HTML"
            )
            return

    await state.update_data(item_name=item_name)
    await message.answer("📅 Введите срок годности в формате <b>ДД.ММ.ГГГГ</b>:", parse_mode="HTML")
    await state.set_state(AddItemState.waiting_for_date)


# 3. Получаем дату, проверяем на просрочку и сохраняем
@router.message(AddItemState.waiting_for_date)
async def process_item_date(message: Message, state: FSMContext):
    date_text = message.text.strip()

    try:
        exp_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        today = datetime.now().date()

        if exp_date < today:
            await message.answer(
                "⚠️ Этот товар уже <b>просрочен</b>! Нельзя добавить товар с истекшим сроком годности.",
                parse_mode="HTML"
            )
            return

    except ValueError:
        await message.answer("❌ Неверный формат даты! Пожалуйста, используйте формат <b>ДД.ММ.ГГГГ</b>.",
                             parse_mode="HTML")
        return

    data = await state.get_data()
    item_name = data.get("item_name")
    user_id = message.from_user.id

    async with async_session_maker() as session:
        new_item = ItemModel(
            user_id=user_id,
            name=item_name,
            expires_at=date_text,
            notified_14_days=0
        )
        session.add(new_item)
        await session.commit()

    await message.answer(f"✅ Товар <b>«{item_name}»</b> (годен до {date_text}) успешно добавлен!", parse_mode="HTML")
    await state.clear()


# 4. Кнопка "Список товаров" (просмотр)
@router.callback_query(F.data == "list_items")
async def show_items(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(
            select(ItemModel).where(ItemModel.user_id == user_id)
        )
        items = result.scalars().all()

        if not items:
            await callback.message.answer("📦 Ваш список товаров пока пуст.")
            await callback.answer()
            return

        text = "📋 <b>Ваши товары:</b>\n\n"
        for item in items:
            text += f"▪️ <b>{item.name}</b> — годен до {item.expires_at}\n"

        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()