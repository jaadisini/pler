import os
from pyrogram import Client, filters
from pyrogram import enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
)
# Import add_user dari database
from database import get_channels, get_channel, get_order_by_user, add_user
from app import app

# ==================================
# START
# ==================================

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    
    # Simpan atau update data user ke database setiap kali menekan /start
    await add_user(user_id=user.id, username=user.username)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Beli VIP", callback_data="vip", style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton("❓ Bantuan", callback_data="help", style=enums.ButtonStyle.PRIMARY)]
    ])

    await message.reply_photo(
        photo="assets/welcome.jpg",
        caption=(
            "👋 <b>Selamat Datang Di Naka VIP</b>\n\n"
            "Pilih menu di bawah untuk melihat daftar Channel VIP."
        ),
        reply_markup=keyboard
    )


# ==================================
# LIST CHANNEL
# ==================================

async def show_channels(callback_query: CallbackQuery):
    channels = await get_channels()

    if not channels:
        await callback_query.answer("❌ Belum ada Channel VIP.", show_alert=True)
        return

    keyboard = []
    text = "📦 <b>DAFTAR CHANNEL VIP</b>\n\nSilakan pilih channel di bawah untuk melihat detail info dan harga:"

    for channel in channels:
        keyboard.append([
            InlineKeyboardButton(
                f"📺 {channel['name']}", 
                callback_data=f"view:{channel['id']}",
                style=enums.ButtonStyle.SUCCESS
            )
        ])

    keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data="home", style=enums.ButtonStyle.DANGER)])

    await callback_query.edit_message_media(
        media=InputMediaPhoto("assets/welcome.jpg", caption=text),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==================================
# DETAIL CHANNEL VIP
# ==================================

async def view_channel_detail(callback_query: CallbackQuery, channel_id: int):
    channel = await get_channel(channel_id)
    
    if not channel:
        await callback_query.answer("❌ Channel tidak ditemukan.", show_alert=True)
        return

    text = (
        f"📺 <b>{channel['name']}</b>\n\n"
        f"💰 <b>Harga :</b> Rp {channel['price']:,}\n"
        f"📝 <b>Deskripsi :</b>\n{channel['description']}\n\n"
        f"Klik tombol di bawah untuk melanjutkan ke proses pembayaran QRIS."
    )

    photo_path = channel['photo_path']
    if not photo_path or not os.path.exists(photo_path):
        photo_path = "assets/welcome.jpg"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Beli Sekarang", callback_data=f"buy:{channel['id']}", style=enums.ButtonStyle.SUCCESS)],
        [InlineKeyboardButton("⬅️ Kembali ke Daftar", callback_data="vip", style=enums.ButtonStyle.DANGER)]
    ])

    await callback_query.edit_message_media(
        media=InputMediaPhoto(photo_path, caption=text),
        reply_markup=keyboard
    )


# ==================================
# HELP
# ==================================

async def show_help(callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Kembali", callback_data="home", style=enums.ButtonStyle.DANGER)]
    ])

    await callback_query.edit_message_media(
        media=InputMediaPhoto("assets/welcome.jpg", caption=(
            "❓ <b>Pusat Bantuan</b>\n\n"
            "Cara membeli VIP:\n\n"
            "1. Tekan <b>🛒 Beli VIP</b>.\n"
            "2. Pilih Channel VIP yang diminati.\n"
            "3. Baca info detail lalu pilih <b>💳 Beli Sekarang</b>.\n"
            "4. Lakukan pembayaran melalui kode QRIS yang dikirim bot.\n"
            "5. Tekan <b>🔄 Cek Pembayaran</b>.\n"
            "6. Sistem akan otomatis memasukkan Anda ke akses Channel VIP.\n\n"
            "Jika mengalami kendala, silakan hubungi admin."
        )),
        reply_markup=keyboard
    )


# ==================================
# CALLBACK ROUTER
# ==================================

@app.on_callback_query(filters.regex(r"^(vip|home|help|view:\d+)$"))
async def user_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    await callback_query.answer()

    if data == "vip":
        await show_channels(callback_query)
    elif data == "help":
        await show_help(callback_query)
    elif data.startswith("view:"):
        channel_id = int(data.split(":")[1])
        await view_channel_detail(callback_query, channel_id)
    elif data == "home":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Beli VIP", callback_data="vip", style=enums.ButtonStyle.SUCCESS)],
            [InlineKeyboardButton("❓ Bantuan", callback_data="help", style=enums.ButtonStyle.PRIMARY)]
        ])
        
        await callback_query.message.delete()
        await client.send_photo(
            chat_id=callback_query.message.chat.id,
            photo="assets/welcome.jpg",
            caption=(
                "👋 <b>Selamat Datang Di Naka VIP</b>\n\n"
                "Pilih menu di bawah untuk melihat daftar Channel VIP."
            ),
            reply_markup=keyboard
        )


# ==================================
# MY ORDER
# ==================================

@app.on_message(filters.command("myorder"))
async def myorder_cmd(client: Client, message: Message):
    order = await get_order_by_user(message.from_user.id)

    if not order:
        await message.reply_text("📭 Belum ada transaksi.")
        return

    status = order['status']
    emoji = {"pending": "🟡", "paid": "🟢", "expired": "🔴", "cancel": "⚫"}.get(status, "❔")

    await message.reply_text(
        "📄 <b>Order Terakhir</b>\n\n"
        f"🆔 {order['transaction_id']}\n"
        f"💰 Rp {order['unique_amount']:,}\n"
        f"{emoji} Status : <b>{status.upper()}</b>"
        )
