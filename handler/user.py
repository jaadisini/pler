
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Message 

from app import app
from config import OWNER_ID
from database import (
    add_user,
    clear_user_bundle,
    get_channel,
    get_channels,
    get_order_by_user,
    get_user_bundle,
    toggle_user_bundle,
)

# Import modul richgram helper/utils
from richgram import (
    rich_esc,
    rich_heading,
    rich_kv_table,
    rich_list,
    rich_note,
)

# ==================================
# KONSTANTA & KEYBOARD UTAMA
# ==================================

ALL_VIP_PRICE = 100000  # Harga paket Beli Semua VIP
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # ⚠️ Ganti dengan ID Telegram Admin Anda


def random_style() -> str:
    """Random button colour — changes on every redraw."""
    return random.choice(["success", "danger", "primary"])


def _tg_btn(text: str, callback_data: str, style: Optional[str] = None) -> str:
    style_attr = f' style="{style}"' if style else ""
    return (
        f'<tg-button type="callback_data"{style_attr} '
        f'data="{callback_data}">{text}</tg-button>'
    )


def _row(*buttons: str) -> str:
    """One full-width row of buttons."""
    return "<tg-button-row>" + "".join(buttons) + "</tg-button-row>"


START_CAPTION = (
    rich_heading("Naka VIP Portal", level=2)
    + "\n"
    + "Hello.\n"
    + "Silahkan Pilih Folder Sesuai Keinginan Anda.\n\n"
    + rich_note("MASING MASING FOLDER MEMILIKI MEDIA PREMIUM, BISA DI SAVE, DAN TANPA JANGKA WAKTU (PERMANENT)", expandable=False)
    + "\n\n"
    + rich_note(
        "<b>Cara melakukan pembayaran :</b>\n"
        "• Tekan /start.\n"
        '• Tekan "List VVIP" atau "Paket Bundle"...',
        expandable=True,
    )
)


def get_main_keyboard() -> str:
    return (
        _row(
            _tg_btn("List VVIP", "vip", random_style()),
            _tg_btn("Paket Bundle 📦", "bundle", random_style()),
        )
        + _row(
            _tg_btn("🔥 Beli Semua VIP", "buy:all", "success"),
        )
        + _row(
            _tg_btn("Cara Order", "help", "primary"),
            _tg_btn("💬 Livechat Admin", "livechat", "primary"),
        )
    )


# ==================================
# START COMMAND
# ==================================


@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    await add_user(user_id=user.id, username=user.username)

    await message.reply_text(
        text=START_CAPTION,
        reply_markup=get_main_keyboard(),
    )


# ==================================
# LIST CHANNEL (Paginasi)
# ==================================


async def show_channels(callback_query, page: int = 1):
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
        f"<emoji id=5447408120752013199>📁</emoji> {rich_heading('LIST VVIP — NAKA VIP', level=2)}\n\n"
        f"🚀 <b>Berikut adalah daftar paket eksklusif yang kami tawarkan. "
        f"Klik salah satu folder VVIP di tombol bawah untuk lihat detail & checkout.</b>\n"
        f"<emoji id=5447421246172069841>📄</emoji> <b>Halaman {page} / {total_pages}</b>\n"
        f"<emoji id=5424972470023104089>🕓</emoji> <b>{wib_now} WIB</b>"
    )

    html_kb = ""
    for channel in current_channels:
        html_kb += _row(_tg_btn(f"{channel['name']}", f"view:{channel['id']}", random_style()))

    html_kb += _row(_tg_btn("🔥 Beli Semua Channel VIP", "buy:all", "success"))
    html_kb += _row(_tg_btn("VVIP POPULER", "vip_populer", "success"))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(_tg_btn("Prev", f"vip:{page-1}", "primary"))
    if page < total_pages:
        nav_buttons.append(_tg_btn("Next", f"vip:{page+1}", "primary"))

    if nav_buttons:
        html_kb += _row(*nav_buttons)

    html_kb += _row(_tg_btn("🏰 Back Home", "home", "danger"))

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=text),
            reply_markup=html_kb,
        )
    except Exception:
        await callback_query.edit_message_text(
            text=text,
            reply_markup=html_kb,
        )


# ==================================
# MENU BUNDLE (DATABASE DRIVEN)
# ==================================


