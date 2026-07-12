import asyncio
import logging
from pyrogram import Client
from config import BOT_TOKEN, API_ID, API_HASH
from database import init_db
from tasks.payment_checker import PaymentChecker

# Import handler agar dekorator terdaftar otomatis
import handler.admin
import handler.backup
import handler.payment
import handler.user

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def main():
    await init_db()
    app = Client("naka_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    # Inisialisasi Checker
    checker = PaymentChecker(app)
    app.payment_checker = checker
    asyncio.create_task(checker.start())
    
    await app.start()
    print("Bot berhasil berjalan!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
