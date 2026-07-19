import logging
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime

# Import dari project kamu
from app import app
from database import init_db, get_channel, get_order, update_order_status
from tasks.payment_checker import PaymentChecker
from config import LOGGER_GROUP_ID

# Import handler agar dekorator terdaftar otomatis
import handler.admin
import handler.backup
import handler.payment
import handler.user

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# =====================================
# LIFESPAN (PENGGANTI app.run & idle)
# =====================================
@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # --- PROSES STARTUP ---
    logging.info("Memulai Database...")
    await init_db()

    logging.info("Memulai Payment Checker...")
    checker = PaymentChecker(app)
    app.payment_checker = checker
    # Jalankan sebagai background task
    checker_task = asyncio.create_task(checker.start())

    logging.info("Memulai Bot Pyrogram...")
    await app.start()
    logging.info("✅ Bot dan Webhook Berhasil Berjalan!")

    yield  # Server FastAPI menahan program agar tetap hidup di titik ini

    # --- PROSES SHUTDOWN (Saat dihentikan / Ctrl+C) ---
    logging.info("Mematikan proses...")
    checker_task.cancel()  # Hentikan task checker
    await app.stop()       # Matikan bot dengan aman
    logging.info("🛑 Bot Berhenti.")

# Inisialisasi Web App dengan lifespan
web_app = FastAPI(lifespan=lifespan)


# =====================================
# ENDPOINT WEBHOOK
# =====================================
@web_app.post("/webhook/casaku")
async def casaku_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Sesuaikan key dengan dokumentasi Casaku (transactionId atau reference)
    transaction_id = data.get("transactionId") or data.get("reference")
    status = data.get("status", "").lower()

    if not transaction_id:
        return {"status": "error", "message": "Missing transaction_id"}

    order = await get_order(transaction_id)
    if not order:
        return {"status": "error", "message": "Order not found"}

    # Cegah double notifikasi jika sudah paid
    if order.get("status") == "paid":
        return {"status": "success", "message": "Already processed"}

    # Jika sukses
    if status in ["paid", "success", "settlement"]:
        await update_order_status(transaction_id, "paid")
        
        channel = await get_channel(order['channel_id'])
        user_id = order['user_id']
        user = await app.get_users(user_id)
        
        invite = await app.create_chat_invite_link(
            chat_id=int(channel['channel_id']),
            member_limit=1
        )
        
        # 1. Kirim notifikasi ke User
        try:
            msg = f"✅ **PEMBAYARAN OTOMATIS BERHASIL**\n\nTerima kasih, ini link akses VIP kamu:\n{invite.invite_link}"
            await app.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logging.error(f"Gagal kirim link ke {user_id}: {e}")

        # 2. Kirim Log Testimoni ke Grup
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        log_text = (
            "🔔 <b>TESTIMONI — NAKA VIP (AUTO)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🗓 <b>Tanggal:</b> {waktu}\n"
            f"👤 <b>Buyer:</b> {full_name}\n"
            f"🆔 <b>ID Buyer:</b> <code>{user.id}</code>\n"
            f"📨 <b>Username:</b> @{user.username or '-'}\n"
            f"🛍 <b>VIP:</b> {channel['name']}\n"
            f"🧾 <b>Order ID:</b> <code>{transaction_id}</code>\n"
            f"💰 <b>Total:</b> Rp {order['unique_amount']:,}\n"
            "🏦 <b>Metode:</b> QRIS\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Terima kasih sudah order layanan bot VIP kami."
        )
        
        bot_info = await app.get_me()
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        log_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Hubungi Bot", url=f"https://t.me/{bot_info.username}")]
        ])
        
        try:
            await app.send_message(chat_id=LOGGER_GROUP_ID, text=log_text, reply_markup=log_keyboard)
        except Exception as log_error:
            logging.error(f"Gagal kirim log ke grup: {log_error}")

        return {"status": "success"}

    elif status in ["expired", "failed", "cancel"]:
        await update_order_status(transaction_id, status)
        try:
            await app.send_message(chat_id=order['user_id'], text=f"❌ Pesanan `{transaction_id}` **{status.upper()}**.")
        except:
            pass
        return {"status": "success", "message": "Updated to failed"}

    return {"status": "ignored"}


if __name__ == "__main__":
    # PERHATIKAN: ganti 'main' dengan nama file kamu (tanpa .py)
    # Misal jika nama file ini app.py, ganti menjadi "app:web_app"
    uvicorn.run("main:web_app", host="0.0.0.0", port=8000, reload=False)
