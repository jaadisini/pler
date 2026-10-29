import asyncio
import logging
from pyrogram import idle

from app import app
from database import init_db
# from tasks.payment_checker import PaymentChecker

# Import handler agar dekorator terdaftar otomatis
import handler.admin
import handler.backup
import handler.payment
import handler.user

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def start():
    # Inisialisasi Database
    await init_db()
    # Inisialisasi dan jalankan Payment Checker
    # checker = PaymentChecker(app)
    # app.payment_checker = checker
    # asyncio.create_task(checker.start())

    # Mulai Bot
    await app.start()
    print("Bot Started")

    # Menjaga bot tetap berjalan sampai ada interupsi (misal: Ctrl+C)
    await idle()

    # Proses penghentian bot dan penutupan database dengan aman
    await app.stop()
    

if __name__ == "__main__":
    # Gunakan asyncio.run() untuk menjalankan coroutine start() dengan benar
    asyncio.run(start())
