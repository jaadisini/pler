# ═══════════════════════════════════════════════════════════════
#                    🎵 NAKA VIP PORTAL
#
#                  © 2026 BAD MUNDA
#
#                Developed with ❤️ by Bad Munda
#
#            Do not remove or alter the original credits.
#
#         Copyright © 2026 Bad Munda. All rights reserved.
#
#
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup

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

# ==================================
# KONSTANTA & KEYBOARD UTAMA
# ==================================

ALL_VIP_PRICE = 100000  # Harga paket Beli Semua VIP
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # ⚠️ Ganti dengan ID Telegram Admin Anda


def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("List VVIP", callback_data="vip"),
            InlineKeyboardButton("Paket Bundle 📦", callback_data="bundle"),
        ],
        [
            InlineKeyboardButton("🔥 Beli Semua VIP", callback_data="buy:all"),
        ],
        [
            InlineKeyboardButton("Cara Order", callback_data="help"),
            InlineKeyboardButton("💬 Livechat Admin", callback_data="livechat"),
        ]
    ])


START_TEXT = (
    "<b>🎵 NAKA VIP PORTAL</b>\n\n"
    "Hello.\n"
    "Silahkan Pilih Folder Sesuai Keinginan Anda.\n\n"
    "📌 <i>MASING MASING FOLDER MEMILIKI MEDIA PREMIUM, BISA DI SAVE, DAN TANPA JANGKA WAKTU (PERMANENT)</i>\n\n"
    "<b>Cara melakukan pembayaran :</b>\n"
    "• Tekan /start.\n"
    "• Tekan \"List VVIP\" atau \"Paket Bundle\"..."
)


# ==================================
# START COMMAND (TANPA FOTO)
# ==================================


@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    try:
        user = message.from_user
        if user:
            await add_user(user_id=user.id, username=user.username)
    except Exception as e:
        print(f"[Database Error di /start]: {e}")

    await message.reply_text(
        text=START_TEXT,
        reply_markup=get_main_keyboard(),
        parse_mode=enums.ParseMode.HTML
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
        f"📁 <b>LIST VVIP — NAKA VIP</b>\n\n"
        f"🚀 <b>Berikut adalah daftar paket eksklusif yang kami tawarkan. "
        f"Klik salah satu folder VVIP di tombol bawah untuk lihat detail & checkout.</b>\n\n"
        f"📄 <b>Halaman {page} / {total_pages}</b>\n"
        f"🕓 <b>{wib_now} WIB</b>"
    )

    keyboard = []
    for channel in current_channels:
        keyboard.append([InlineKeyboardButton(f"{channel['name']}", callback_data=f"view:{channel['id']}")])

    keyboard.append([InlineKeyboardButton("🔥 Beli Semua Channel VIP", callback_data="buy:all")])
    keyboard.append([InlineKeyboardButton("VVIP POPULER", callback_data="vip_populer")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"vip:{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"vip:{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🏰 Back Home", callback_data="home")])

    await callback_query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=enums.ParseMode.HTML
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
        f"📦 <b>CUSTOM BUNDLE — PILIH CHANNEL SENDIRI</b>\n\n"
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
        keyboard.append([InlineKeyboardButton(f"{checkbox} {ch['name']} — Rp {ch['price']:,}", callback_data=f"toggle_bundle:{ch_id}:{page}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bundle:{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"bundle:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    if selected_ids:
        keyboard.append([InlineKeyboardButton(f"💳 Checkout Bundle (Rp {total_price:,})", callback_data="buy_bundle")])
        keyboard.append([InlineKeyboardButton("🧹 Reset Pilihan", callback_data="clear_bundle")])

    keyboard.append([InlineKeyboardButton("🏰 Back Home", callback_data="home")])

    await callback_query.message.edit_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=enums.ParseMode.HTML
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
        f"📁 <b>{channel['name']}</b>\n\n"
        f"💵 <b>Harga :</b> Rp {channel['price']:,}\n"
        f"📝 <b>Deskripsi :</b>\n{channel['description']}\n\n"
        "Klik tombol di bawah untuk melanjutkan ke proses pembayaran QRIS."
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Beli Sekarang", callback_data=f"buy:{channel['id']}")],
        [InlineKeyboardButton("Kembali ke Daftar", callback_data="vip")]
    ])

    await callback_query.message.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML
    )


# ==================================
# HELP / CARA ORDER
# ==================================


async def show_help(callback_query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Kembali", callback_data="home")]
    ])

    caption = (
        "❓ <b>Pusat Bantuan / Cara Order</b>\n\n"
        "<b>Cara membeli VIP:</b>\n"
        "1. Tekan <b>🏷 List VVIP</b>, <b>📦 Paket Bundle</b>, atau <b>🔥 Beli Semua VIP</b>.\n"
        "2. Pilih satu, beberapa, atau semua Channel VIP.\n"
        "3. Lanjutkan ke proses pembayaran QRIS yang dikirim bot.\n"
        "4. Tekan <b>🔄 Cek Pembayaran</b>.\n"
        "5. Sistem akan otomatis memasukkan Anda ke akses Channel VIP.\n\n"
        "<i>Jika mengalami kendala, silakan hubungi admin melalui menu Livechat.</i>"
    )

    await callback_query.message.edit_text(
        text=caption,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML
    )


# ==================================
# LIVECHAT ADMIN HANDLERS
# ==================================


async def show_livechat_menu(callback_query):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Kembali ke Menu Utama", callback_data="home")]
    ])

    caption = (
        "💬 <b>LIVECHAT DENGAN ADMIN</b>\n\n"
        "Silakan kirimkan pesan, pertanyaan, atau kendala Anda (bisa berupa teks, foto, atau bukti transfer) langsung di chat ini.\n\n"
        "<i>Admin akan segera membalas pesan Anda.</i>"
    )

    await callback_query.message.edit_text(
        text=caption,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML
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
        await callback_query.message.edit_text(
            text=START_TEXT,
            reply_markup=get_main_keyboard(),
            parse_mode=enums.ParseMode.HTML
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

    table_content = (
        f"• <b>ID Transaksi:</b> `{order['transaction_id']}`\n"
        f"• <b>Nominal:</b> Rp {order['unique_amount']:,}\n"
        f"• <b>Status:</b> {emoji} <b>{status.upper()}</b>"
    )

    await message.reply_text(
        f"📄 <b>Order Terakhir</b>\n\n" + table_content,
        parse_mode=enums.ParseMode.HTML
    )
