import os
import logging
import asyncio
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, types, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from motor.motor_asyncio import AsyncIOMotorClient

# --- RENDER WEB SERVICE PORT FIX ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is Running!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT SETUP ---
API_TOKEN = os.getenv('MOTHER_BOT_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- DATABASE CONNECTION ---
client = AsyncIOMotorClient(MONGO_URL)
db = client["market_database"]
products_col = db["products"]

# --- STATES FOR ADDING PRODUCT ---
class AddProduct(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_price = State()

# --- KEYBOARDS ---
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛍️ I am a Buyer", callback_data="role_buyer"),
        types.InlineKeyboardButton("⚙️ I am a Seller", callback_data="role_seller")
    )
    return kb

def seller_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ Add New Product", callback_data="add_item"),
        types.InlineKeyboardButton("📦 View My Products", callback_data="view_my_items"),
        types.InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")
    )
    return kb

# --- HANDLERS ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.reply(
        "🚀 **Welcome to MarketMaster!**\n\nThe most advanced marketplace bot. "
        "Choose your role to get started:",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(text="role_seller")
async def seller_home(call: types.CallbackQuery):
    await call.message.edit_text(
        "👨‍💼 **Seller Dashboard**\nManage your store and products below:",
        reply_markup=seller_menu(),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(text="role_buyer")
async def buyer_home(call: types.CallbackQuery):
    await call.answer("Loading Marketplace...", show_alert=False)
    # Fetch products from MongoDB
    products = await products_col.find().to_list(length=10)
    if not products:
        await call.message.edit_text("🛒 **Marketplace**\n\nNo products listed yet. Check back later!")
    else:
        await call.message.edit_text("🛒 **Marketplace**\n\nShowing latest products:")
        for p in products:
            await bot.send_photo(
                call.from_user.id, 
                p['photo'], 
                caption=f"📦 *Name:* {p['name']}\n💰 *Price:* {p['price']}\n\n[ 🛒 Buy Now ]",
                parse_mode="Markdown"
            )

# --- PRODUCT ADDING LOGIC (SELLER) ---

@dp.callback_query_handler(text="add_item")
async def start_add_item(call: types.CallbackQuery):
    await AddProduct.waiting_for_photo.set()
    await call.message.answer("📸 Please send the **Product Photo**:")

@dp.message_handler(content_types=['photo'], state=AddProduct.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await AddProduct.next()
    await message.answer("📝 Enter the **Product Name**:")

@dp.message_handler(state=AddProduct.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AddProduct.next()
    await message.answer("💰 Enter the **Price** (e.g. $50 or 1000 INR):")

@dp.message_handler(state=AddProduct.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    # Save to MongoDB
    product = {
        "seller_id": message.from_user.id,
        "photo": user_data['photo'],
        "name": user_data['name'],
        "price": message.text
    }
    await products_col.insert_one(product)
    
    await message.answer("✅ **Product added successfully!** It is now live in the marketplace.")
    await state.finish()

# --- START BOT ---
if __name__ == '__main__':
    keep_alive() # Starts Flask server for Render Port Fix
    executor.start_polling(dp, skip_updates=True)
    
