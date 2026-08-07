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
from database import (
    add_user,
    clear_user_bundle,
    get_channel,
    get_channels,
    get_order_by_user,
    get_user_bundle,
    toggle_user_bundle,
)

# ==================================
# KONSTANTA & KEYBOARD UTAMA
# ==================================

ALL_VIP_PRICE = 100000  # Harga paket Beli Semua VIP (Rp 100.000)

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
                text="Paket Bundle 📦",
                callback_data="bundle",
                style=enums.ButtonStyle.SUCCESS,
                icon_custom_emoji_id="5447408120752013199",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔥 Beli Semua VIP (Rp {ALL_VIP_PRICE:,})",
                callback_data="buy:all",
                style=enums.ButtonStyle.SUCCESS,
            ),
        ],
        [
            InlineKeyboardButton(
                text="Cara Order",
                callback_data="help",
                style=enums.ButtonStyle.PRIMARY,
                icon_custom_emoji_id="5805434498602506971",
            ),
        ],
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

    # Tombol Akses Semua VIP
    keyboard.append([
        InlineKeyboardButton(
            text=f"🔥 Beli Semua Channel VIP (Rp {ALL_VIP_PRICE:,})",
            callback_data="buy:all",
            style=enums.ButtonStyle.SUCCESS,
        )
    ])

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
# MENU BUNDLE (DATABASE DRIVEN)
# ==================================


async def show_bundle_menu(callback_query: CallbackQuery, page: int = 1):
    user_id = callback_query.from_user.id
    
    # Ambil data keranjang bundle langsung dari database
    selected_ids = set(await get_user_bundle(user_id))

    channels = await get_channels()
    if not channels:
        await callback_query.answer("❌ Belum ada Channel VIP.", show_alert=True)
        return

    items_per_page = 8
    total_channels = len(channels)
    total_pages = (total_channels + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_channels = channels[start_idx:end_idx]

    channel_map = {ch["id"]: ch for ch in channels}
    total_price = sum(channel_map[cid]["price"] for cid in selected_ids if cid in channel_map)
    selected_names = [channel_map[cid]["name"] for cid in selected_ids if cid in channel_map]

    selected_str = (
        "\n".join([f"• <b>{name}</b>" for name in selected_names])
        if selected_names
        else "<i>Belum ada channel yang dipilih</i>"
    )

    text = (
        "📦 <b>CUSTOM BUNDLE — PILIH CHANNEL SENDIRI</b>\n\n"
        "Pilih channel apa saja yang ingin Anda beli dalam <b>1x pembayaran</b>.\n"
        "Klik tombol channel di bawah untuk mencentang/membatalkan.\n\n"
        f"📋 <b>Channel Terpilih ({len(selected_ids)}):</b>\n{selected_str}\n\n"
        f"💰 <b>Total Harga:</b> Rp {total_price:,}\n"
        f"📄 <b>Halaman {page} / {total_pages}</b>"
    )

    keyboard = []
    for ch in current_channels:
        ch_id = ch["id"]
        is_selected = ch_id in selected_ids
        checkbox = "☑️" if is_selected else "⬜"
        btn_style = enums.ButtonStyle.SUCCESS if is_selected else enums.ButtonStyle.PRIMARY

        keyboard.append([
            InlineKeyboardButton(
                text=f"{checkbox} {ch['name']} — Rp {ch['price']:,}",
                callback_data=f"toggle_bundle:{ch_id}:{page}",
                style=btn_style,
            )
        ])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Prev",
                callback_data=f"bundle:{page-1}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )
    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Next",
                callback_data=f"bundle:{page+1}",
                style=enums.ButtonStyle.PRIMARY,
            )
        )
    if nav_buttons:
        keyboard.append(nav_buttons)

    if selected_ids:
        keyboard.append([
            InlineKeyboardButton(
                text=f"💳 Checkout Bundle (Rp {total_price:,})",
                callback_data="buy_bundle",
                style=enums.ButtonStyle.SUCCESS,
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="🧹 Reset Pilihan",
                callback_data="clear_bundle",
                style=enums.ButtonStyle.DANGER,
            )
        ])

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

    photo_path = channel["photo_path"] if "photo_path" in channel.keys() else None
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
        "1. Tekan <b>🏷 List VVIP</b>, <b>📦 Paket Bundle</b>, atau <b>🔥 Beli Semua VIP</b>.\n"
        "2. Pilih satu, beberapa, atau semua Channel VIP.\n"
        "3. Lanjutkan ke proses pembayaran QRIS yang dikirim bot.\n"
        "4. Tekan <b>🔄 Cek Pembayaran</b>.\n"
        "5. Sistem akan otomatis memasukkan Anda ke akses Channel VIP.\n\n"
        "Jika mengalami kendala, silakan hubungi admin."
    )

    await callback_query.edit_message_media(
        media=InputMediaPhoto("assets/welcome.jpg", caption=caption),
        reply_markup=keyboard,
    )


# ==================================
# CALLBACK ROUTER
# ==================================


@app.on_callback_query(
    filters.regex(
        r"^(vip(:\d+)?|home|help|view:\d+|vip_populer|bundle(:\d+)?|toggle_bundle:\d+:\d+|buy_bundle|clear_bundle|buy:all)$"
    )
)
async def user_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    await callback_query.answer()

    if data == "buy:all":
        await callback_query.answer(
            f"🚀 Melanjutkan ke pembayaran Paket Semua VIP (Rp {ALL_VIP_PRICE:,})...", 
            show_alert=True
        )

    elif data.startswith("vip"):
        parts = data.split(":")
        page = int(parts[1]) if len(parts) > 1 else 1
        await show_channels(callback_query, page)

    elif data.startswith("bundle"):
        parts = data.split(":")
        page = int(parts[1]) if len(parts) > 1 else 1
        await show_bundle_menu(callback_query, page)

    elif data.startswith("toggle_bundle:"):
        _, ch_id_str, page_str = data.split(":")
        ch_id = int(ch_id_str)
        page = int(page_str)

        # Toggle item di database
        await toggle_user_bundle(user_id, ch_id)
        await show_bundle_menu(callback_query, page)

    elif data == "clear_bundle":
        # Bersihkan item di database
        await clear_user_bundle(user_id)
        await callback_query.answer("🧹 Pilihan bundle dibersihkan.")
        await show_bundle_menu(callback_query, 1)

    elif data == "buy_bundle":
        selected_ids = await get_user_bundle(user_id)
        if not selected_ids:
            await callback_query.answer("⚠️ Silakan pilih minimal 1 channel!", show_alert=True)
            return

        await callback_query.answer(
            f"🚀 Melanjutkan transaksi {len(selected_ids)} channel...", show_alert=True
        )

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

    status = order["status"] if "status" in order.keys() else ""
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
