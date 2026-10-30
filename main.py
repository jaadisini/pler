import asyncio
import logging
from pyrogram import idle
from app import app
from config import OWNER_ID
from database import init_db

# Import handler Anda
import handler.admin
import handler.backup
import handler.payment
import handler.user

# Konfigurasi logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def send_startup_notification(client):
    """Mengirim pesan notifikasi ke owner bahwa bot telah aktif."""
    try:
        me = await client.get_me()
        text = (
            "🚀 **Bot Berhasil Diaktifkan!**\n\n"
            f"🤖 **Nama Bot:** @{me.username}\n"
            f"🆔 **ID Bot:** `{me.id}`\n"
            f"🟢 **Status:** Online & Siap digunakan."
        )
        await client.send_message(OWNER_ID, text)
        logger.info("Notifikasi startup berhasil dikirim ke owner.")
    except Exception as e:
        logger.error(f"Gagal mengirim notifikasi ke owner: {e}")

async def start():
    # Inisialisasi Database
    await init_db()
    logger.info("Database berhasil diinisialisasi.")
    
    # Mulai Bot Pyrogram
    await app.start()
    
    # Tampilan Banner Cantik di Console/Terminal
    banner = """
    ╔══════════════════════════════════════════╗
    ║               BOT STARTED                ║
    ║        Powered by Pyrogram & Python      ║
    ╚══════════════════════════════════════════╝
    """
    print(banner)
    logger.info("Bot Telegram Anda kini sedang berjalan...")

    # Kirim notifikasi ke owner
    await send_startup_notification(app)

    # Menjaga bot tetap hidup
    await idle()

    # Hentikan bot dengan aman saat keluar
    await app.stop()
    logger.info("Bot dihentikan dengan aman.")

if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("\n[!] Bot dihentikan oleh user (KeyboardInterrupt).")
