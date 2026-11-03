from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить товар", callback_data="btn_add")],
            [InlineKeyboardButton(text="📋 Мои товары", callback_data="btn_items")],
            [InlineKeyboardButton(text="🗑 Очистить список товаров", callback_data="btn_clear")]
        ]
    )

@router.message(F.text == "/start")
async def cmd_start(message: Message):
    text = "👋 <b>Главное меню:</b>\n\nВыбери нужное действие:"
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")