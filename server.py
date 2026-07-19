import asyncio
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from pyrogram import Client
from datetime import datetime

# Import fungsi database dan bot kamu
from database import get_channel, get_order, update_order_status
from config import LOGGER_GROUP_ID
from app import app  # Import instance Pyrogram-mu

# Inisialisasi FastAPI
web_app = FastAPI()

# =====================================
# ENDPOINT WEBHOOK
# =====================================
@web_app.post("/webhook/casaku")
async def casaku_webhook(request: Request):
    try:
        # Ambil payload JSON dari Casaku
        data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Sesuaikan key 'transactionId' dan 'status' dengan dokumentasi asli Casaku
    transaction_id = data.get("transactionId") or data.get("reference")
    status = data.get("status", "").lower()

    if not transaction_id:
        return {"status": "error", "message": "Missing transaction_id"}

    # Cek order di database
    order = await get_order(transaction_id)
    if not order:
        return {"status": "error", "message": "Order not found"}

    # Jika order sudah berstatus 'paid', abaikan webhook ini (mencegah double process)
    if order.get("status") == "paid":
        return {"status": "success", "message": "Already paid"}

    # Jika status pembayaran berhasil
    if status in ["paid", "success", "settlement"]:
        # Update status di database
        await update_order_status(transaction_id, "paid")
        
        channel = await get_channel(order['channel_id'])
        user_id = order['user_id']
        
        # Dapatkan data user dari Telegram (karena webhook tidak memiliki callback_query)
        user = await app.get_users(user_id)
        
        # Generate invite link
        invite = await app.create_chat_invite_link(
            chat_id=int(channel['channel_id']),
            member_limit=1
        )
        
        # 1. Kirim notifikasi sukses ke User
        try:
            success_msg = f"✅ **PEMBAYARAN OTOMATIS BERHASIL**\n\nTerima kasih, ini link akses VIP kamu:\n{invite.invite_link}"
            await app.send_message(chat_id=user_id, text=success_msg)
        except Exception as e:
            print(f"Gagal mengirim link ke user {user_id}: {e}")

        # 2. Kirim Log / Testimoni ke Grup
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        channel_name = channel['name']
        unique_amount = order['unique_amount']
        
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
            f"🛍 <b>VIP:</b> {channel_name}\n"
            f"🧾 <b>Order ID:</b> <code>{transaction_id}</code>\n"
            f"💰 <b>Total:</b> Rp {unique_amount:,}\n"
            "🏦 <b>Metode:</b> QRIS\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Terima kasih sudah order layanan bot VIP kami.\n\n"
            "👋🏻 <b>Pengen Order Cepat?</b>\n"
            "Silakan klik tombol di bawah 👇"
        )
        
        bot_info = await app.get_me()
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        log_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Hubungi Bot / Order", url=f"https://t.me/{bot_info.username}")]
        ])
        
        try:
            await app.send_message(
                chat_id=LOGGER_GROUP_ID,
                text=log_text,
                reply_markup=log_keyboard
            )
        except Exception as log_error:
            print(f"Gagal mengirim log ke grup: {log_error}")

        return {"status": "success", "message": "Payment processed automatically"}
    
    elif status in ["expired", "failed", "cancel"]:
        # Opsional: Handle jika webhook mengirim status gagal
        await update_order_status(transaction_id, status)
        try:
            await app.send_message(
                chat_id=order['user_id'], 
                text=f"❌ Pembayaran untuk pesanan `{transaction_id}` telah **{status.upper()}**."
            )
        except:
            pass
        return {"status": "success", "message": "Status updated to failed/expired"}

    return {"status": "ignored", "message": f"Unhandled status: {status}"}

# =====================================
# LIFESPAN & RUNNER (Menjalankan Bot & API)
# =====================================
@web_app.on_event("startup")
async def startup_event():
    # Menjalankan Pyrogram saat FastAPI mulai
    await app.start()
    print("🤖 Bot Telegram berjalan...")

@web_app.on_event("shutdown")
async def shutdown_event():
    # Mematikan Pyrogram saat FastAPI berhenti
    await app.stop()
    print("🤖 Bot Telegram dihentikan...")

if __name__ == "__main__":
    # Jalankan server Uvicorn (Host dan Port bisa disesuaikan)
    # Port 8000 adalah default, pastikan port ini terbuka / di-reverse proxy oleh Nginx
    uvicorn.run("server:web_app", host="0.0.0.0", port=8000, reload=True)
