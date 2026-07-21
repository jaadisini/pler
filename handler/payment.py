from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app import app
from config import LOGGER_GROUP_ID, OWNER_ID
from database import (
    clear_user_bundle,
    create_order,
    get_active_order,
    get_channel,
    get_order,
    get_user_bundle,
    update_order_status,
)
from services.casaku import casaku
from services.qrcode import generate_qr


# =====================================
# CREATE PAYMENT (SINGLE & BUNDLE)
# =====================================

@app.on_callback_query(filters.regex(r"^(buy:\d+|buy_bundle)$"))
async def create_payment(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    data_str = callback_query.data

    # Cek apakah user masih memiliki order aktif
    active = await get_active_order(user.id)
    if active:
        return await callback_query.answer("Masih ada pembayaran aktif.", show_alert=True)

    channels_to_buy = []

    # 1. Pembelian Single Channel
    if data_str.startswith("buy:"):
        channel_id = int(data_str.split(":")[1])
        channel = await get_channel(channel_id)
        if not channel:
            return await callback_query.answer("Channel tidak ditemukan.", show_alert=True)
        channels_to_buy.append(channel)

    # 2. Pembelian Bundle Multi-Channel (DATABASE DRIVEN)
    elif data_str == "buy_bundle":
        selected_ids = await get_user_bundle(user.id)
        if not selected_ids:
            return await callback_query.answer("⚠️ Silakan pilih minimal 1 channel!", show_alert=True)

        for cid in selected_ids:
            ch = await get_channel(cid)
            if ch:
                channels_to_buy.append(ch)

        if not channels_to_buy:
            return await callback_query.answer("Channel pilihan tidak ditemukan.", show_alert=True)

    # Hitung total harga & siapkan nama/ID channel
    total_price = sum(ch["price"] for ch in channels_to_buy)
    channel_names = ", ".join(ch["name"] for ch in channels_to_buy)
    channel_ids_str = ",".join(str(ch["id"]) for ch in channels_to_buy)

    try:
        result = await casaku.generate_qris(
            amount=total_price,
            package_ids=["id.dana"],
            unique_code=True,
            expired=15,
            prefix="VIP",
        )
        data = result.get("data", {})
        transaction_id = data.get("transactionId")
        unique_amount = data.get("amount") or data.get("uniqueAmount") or total_price
        qr_string = data.get("qrString") or data.get("qr_string") or data.get("qrCode")
        expired_at = data.get("expiredAt", "-")

        # Simpan order ke database (channel_id berisi ID tunggal atau CSV ID bundle)
        await create_order(
            user.id,
            user.username or "",
            channel_ids_str,
            transaction_id,
            total_price,
            unique_amount,
            qr_string,
            expired_at,
        )

        # Bersihkan keranjang bundle user di database setelah transaksi berhasil dibuat
        if data_str == "buy_bundle":
            await clear_user_bundle(user.id)

        # Kirim QR ke User
        qr = generate_qr(qr_string)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Cek Pembayaran", callback_data=f"check:{transaction_id}")],
            [InlineKeyboardButton("❌ Batalkan", callback_data=f"cancel:{transaction_id}")],
        ])

        package_title = f"📦 VIP Bundle ({len(channels_to_buy)} Channel)" if len(channels_to_buy) > 1 else f"📦 Channel : {channel_names}"

        caption_text = (
            "💳 <b>Pembayaran VIP</b>\n\n"
            f"{package_title}\n"
            f"📋 <b>Detail VIP:</b> {channel_names}\n"
            f"💰 <b>Nominal:</b> Rp {unique_amount:,}\n\n"
            f"🆔 <b>Invoice:</b> <code>{transaction_id}</code>\n"
            f"⏰ <b>Expired:</b> {expired_at}"
        )

        await callback_query.message.reply_photo(
            photo=qr,
            caption=caption_text,
            reply_markup=keyboard,
        )
        await callback_query.answer()

        # LOG NOTIFIKASI KE ADMIN
        try:
            admin_log_msg = (
                "🔔 <b>LOG PEMBAYARAN BARU</b>\n\n"
                f"👤 <b>User:</b> {user.mention} ( <code>{user.id}</code> )\n"
                f"🏷 <b>Username:</b> @{user.username if user.username else '-'}\n"
                f"📺 <b>Channel/Bundle:</b> {channel_names} ( <code>{channel_ids_str}</code> )\n"
                f"💰 <b>Nominal:</b> Rp {unique_amount:,}\n"
                f"🆔 <b>Invoice:</b> <code>{transaction_id}</code>\n"
                f"⏰ <b>Expired:</b> {expired_at}"
            )
            await client.send_message(chat_id=OWNER_ID, text=admin_log_msg)
        except Exception as log_error:
            print(f"Gagal mengirim log ke admin: {log_error}")

    except Exception as e:
        await callback_query.message.reply_text(f"❌ Gagal membuat pembayaran: {e}")


