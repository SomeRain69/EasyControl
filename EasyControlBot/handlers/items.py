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


# Кнопка "Назад в меню"
@router.callback_query(F.data == "btn_back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from EasyControlBot.handlers.start import get_main_menu_keyboard
    await callback.message.answer("👋 <b>Главное меню:</b>\n\nВыбери нужное действие:",
                                  reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()


# 1. Шаг добавления товара
@router.callback_query(F.data == "btn_add")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="btn_back_to_menu")]
    ])
    await callback.message.answer("✏️ Введите название товара:", reply_markup=keyboard)
    await state.set_state(AddItemState.waiting_for_name)
    await callback.answer()


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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="btn_back_to_menu")]
    ])
    await message.answer("📅 Введите срок годности в формате <b>ДД.ММ.ГГГГ</b>:", reply_markup=keyboard,
                         parse_mode="HTML")
    await state.set_state(AddItemState.waiting_for_date)


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

    from EasyControlBot.handlers.start import get_main_menu_keyboard
    await message.answer(
        f"✅ Товар <b>«{item_name}»</b> (годен до {date_text}) успешно добавлен!",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()


# 2. Просмотр списка с кнопкой удаления для каждого товара
@router.callback_query(F.data == "btn_items")
async def show_items(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session_maker() as session:
        result = await session.execute(
            select(ItemModel).where(ItemModel.user_id == user_id)
        )
        items = result.scalars().all()

        if not items:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="btn_back_to_menu")]
            ])
            await callback.message.answer("📦 Ваш список товаров пока пуст.", reply_markup=keyboard)
            await callback.answer()
            return

        keyboard_buttons = []
        text = "📋 <b>Ваши товары:</b>\n\n"
        for item in items:
            text += f"▪️ <b>{item.name}</b> — годен до {item.expires_at}\n"
            keyboard_buttons.append([
                InlineKeyboardButton(text=f"❌ Удалить: {item.name}", callback_data=f"del_item_{item.id}")
            ])

        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="btn_back_to_menu")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()


# 3. Удаление конкретного товара по кнопке
@router.callback_query(F.data.startswith("del_item_"))
async def delete_single_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[2])
    async with async_session_maker() as session:
        await session.execute(delete(ItemModel).where(ItemModel.id == item_id))
        await session.commit()

    await callback.message.answer("🗑 Товар успешно удален из базы!")
    await callback.answer()

    # Переоткрываем обновленный список
    await show_items(callback)