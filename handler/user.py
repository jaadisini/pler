import os
from datetime import datetime, timedelta, timezone

from pyrogram import Client, enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from app import app
from database import add_user, get_channel, get_channels, get_order_by_user

# ==================================
# KONSTANTA & KEYBOARD UTAMA
# ==================================

START_CAPTION = (
    "Hello.\n"
    "Silahkan Pilih Folder Sesuai Keinginan Anda.\n\n"
    "<blockquote>MASING MASING FOLDER MEMILIKI MEDIA PREMIUM, BISA DI SAVE, DAN TANPA JANGKA WAKTU (PERMANENT)</blockquote>\n\n"
    "<blockquote>Cara melakukan pembayaran :\n"
    "• Tekan /start.\n"
    '• Tekan "Lihat Daftar Vip"...</blockquote>'
)


def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="List VVIP",
                callback_data="vip",
                style=enums.ButtonStyle.SUCCESS,
                icon_custom_emoji_id="5447408120752013199",
            ),
            InlineKeyboardButton(
                text="Cara Order",
                callback_data="help",
                style=enums.ButtonStyle.PRIMARY,
                icon_custom_emoji_id="5805434498602506971",
            ),
        ]
    ])


# ==================================
# START COMMAND
# ==================================


@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    await add_user(user_id=user.id, username=user.username)

    await message.reply_photo(
        photo="assets/welcome.jpg",
        caption=START_CAPTION,
        reply_markup=get_main_keyboard(),
    )


# ==================================
# LIST CHANNEL (Paginasi)
# ==================================


async def show_channels(callback_query: CallbackQuery, page: int = 1):
    channels = await get_channels()

    if not channels:
        await callback_query.answer("❌ Belum ada Channel VIP.", show_alert=True)
        return

    # --- Konfigurasi Paginasi ---
    items_per_page = 10
    total_channels = len(channels)
    total_pages = (total_channels + items_per_page - 1) // items_per_page

    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_channels = channels[start_idx:end_idx]

    wib_now = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")

    text = (
        "<emoji id=5447408120752013199>📁</emoji> <b>LIST VVIP — NAKA VIP</b>\n\n"
        "🚀 <b>Berikut adalah daftar paket eksklusif yang kami tawarkan. "
        "Klik salah satu folder VVIP di tombol bawah untuk lihat detail & checkout.</b>\n"
        f"<emoji id=5447421246172069841>📄</emoji> <b>Halaman {page} / {total_pages}</b>\n"
        f"<emoji id=5424972470023104089>🕓</emoji> <b>{wib_now} WIB</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{channel['name']}",
                icon_custom_emoji_id="5447408120752013199",
                callback_data=f"view:{channel['id']}",
                style=enums.ButtonStyle.PRIMARY,
            )
        ]
        for channel in current_channels
    ]

    keyboard.append([
        InlineKeyboardButton(
            text="VVIP POPULER",
            icon_custom_emoji_id="5424972470023104089",
            callback_data="vip_populer",
            style=enums.ButtonStyle.SUCCESS,
        )
    ])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Prev",
                icon_custom_emoji_id="5805434498602506971",
                callback_data=f"vip:{page-1}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Next",
                icon_custom_emoji_id="5805194895261963278",
                callback_data=f"vip:{page+1}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([
        InlineKeyboardButton(
            text="🏰 Back Home",
            callback_data="home",
            style=enums.ButtonStyle.DANGER,
        )
    ])

    await callback_query.edit_message_media(
        media=InputMediaPhoto("assets/welcome.jpg", caption=text),
        reply_markup=InlineKeyboardMarkup(keyboard),
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
        f"<emoji id=5447408120752013199>📁</emoji> <b>{channel['name']}</b>\n\n"
        f"<emoji id=5409048419211682843>💵</emoji> <b>Harga :</b> Rp {channel['price']:,}\n"
        f"<emoji id=5334882760735598374>📝</emoji> <b>Deskripsi :</b>\n{channel['description']}\n\n"
        "Klik tombol di bawah untuk melanjutkan ke proses pembayaran QRIS."
    )

    photo_path = channel.get("photo_path")
    if not photo_path or (not photo_path.startswith("AgA") and not os.path.exists(photo_path)):
        photo_path = "assets/welcome.jpg"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="Beli Sekarang",
                icon_custom_emoji_id="5409048419211682843",
                callback_data=f"buy:{channel['id']}",
                style=enums.ButtonStyle.SUCCESS,
            )
        ],
        [
            InlineKeyboardButton(
                text="Kembali ke Daftar",
                icon_custom_emoji_id="5805434498602506971",
                callback_data="vip",
                style=enums.ButtonStyle.DANGER,
            )
        ],
    ])

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto(photo_path, caption=text),
            reply_markup=keyboard,
        )
    except Exception:
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=text),
            reply_markup=keyboard,
        )


# ==================================
# HELP / CARA ORDER
# ==================================


async def show_help(callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="Kembali",
                icon_custom_emoji_id="5805434498602506971",
                callback_data="home",
                style=enums.ButtonStyle.DANGER,
            )
        ]
    ])

    caption = (
        "❓ <b>Pusat Bantuan / Cara Order</b>\n\n"
        "Cara membeli VIP:\n\n"
        "1. Tekan <b>🏷 List VVIP</b>.\n"
        "2. Pilih Channel VIP yang diminati.\n"
        "3. Baca info detail lalu pilih <b>💳 Beli Sekarang</b>.\n"
        "4. Lakukan pembayaran melalui kode QRIS yang dikirim bot.\n"
        "5. Tekan <b>🔄 Cek Pembayaran</b>.\n"
        "6. Sistem akan otomatis memasukkan Anda ke akses Channel VIP.\n\n"
        "Jika mengalami kendala, silakan hubungi admin."
    )

    await callback_query.edit_message_media(
        media=InputMediaPhoto("assets/welcome.jpg", caption=caption),
        reply_markup=keyboard,
    )


# ==================================
# CALLBACK ROUTER
# ==================================


@app.on_callback_query(filters.regex(r"^(vip(:\d+)?|home|help|view:\d+|vip_populer)$"))
async def user_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    await callback_query.answer()

    if data.startswith("vip"):
        parts = data.split(":")
        page = int(parts[1]) if len(parts) > 1 else 1
        await show_channels(callback_query, page)

    elif data == "help":
        await show_help(callback_query)

    elif data.startswith("view:"):
        channel_id = int(data.split(":")[1])
        await view_channel_detail(callback_query, channel_id)

    elif data == "vip_populer":
        await callback_query.answer("🔥 Menampilkan daftar VVIP Populer", show_alert=False)

    elif data == "home":
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=START_CAPTION),
            reply_markup=get_main_keyboard(),
        )


# ==================================
# MY ORDER COMMAND
# ==================================


@app.on_message(filters.command("myorder"))
async def myorder_cmd(client: Client, message: Message):
    order = await get_order_by_user(message.from_user.id)

    if not order:
        await message.reply_text("📭 Belum ada transaksi.")
        return

    status = order.get("status", "")
    emoji = {
        "pending": "🟡",
        "paid": "🟢",
        "expired": "🔴",
        "cancel": "⚫",
    }.get(status, "❔")

    await message.reply_text(
        "📄 <b>Order Terakhir</b>\n\n"
        f"🆔 {order['transaction_id']}\n"
        f"💰 Rp {order['unique_amount']:,}\n"
        f"{emoji} Status : <b>{status.upper()}</b>"
    )
