import os
import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# API Tokens (Render Environment Variables se aayenge)
API_TOKEN = os.getenv('MOTHER_BOT_TOKEN')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- UI Buttons ---
def main_menu():
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("🛍️ I am a Buyer", callback_data="buyer_home"),
        InlineKeyboardButton("⚙️ I am a Seller", callback_data="seller_home")
    )

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply(
        "Welcome to the Marketplace! \n\nPlease select your role:",
        reply_markup=main_menu()
    )

@dp.callback_query_handler(text="seller_home")
async def seller_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("➕ Add Product", callback_data="add_item"),
        InlineKeyboardButton("📦 My Sales", callback_data="my_sales")
    )
    await call.message.edit_text("👨‍💼 **Seller Dashboard**\nManage your shop here:", reply_markup=kb)

@dp.callback_query_handler(text="buyer_home")
async def buyer_menu(call: types.CallbackQuery):
    await call.message.edit_text("🛒 **Buyer Mode**\nListing all products from our sellers...")
    # Yahan database se products fetch karne ka code aayega

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
