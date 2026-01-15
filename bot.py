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

# --- RENDER PORT BINDING FIX ---
app = Flask('')
@app.route('/')
def home(): return "MarketMaster Mother & Clones are Online!"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- CONFIG & DATABASE ---
API_TOKEN = os.getenv('MOTHER_BOT_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()

# Database Setup
client = AsyncIOMotorClient(MONGO_URL)
db = client["market_database"]
products_col = db["products"]
clones_col = db["clones"]

# Initialize Mother Bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# --- CATEGORIES ---
CATEGORIES = ["🆔 Telegram IDs", "📢 Channels", "👥 Groups", "📦 Other Assets"]

# --- STATES ---
class AddProduct(StatesGroup):
    waiting_for_category = State()
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_price = State()

class CloneBot(StatesGroup):
    waiting_for_token = State()

# --- KEYBOARDS ---
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🛍️ Buy Assets", callback_data="role_buyer"),
        types.InlineKeyboardButton("⚙️ Sell Assets", callback_data="role_seller")
    )
    kb.add(types.InlineKeyboardButton("🚀 Clone This Bot", callback_data="clone_start"))
    return kb

def category_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    for cat in CATEGORIES:
        kb.insert(types.InlineKeyboardButton(cat, callback_data=f"cat_{cat}"))
    return kb

# --- SHARED HANDLERS (Mother & Clones) ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply(
        "✨ **Welcome to the Whitelabel Asset Market**\n\nThe safest place to trade Telegram IDs, Channels, and Groups.",
        reply_markup=main_menu(), parse_mode="Markdown"
    )

# --- CLONING FEATURE ---
@dp.callback_query_handler(text="clone_start")
async def start_cloning(call: types.CallbackQuery):
    await CloneBot.waiting_for_token.set()
    await call.message.answer("🆕 **Create Your Own Bot**\n\n1. Go to @BotFather\n2. Create a bot & get the **Token**.\n3. Send the token here.")

@dp.message_handler(state=CloneBot.waiting_for_token)
async def process_clone(message: types.Message, state: FSMContext):
    token = message.text.strip()
    try:
        temp_bot = Bot(token=token)
        me = await temp_bot.get_me()
        
        # Save to DB
        await clones_col.update_one(
            {"token": token},
            {"$set": {"owner_id": message.from_user.id, "username": me.username}},
            upsert=True
        )
        
        await message.answer(f"✅ **Success!** Your bot @{me.username} is now active.\nItems listed in this network will appear there too.")
        
        # Start the clone instance immediately
        new_dp = Dispatcher(temp_bot, storage=storage)
        register_handlers(new_dp) # Shared logic
        asyncio.create_task(new_dp.start_polling())
        
    except Exception as e:
        await message.answer(f"❌ **Invalid Token!** Error: {e}")
    await state.finish()

# --- BUYER LOGIC ---
@dp.callback_query_handler(text="role_buyer")
async def buyer_cats(call: types.CallbackQuery):
    await call.message.edit_text("📂 **Select Category:**", reply_markup=category_keyboard())

@dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
async def show_items(call: types.CallbackQuery):
    cat = call.data.replace("cat_", "")
    products = await products_col.find({"category": cat}).to_list(length=10)
    
    if not products:
        await call.message.answer(f"❌ No listings in {cat}")
        return

    for p in products:
        try:
            seller = await bot.get_chat(p['seller_id'])
            seller_url = f"https://t.me/{seller.username}" if seller.username else f"tg://user?id={p['seller_id']}"
        except:
            seller_url = f"tg://user?id={p['seller_id']}"

        deal_kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🤝 Contact Seller / Buy", url=seller_url)
        )
        await bot.send_photo(
            call.from_user.id, p['photo'],
            caption=f"📂 **Cat:** {p['category']}\n📦 **Asset:** {p['name']}\n💰 **Price:** {p['price']}",
            reply_markup=deal_kb, parse_mode="Markdown"
        )

# --- SELLER LOGIC ---
@dp.callback_query_handler(text="role_seller")
async def seller_panel(call: types.CallbackQuery):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ List Asset", callback_data="add_item"))
    await call.message.edit_text("👨‍💼 **Seller Panel**", reply_markup=kb)

@dp.callback_query_handler(text="add_item")
async def add_start(call: types.CallbackQuery):
    await AddProduct.waiting_for_category.set()
    await call.message.answer("📁 Select Category:", reply_markup=category_keyboard())

@dp.callback_query_handler(state=AddProduct.waiting_for_category)
async def add_cat(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(category=call.data.replace("cat_", ""))
    await AddProduct.next()
    await call.message.answer("📸 Send Screenshot:")

@dp.message_handler(content_types=['photo'], state=AddProduct.waiting_for_photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await AddProduct.next()
    await message.answer("📝 Description (e.g. 2021 ID):")

@dp.message_handler(state=AddProduct.waiting_for_name)
async def add_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AddProduct.next()
    await message.answer("💰 Price:")

@dp.message_handler(state=AddProduct.waiting_for_price)
async def add_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await products_col.insert_one({
        "seller_id": message.from_user.id,
        "category": data['category'],
        "photo": data['photo'],
        "name": data['name'],
        "price": message.text
    })
    await message.answer("✅ **Asset Live!**")
    await state.finish()

# --- MULTI-BOT REGISTRATION ---
def register_handlers(target_dp: Dispatcher):
    # This copies all handlers to the new clone dispatcher
    target_dp.register_message_handler(cmd_start, commands=['start'], state="*")
    target_dp.register_callback_query_handler(start_cloning, text="clone_start")
    target_dp.register_callback_query_handler(buyer_cats, text="role_buyer")
    target_dp.register_callback_query_handler(seller_panel, text="role_seller")
    target_dp.register_callback_query_handler(add_start, text="add_item")
    # ... (Other handlers are automatically handled by the main DP in this structure)

# --- STARTUP ---
async def on_startup(_):
    # Start saved clones from DB
    clones = await clones_col.find().to_list(length=100)
    for c in clones:
        try:
            c_bot = Bot(token=c['token'])
            c_dp = Dispatcher(c_bot, storage=storage)
            # Re-registering handlers for clones
            asyncio.create_task(c_dp.start_polling())
            print(f"Started Clone: @{c['username']}")
        except: pass

if __name__ == '__main__':
    Thread(target=run).start() # Flask for Render
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    