async def show_bundle_menu(callback_query, page: int = 1):
    user_id = callback_query.from_user.id
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
        f"{rich_heading('CUSTOM BUNDLE — PILIH CHANNEL SENDIRI', level=2)}\n\n"
        "Pilih channel apa saja yang ingin Anda beli dalam <b>1x pembayaran</b>.\n"
        "Klik tombol channel di bawah untuk mencentang/membatalkan.\n\n"
        f"📋 <b>Channel Terpilih ({len(selected_ids)}):</b>\n{selected_str}\n\n"
        f"💰 <b>Total Harga:</b> Rp {total_price:,}\n"
        f"📄 <b>Halaman {page} / {total_pages}</b>"
    )

    html_kb = ""
    for ch in current_channels:
        ch_id = ch["id"]
        is_selected = ch_id in selected_ids
        checkbox = "☑️" if is_selected else "⬜"
        btn_style = "success" if is_selected else "primary"

        html_kb += _row(_tg_btn(f"{checkbox} {ch['name']} — Rp {ch['price']:,}", f"toggle_bundle:{ch_id}:{page}", btn_style))

    nav_buttons = []
    if page > 1:
        nav_buttons.append(_tg_btn("Prev", f"bundle:{page-1}", "primary"))
    if page < total_pages:
        nav_buttons.append(_tg_btn("Next", f"bundle:{page+1}", "primary"))
    if nav_buttons:
        html_kb += _row(*nav_buttons)

    if selected_ids:
        html_kb += _row(_tg_btn(f"💳 Checkout Bundle (Rp {total_price:,})", "buy_bundle", "success"))
        html_kb += _row(_tg_btn("🧹 Reset Pilihan", "clear_bundle", "danger"))

    html_kb += _row(_tg_btn("🏰 Back Home", "home", "danger"))

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=text),
            reply_markup=html_kb,
        )
    except Exception:
        await callback_query.edit_message_text(
            text=text,
            reply_markup=html_kb,
        )


# ==================================
# DETAIL CHANNEL VIP
# ==================================


async def view_channel_detail(callback_query, channel_id: int):
    channel = await get_channel(channel_id)

    if not channel:
        await callback_query.answer("❌ Channel tidak ditemukan.", show_alert=True)
        return

    text = (
        f"<emoji id=5447408120752013199>📁</emoji> {rich_heading(channel['name'], level=2)}\n\n"
        f"<emoji id=5409048419211682843>💵</emoji> <b>Harga :</b> Rp {channel['price']:,}\n"
        f"<emoji id=5334882760735598374>📝</emoji> <b>Deskripsi :</b>\n"
        + rich_note(channel['description'], expandable=True)
        + "\n\nKlik tombol di bawah untuk melanjutkan ke proses pembayaran QRIS."
    )

    photo_path = channel.get("photo_path")
    if not photo_path or (not photo_path.startswith("AgA") and not os.path.exists(photo_path)):
        photo_path = "assets/welcome.jpg"

    html_kb = (
        _row(_tg_btn("Beli Sekarang", f"buy:{channel['id']}", "success"))
        + _row(_tg_btn("Kembali ke Daftar", "vip", "danger"))
    )

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto(photo_path, caption=text),
            reply_markup=html_kb,
        )
    except Exception:
        await callback_query.edit_message_text(
            text=text,
            reply_markup=html_kb,
        )


# ==================================
# HELP / CARA ORDER
# ==================================


async def show_help(callback_query):
    html_kb = _row(_tg_btn("Kembali", "home", "danger"))

    caption = (
        f"❓ {rich_heading('Pusat Bantuan / Cara Order', level=2)}\n\n"
        "<b>Cara membeli VIP:</b>\n"
        + rich_list([
            "Tekan <b>🏷 List VVIP</b>, <b>📦 Paket Bundle</b>, atau <b>🔥 Beli Semua VIP</b>.",
            "Pilih satu, beberapa, atau semua Channel VIP.",
            "Lanjutkan ke proses pembayaran QRIS yang dikirim bot.",
            "Tekan <b>🔄 Cek Pembayaran</b>.",
            "Sistem akan otomatis memasukkan Anda ke akses Channel VIP."
        ], ordered=True)
        + "\n\n"
        + rich_note("Jika mengalami kendala, silakan hubungi admin melalui menu Livechat.", expandable=False)
    )

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=caption),
            reply_markup=html_kb,
        )
    except Exception:
        await callback_query.edit_message_text(
            text=caption,
            reply_markup=html_kb,
        )


# ==================================
# LIVECHAT ADMIN HANDLERS
# ==================================


