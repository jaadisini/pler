import asyncio
import logging
from pyrogram import Client, filters
from config import BOT_TOKEN, API_ID, API_HASH
from database import init_db
from tasks.payment_checker import PaymentChecker

# Pastikan handler di-import agar dekorator terdaftar
import handler.admin
import handler.backup
import handler.payment
import handler.user

# =====================================
# LOGGING
# =====================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =====================================
# MAIN
# =====================================

async def main():
    # 1. Inisialisasi Database
    await init_db()
    logger.info("Database initialized")

    # 2. Inisialisasi Client Pyrogram
    # Pastikan API_ID dan API_HASH ada di config.py
    app = Client(
        "my_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    # 3. Setup Payment Checker
    # Di Pyrogram, kita bisa menyimpan objek di 'app' sebagai atribut tambahan
    checker = PaymentChecker(app)
    app.payment_checker = checker
    
    asyncio.create_task(checker.start())
    logger.info("Payment checker started")

    # 4. Start Bot
    logger.info("Bot starting...")
    await app.start()
    
    # Mendapatkan informasi bot untuk logging
    me = await app.get_me()
    logger.info(f"Bot started as @{me.username}")
    
    # Menjaga proses tetap berjalan
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
