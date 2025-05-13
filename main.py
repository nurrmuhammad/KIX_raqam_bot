import asyncio
import json
import os
import re
from datetime import datetime
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    LabeledPrice, PreCheckoutQuery
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configs
TOKEN = "7978939540:AAHSCAEr0ofNybS84I9RNaTHi1wGeL38zLs"
ADMIN_ID = 7133850731
PAYMENT_PROVIDER_TOKEN = "398062629:TEST:999999999_F91D8F69C042267444B74CC0B3C747757EB0E065"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Files
raqamlar_file = "raqamlar.json"
buyurtmalar_file = "buyurtmalar.json"
users_file = "users.json"

class AddNumber(StatesGroup):
    waiting_for_number = State()
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_price = State()

def load_data(filename, default):
    if not os.path.exists(filename): return default
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return default

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_numbers(): return load_data(raqamlar_file, [])

def get_main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📱 Telefon raqamlar")],
        [KeyboardButton(text="📦 Mening buyurtmalarim")]
    ])

@dp.message(CommandStart())
async def start(message: Message):
    users = load_data(users_file, [])
    user_id = message.from_user.id
    if all(u.get("id") != user_id for u in users):
        users.append({"id": user_id, "name": message.from_user.full_name, "username": message.from_user.username})
        save_data(users_file, users)
    await message.answer("Assalomu alaykum!", reply_markup=get_main_menu())

@dp.message(F.text == "📱 Telefon raqamlar")
async def show_all_numbers(message: Message):
    numbers = load_numbers()
    if not numbers:
        return await message.answer("Raqamlar mavjud emas.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Sotib olish: {n['number']}", callback_data=f"buy_{n['number']}")]
        for n in numbers
    ])
    await message.answer("Mavjud raqamlar:", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def process_buy_with_invoice(callback: types.CallbackQuery):
    number = callback.data.replace("buy_", "")
    numbers = load_numbers()
    for num in numbers:
        if num["number"] == number:
            title = f"Raqam: {num['number']}"
            description = f"{num['number']} raqamini sotib olish"
            prices = [LabeledPrice(label=title, amount=num["price"] * 100)]
            payload = f"{callback.from_user.id}_{num['number']}_{datetime.now().timestamp()}"
            await bot.send_invoice(
                chat_id=callback.from_user.id,
                title=title,
                description=description,
                payload=payload,
                provider_token=PAYMENT_PROVIDER_TOKEN,
                currency="UZS",
                prices=prices,
                start_parameter="buy-number"
            )
            await callback.message.delete()
            return
    await callback.message.answer("❌ Raqam topilmadi.")

@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    await message.answer("✅ To‘lov muvaffaqiyatli amalga oshirildi! Raqamingiz tez orada tasdiqlanadi.")
    # Buyurtmani yozish yoki adminga habar yuborish mumkin

@dp.message(F.text == "📦 Mening buyurtmalarim")
async def my_orders(message: Message):
    await message.answer("Sizning buyurtmalaringiz hozircha mavjud emas.")

# ADMIN
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Sizga ruxsat yo'q!")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="➕ Raqam qo'shish")],
        [KeyboardButton(text="🔙 Asosiy menyu")]
    ])
    await message.answer("Admin panelga xush kelibsiz!", reply_markup=keyboard)

@dp.message(F.text == "➕ Raqam qo'shish")
async def add_number_start(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Sizga ruxsat yo'q!")
    await message.answer("Raqamni kiriting (+99811 bilan):")
    await state.set_state(AddNumber.waiting_for_number)

@dp.message(AddNumber.waiting_for_number)
async def process_number(message: Message, state: FSMContext):
    number = message.text.strip()
    if not re.match(r"^\+99811\d{7}$", number):
        return await message.answer("❌ Notog'ri format. +99811 bilan kiriting")
    numbers = load_numbers()
    if any(n["number"] == number for n in numbers):
        return await message.answer("❌ Bu raqam allaqachon mavjud")
    await state.update_data(number=number)
    await message.answer("Ismni kiriting:")
    await state.set_state(AddNumber.waiting_for_name)

@dp.message(AddNumber.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Yoshni kiriting:")
    await state.set_state(AddNumber.waiting_for_age)

@dp.message(AddNumber.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Faqat raqam kiriting")
    await state.update_data(age=int(message.text.strip()))
    await message.answer("Narxni kiriting (so'm):")
    await state.set_state(AddNumber.waiting_for_price)

@dp.message(AddNumber.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Faqat raqam kiriting")
    data = await state.get_data()
    price = int(message.text.strip())
    numbers = load_numbers()
    numbers.append({
        "number": data["number"],
        "name": data["name"],
        "age": data["age"],
        "price": price,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_data(raqamlar_file, numbers)
    await message.answer("✅ Raqam qo'shildi")
    await state.clear()

@dp.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message):
    await start(message)

async def main():
    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
 