from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select, delete
from datetime import datetime

from database.database import async_session_maker
from database.models import ItemModel

router = Router()


def get_back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main")]
        ]
    )


class AddItemState(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()


# 1. НАЖАТИЕ "ДОБАВИТЬ ТОВАР"
@router.callback_query(F.data == "btn_add")
async def start_add_item(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("✍️ <b>Введите название товара:</b>", reply_markup=get_back_keyboard(),
                                     parse_mode="HTML")
    await state.set_state(AddItemState.waiting_for_name)
    await callback.answer()


# 2. ПОЛУЧАЕМ НАЗВАНИЕ
@router.message(AddItemState.waiting_for_name)
async def process_item_name(message: Message, state: FSMContext):
    await state.update_data(item_name=message.text)

    try:
        await message.delete()
    except Exception:
        pass

    msg = await message.answer(
        "📅 <b>Введите дату окончания срока годности</b> (обязательно в формате ДД.ММ.ГГГГ, например: <i>01.12.2026</i>):",
        parse_mode="HTML")
    await state.update_data(prompt_msg_id=msg.message_id)
    await state.set_state(AddItemState.waiting_for_date)


# 3. ПОЛУЧАЕМ ДАТУ С ПРОВЕРКОЙ НА СПАМ/ФОРМАТ
@router.message(AddItemState.waiting_for_date)
async def process_item_date(message: Message, state: FSMContext):
    user_data = await state.get_data()
    item_name = user_data.get("item_name")
    prompt_msg_id = user_data.get("prompt_msg_id")
    item_date_str = message.text.strip()
    user_id = message.from_user.id

    # Проверяем, соответствует ли введенный текст формату ДД.ММ.ГГГГ
    try:
        # Пытаемся распарсить дату
        datetime.strptime(item_date_str, "%d.%m.%Y")
    except ValueError:
        # Если формат неверный — удаляем мусорное сообщение пользователя
        try:
            await message.delete()
        except Exception:
            pass

        # Просим ввести дату заново, не сбрасывая состояние
        error_msg = await message.answer(
            "❌ <b>Неверный формат даты!</b>\nПожалуйста, введите дату строго в формате <b>ДД.ММ.ГГГГ</b> (например: <i>15.06.2026</i>):",
            parse_mode="HTML"
        )
        return

    # Удаляем сообщение с правильной датой от пользователя
    try:
        await message.delete()
    except Exception:
        pass

    # Удаляем старый запрос бота
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
    except Exception:
        pass

    # Сохраняем в базу данных
    async with async_session_maker() as session:
        new_item = ItemModel(
            user_id=user_id,
            name=item_name,
            expires_at=item_date_str
        )
        session.add(new_item)
        await session.commit()

    await message.answer(
        f"✅ Товар <b>«{item_name}»</b> (до {item_date_str}) успешно сохранен!",
        reply_markup=get_back_keyboard(),
        parse_mode="HTML"
    )
    await state.clear()


# 4. МОИ ТОВАРЫ
@router.callback_query(F.data == "btn_items")
async def show_items(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with async_session_maker() as session:
        result = await session.execute(select(ItemModel).where(ItemModel.user_id == user_id))
        items = result.scalars().all()

    if not items:
        text = "📋 <b>Ваши товары:</b>\n\nУ вас пока нет сохраненных товаров."
        await callback.message.edit_text(text, reply_markup=get_back_keyboard(), parse_mode="HTML")
    else:
        items_text = "\n".join([f"• <b>{item.name}</b> — до {item.expires_at}" for item in items])
        text = f"📋 <b>Ваши товары:</b>\n\n{items_text}\n\n<i>Нажмите на кнопку ниже, чтобы удалить товар:</i>"

        keyboard_buttons = []
        for item in items:
            btn_text = f"❌ Удалить: {item.name} ({item.expires_at})"
            keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"del_{item.id}")])

        keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main")])

        items_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await callback.message.edit_text(text, reply_markup=items_keyboard, parse_mode="HTML")

    await callback.answer()


# 5. УДАЛЕНИЕ ТОВАРА
@router.callback_query(F.data.startswith("del_"))
async def delete_single_item(callback: CallbackQuery):
    item_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id

    async with async_session_maker() as session:
        await session.execute(
            delete(ItemModel).where(ItemModel.id == item_id, ItemModel.user_id == user_id)
        )
        await session.commit()

    await callback.answer("🗑 Товар удален!")
    await show_items(callback)


# 6. ВОЗВРАТ В МЕНЮ
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from handlers.start import get_main_menu_keyboard
    await callback.message.edit_text(
        "👋 <b>Главное меню:</b>\n\nВыбери нужное действие:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()