# ==================================
# CHECK PAYMENT
# ==================================

@app.on_callback_query(filters.regex(r"^check:"))
async def check_payment(client: Client, callback_query: CallbackQuery):
    transaction_id = callback_query.data.split(":")[1]
    order = await get_order(transaction_id)

    if not order:
        return await callback_query.answer("Order tidak ditemukan di database.", show_alert=True)

    result = await casaku.check_status(transaction_id)
    status = result["data"]["status"].lower()

    if status == "pending":
        return await callback_query.answer("Pembayaran belum diterima.", show_alert=True)

    if status == "paid":
        await update_order_status(transaction_id, "paid")

        # Parsing ID Channel (Mendukung single id "1" maupun bundle "1,2,3")
        raw_channel_ids = str(order["channel_id"]).split(",")
        invite_links = []
        channel_names = []

        for cid_str in raw_channel_ids:
            cid_str = cid_str.strip()
            if not cid_str:
                continue

            channel = await get_channel(int(cid_str))
            if channel:
                try:
                    invite = await client.create_chat_invite_link(
                        chat_id=int(channel["channel_id"]),
                        member_limit=1,
                    )
                    invite_links.append(f"• <b>{channel['name']}</b>:\n{invite.invite_link}")
                    channel_names.append(channel["name"])
                except Exception as link_err:
                    print(f"Gagal membuat invite link untuk channel {cid_str}: {link_err}")

        invite_str = "\n\n".join(invite_links) if invite_links else "Hubungi admin untuk mendapatkan link akses."
        success_text = (
            "✅ <b>PEMBAYARAN BERHASIL</b>\n\n"
            "Berikut adalah link akses VIP Anda:\n\n"
            f"{invite_str}\n\n"
            "<i>Link bersifat sekali pakai per channel. Silakan langsung bergabung!</i>"
        )

        # Kirim pemberitahuan ke user
        await callback_query.edit_message_caption(caption=success_text)
        await client.send_message(callback_query.from_user.id, success_text)

        # LOG TESTIMONI KE GRUP
        user = callback_query.from_user
        waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bought_channels_str = ", ".join(channel_names) if channel_names else str(order["channel_id"])
        unique_amount = order["unique_amount"]

        log_text = (
            "🔔 <b>TESTIMONI — NAKA VIP</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🗓 <b>Tanggal:</b> {waktu}\n"
            f"👤 <b>Buyer:</b> {user.first_name if not user.last_name else f'{user.first_name} {user.last_name}'}\n"
            f"🆔 <b>ID Buyer:</b> <code>{user.id}</code>\n"
            f"📨 <b>Username:</b> @{user.username or '-'}\n"
            f"🛍 <b>VIP:</b> {bought_channels_str}\n"
            f"🧾 <b>Order ID:</b> <code>{transaction_id}</code>\n"
            f"💰 <b>Total:</b> Rp {unique_amount:,}\n"
            "🏦 <b>Metode:</b> QRIS\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Terima kasih sudah order layanan bot VIP kami.\n\n"
            "👋🏻 <b>Pengen Order Cepat?</b>\n"
            "Mudah? Transaksi Otomatis?\n"
            "Silakan klik tombol di bawah 👇"
        )

        bot_info = await client.get_me()
        log_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Hubungi Bot / Order", url=f"https://t.me/{bot_info.username}")]
        ])

        try:
            await client.send_message(
                chat_id=LOGGER_GROUP_ID,
                text=log_text,
                reply_markup=log_keyboard,
            )
        except Exception as log_error:
            print(f"Gagal mengirim log ke grup: {log_error}")

    else:
        await update_order_status(transaction_id, status)
        await callback_query.edit_message_caption(caption=f"❌ Status: {status.upper()}")


# ==================================
# CANCEL PAYMENT
# ==================================

@app.on_callback_query(filters.regex(r"^cancel:"))
async def cancel_payment(client: Client, callback_query: CallbackQuery):
    transaction_id = callback_query.data.split(":")[1]

    try:
        await casaku.cancel_transaction(transaction_id)
        await update_order_status(transaction_id, "cancel")
        await callback_query.edit_message_caption(caption="❌ Pembayaran dibatalkan.")
    except Exception:
        await callback_query.answer("Gagal membatalkan.", show_alert=True)
