from datetime import datetime
import uuid

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app import app
from config import LOGGER_GROUP_ID, OWNER_ID
from database import (
    clear_user_bundle,
    create_order,
    get_active_order,
    get_channel,
    get_channels,
    get_order,
    get_user_bundle,
    update_order_status,
)
from services.casaku import saweria
from services.qrcode import generate_qr

ALL_VIP_PRICE = 50000  # Fixed price untuk Beli Semua VIP


# =====================================
# CREATE PAYMENT (SINGLE, BUNDLE & ALL)
# =====================================

@app.on_callback_query(filters.regex(r"^(buy:\d+|buy_bundle|buy:all)$"))
async def create_payment(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    data_str = callback_query.data

    # Cek apakah user masih memiliki order aktif
    active = await get_active_order(user.id)
    if active:
        return await callback_query.answer("Masih ada pembayaran aktif.", show_alert=True)

    channels_to_buy = []
    is_buy_all = False

    # 1. Pembelian Semua Channel VIP
    if data_str == "buy:all":
        all_channels = await get_channels()
        if not all_channels:
            return await callback_query.answer("❌ Belum ada Channel VIP tersedia.", show_alert=True)
        channels_to_buy = all_channels
        total_price = ALL_VIP_PRICE
        is_buy_all = True

    # 2. Pembelian Single Channel
    elif data_str.startswith("buy:"):
        channel_id = int(data_str.split(":")[1])
        channel = await get_channel(channel_id)
        if not channel:
            return await callback_query.answer("Channel tidak ditemukan.", show_alert=True)
        channels_to_buy.append(channel)
        total_price = channel["price"]

    # 3. Pembelian Bundle Multi-Channel
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
        
        total_price = sum(ch["price"] for ch in channels_to_buy)

    # Siapkan nama/ID channel
    channel_names = ", ".join(ch["name"] for ch in channels_to_buy)
    channel_ids_str = ",".join(str(ch["id"]) for ch in channels_to_buy)

    try:
        user_fullname = f"{user.first_name} {user.last_name or ''}".strip()
        
        # Panggil API Saweria via Maelyn
        result = await saweria.create_transaction(
            amount=total_price,
            name=user_fullname or f"User_{user.id}",
            email=f"{user.id}@telegram.org",
            msg=f"VIP Access: {channel_names[:30]}",
        )
        
        payment_data = result.get("payment", {}) if isinstance(result, dict) else {}
        
        # Ambil transaction_id / payment_id dari response API
        transaction_id = payment_data.get("id") or payment_data.get("payment_id") or result.get("id")
        payment_url = payment_data.get("payment_url") or result.get("payment_url")
        amount = payment_data.get("amount") or total_price

        # Validasi: Jika transaction_id atau payment_url dari API kosong
        if not transaction_id or not payment_url:
            err_msg = result.get("message", "Gagal mendapatkan data transaksi dari Saweria")
            return await callback_query.message.reply_text(f"❌ Gagal membuat pembayaran: {err_msg}")

        # Simpan order ke database
        await create_order(
            user.id,
            user.username or "",
            channel_ids_str,
            str(transaction_id),
            total_price,
            amount,
            payment_url,
            "-",
        )

        # Bersihkan keranjang bundle user di database
        if data_str == "buy_bundle":
            await clear_user_bundle(user.id)

        # Generate QR Code dari Link Pembayaran Saweria
        qr = generate_qr(payment_url)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Link Pembayaran Direct", url=payment_url)],
            [InlineKeyboardButton("🔄 Cek Pembayaran", callback_data=f"check:{transaction_id}")],
            [InlineKeyboardButton("❌ Batalkan", callback_data=f"cancel:{transaction_id}")],
        ])

        if is_buy_all:
            package_title = f"🔥 PAKET AKSES SEMUA VIP ({len(channels_to_buy)} Channel)"
        elif len(channels_to_buy) > 1:
            package_title = f"📦 VIP Bundle ({len(channels_to_buy)} Channel)"
        else:
            package_title = f"📦 Channel : {channel_names}"

        caption_text = (
            "💳 <b>Pembayaran VIP (Saweria)</b>\n\n"
            f"{package_title}\n"
            f"📋 <b>Detail VIP:</b> {channel_names}\n"
            f"💰 <b>Nominal:</b> Rp {amount:,}\n\n"
            f"🆔 <b>Invoice:</b> <code>{transaction_id}</code>\n\n"
            "<i>Scan QR Code di atas atau klik tombol <b>Link Pembayaran Direct</b> untuk bayar, lalu tekan <b>Cek Pembayaran</b>.</i>"
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
                "🔔 <b>LOG PEMBAYARAN BARU (SAWERIA)</b>\n\n"
                f"👤 <b>User:</b> {user.mention} ( <code>{user.id}</code> )\n"
                f"🏷 <b>Username:</b> @{user.username if user.username else '-'}\n"
                f"📺 <b>Channel/Bundle:</b> {package_title}\n"
                f"💰 <b>Nominal:</b> Rp {amount:,}\n"
                f"🆔 <b>Invoice:</b> <code>{transaction_id}</code>"
            )
            await client.send_message(chat_id=OWNER_ID, text=admin_log_msg)
        except Exception as log_error:
            print(f"Gagal mengirim log ke admin: {log_error}")

    except Exception as e:
        await callback_query.message.reply_text(f"❌ Gagal membuat pembayaran: {e}")
