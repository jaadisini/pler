import asyncio
import logging
from pyrogram import idle
from app import app
from database import init_db

import handler.admin
import handler.backup
import handler.payment
import handler.user

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def start():
    await init_db()
    
    # Mulai Bot
    await app.start()
    print("Bot Started")

    # Menjaga bot tetap hidup
    await idle()

    # Hentikan bot dengan aman saat keluar
    await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("Bot dihentikan oleh user.")