async def show_livechat_menu(callback_query):
    html_kb = _row(_tg_btn("« Kembali ke Menu Utama", "home", "danger"))

    caption = (
        f"💬 {rich_heading('LIVECHAT DENGAN ADMIN', level=2)}\n\n"
        "Silakan kirimkan pesan, pertanyaan, atau kendala Anda (bisa berupa teks, foto, atau bukti transfer) langsung di chat ini.\n\n"
        "<i>Admin akan segera membalas pesan Anda.</i>"
    )

    try:
        await callback_query.edit_message_media(
            media=InputMediaPhoto("assets/welcome.jpg", caption=caption),
            reply_markup=html_kb,
        )
    except Exception:
        await callback_query.edit_message_text(
            text=caption,
            reply_markup=html_kb,
        )


@app.on_message(filters.private & ~filters.user(ADMIN_ID) & ~filters.command(["start", "myorder"]))
async def forward_to_admin(client: Client, message: Message):
    if not OWNER_ID:
        await message.reply_text("⚠️ Livechat sedang tidak aktif (Admin ID belum diatur).")
        return

    user = message.from_user
    forwarded = await message.forward(OWNER_ID)

    await client.send_message(
        chat_id=OWNER_ID,
        text=(
            f"📩 <b>Pesan Masuk dari User:</b>\n"
            f"• Nama: {user.first_name} {user.last_name or ''}\n"
            f"• Username: @{user.username or 'Tidak ada'}\n"
            f"• ID: `{user.id}`\n\n"
            f"<i>(Balas pesan ini untuk merespons user)</i>"
        ),
        reply_to_message_id=forwarded.id,
    )
    await message.reply_text("✅ Pesan Anda telah dikirim ke Admin. Mohon tunggu balasan selanjutnya.")


@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.reply)
async def reply_from_admin(client: Client, message: Message):
    replied_msg = message.reply_to_message
    if not replied_msg:
        return

    target_user_id = None

    if replied_msg.forward_from:
        target_user_id = replied_msg.forward_from.id
    elif replied_msg.caption and "ID:" in replied_msg.caption:
        try:
            for line in replied_msg.caption.split("\n"):
                if "ID:" in line:
                    target_user_id = int(line.split("`")[1])
        except Exception:
            pass

    if not target_user_id and replied_msg.reply_to_message and replied_msg.reply_to_message.forward_from:
        target_user_id = replied_msg.reply_to_message.forward_from.id

    if target_user_id:
        try:
            await message.copy(chat_id=target_user_id)
            await message.reply_text("✅ Balasan berhasil dikirim ke user.", quote=True)
        except Exception as e:
            await message.reply_text(f"❌ Gagal mengirim pesan ke user: {e}", quote=True)
    else:
        await message.reply_text("⚠️ Gagal mendeteksi ID user. Pastikan Anda melakukan Reply pada pesan yang diteruskan dari user.", quote=True)


# ==================================
# CALLBACK ROUTER
# ==================================


@app.on_callback_query(
    filters.regex(
        r"^(vip(:\d+)?|home|help|view:\d+|vip_populer|bundle(:\d+)?|toggle_bundle:\d+:\d+|buy_bundle|clear_bundle|buy:all|livechat)$"
    )
)
async def user_callback(client: Client, callback_query):
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

        await toggle_user_bundle(user_id, ch_id)
        await show_bundle_menu(callback_query, page)

    elif data == "clear_bundle":
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

    elif data == "livechat":
        await show_livechat_menu(callback_query)

    elif data.startswith("view:"):
        channel_id = int(data.split(":")[1])
        await view_channel_detail(callback_query, channel_id)

    elif data == "vip_populer":
        await callback_query.answer("🔥 Menampilkan daftar VVIP Populer", show_alert=False)

    elif data == "home":
        try:
            await callback_query.edit_message_media(
                media=InputMediaPhoto("assets/welcome.jpg", caption=START_CAPTION),
                reply_markup=get_main_keyboard(),
            )
        except Exception:
            await callback_query.edit_message_text(
                text=START_CAPTION,
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

    table_data = [
        ("ID Transaksi", f"`{order['transaction_id']}`"),
        ("Nominal", f"Rp {order['unique_amount']:,}"),
        ("Status", f"{emoji} <b>{status.upper()}</b>")
    ]
    
    table_content = rich_kv_table(table_data)

    await message.reply_text(
        f"📄 {rich_heading('Order Terakhir', level=3)}\n\n" + table_content
    )
