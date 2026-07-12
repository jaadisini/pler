from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_channel,
    create_order,
    get_active_order,
    get_order,
    update_order_status,
)
from services.casaku import casaku
from services.qrcode import generate_qr
from datetime import datetime
from config import LOGGER_GROUP_ID

# ==================================
# CREATE PAYMENT
# ==================================

@Client.on_callback_query(filters.regex(r"^buy:"))
async def create_payment(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    channel_id = int(callback_query.data.split(":")[1])
    
    channel = await get_channel(channel_id)
    if not channel:
        return await callback_query.answer("Channel tidak ditemukan.", show_alert=True)

    active = await get_active_order(user.id)
    if active:
        return await callback_query.answer("Masih ada pembayaran aktif.", show_alert=True)

    try:
        result = await casaku.generate_qris(
            amount=channel['price'],
            package_ids=["id.dana"],
            unique_code=True,
            expired=15,
            prefix="VIP",
        )
        data = result.get("data")
        transaction_id = data["transactionId"]
        unique_amount = data.get("amount") or data.get("uniqueAmount") or channel['price']
        qr_string = data["qrString"]
        expired_at = data.get("expiredAt", "-")

        await create_order(user.id, user.username or "", channel_id, transaction_id, channel['price'], unique_amount, qr_string, expired_at)
        
        # Kirim QR
        qr = generate_qr(qr_string)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Cek Pembayaran", callback_data=f"check:{transaction_id}")],
            [InlineKeyboardButton("❌ Batalkan", callback_data=f"cancel:{transaction_id}")]
        ])

        await callback_query.message.reply_photo(
            photo=qr,
            caption=f"💳 <b>Pembayaran VIP</b>\n\n📦 Channel : {channel['name']}\n💰 Nominal : Rp {unique_amount:,}\n\n🆔 Invoice : <code>{transaction_id}</code>\n⏰ Expired : {expired_at}",
            reply_markup=keyboard
        )
        await callback_query.answer()
        
    except Exception as e:
        await callback_query.message.reply_text(f"❌ Gagal membuat pembayaran: {e}")

# ==================================
# CHECK PAYMENT
# ==================================

@Client.on_callback_query(filters.regex(r"^check:"))
async def check_payment(client: Client, callback_query: CallbackQuery):
    transaction_id = callback_query.data.split(":")[1]
    order = await get_order(transaction_id)
    
    result = await casaku.check_status(transaction_id)
    status = result["data"]["status"].lower()

    if status == "pending":
        return await callback_query.answer("Pembayaran belum diterima.", show_alert=True)

    if status == "paid":
        await update_order_status(transaction_id, "paid")
        channel = await get_channel(order['channel_id'])
        
        # Generate invite link
        invite = await client.create_chat_invite_link(
            chat_id=int(channel['channel_id']),
            member_limit=1
        )
        
        await callback_query.edit_message_caption(caption=f"✅ PEMBAYARAN BERHASIL\n\nInvite Link: {invite.invite_link}")
        await client.send_message(callback_query.from_user.id, f"✅ Pembayaran berhasil. Link: {invite.invite_link}")
    else:
        await update_order_status(transaction_id, status)
        await callback_query.edit_message_caption(caption=f"❌ Status: {status.upper()}")

# ==================================
# CANCEL PAYMENT
# ==================================

@Client.on_callback_query(filters.regex(r"^cancel:"))
async def cancel_payment(client: Client, callback_query: CallbackQuery):
    transaction_id = callback_query.data.split(":")[1]
    
    try:
        await casaku.cancel_transaction(transaction_id)
        await update_order_status(transaction_id, "cancel")
        await callback_query.edit_message_caption(caption="❌ Pembayaran dibatalkan.")
    except Exception as e:
        await callback_query.answer("Gagal membatalkan.", show_alert=True)
