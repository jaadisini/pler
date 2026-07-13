from pyrogram import Client, filters
from pyrogram import enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from database import get_channels, get_order_by_user
from app import app

# ==================================
# START
# ==================================

@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        # Gunakan parameter style= secara eksplisit
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
    text = "📦 <b>DAFTAR CHANNEL VIP</b>\n\n"

    for channel in channels:
        text += f"📺 <b>{channel['name']}</b>\n💰 Rp {channel['price']:,}\n\n"
        keyboard.append([
            InlineKeyboardButton(
                f"🛒 {channel['name']}", 
                callback_data=f"buy:{channel['id']}", 
                style=enums.ButtonStyle.SUCCESS # Tambahkan style=
            )
        ])

    # Tambahkan style sekunder/danger untuk tombol kembali
    keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data="home", style=enums.ButtonStyle.DANGER)])

    await callback_query.edit_message_caption(
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================================
# HELP
# ==================================

async def show_help(callback_query: CallbackQuery):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Kembali", callback_data="home", style=enums.ButtonStyle.DANGER)]
    ])

    await callback_query.edit_message_caption(
        caption=(
            "❓ <b>Pusat Bantuan</b>\n\n"
            "Cara membeli VIP:\n\n"
            "1. Tekan <b>🛒 Beli VIP</b>.\n"
            "2. Pilih Channel VIP.\n"
            "3. Lakukan pembayaran melalui QRIS.\n"
            "4. Tekan <b>✅ Cek Pembayaran</b>.\n"
            "5. Jika pembayaran berhasil, bot akan otomatis mengirimkan akses Channel VIP.\n\n"
            "Jika mengalami kendala, silakan hubungi admin."
        ),
        reply_markup=keyboard
    )

# ==================================
# CALLBACK HANDLER
# ==================================

@app.on_callback_query(filters.regex(r"^(vip|home|help)$"))
async def user_callback(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    await callback_query.answer()

    if data == "vip":
        await show_channels(callback_query)
    elif data == "help":
        await show_help(callback_query)
    elif data == "home":
        # Samakan dengan style pada fungsi start_cmd
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Beli VIP", callback_data="vip", style=enums.ButtonStyle.SUCCESS)],
            [InlineKeyboardButton("❓ Bantuan", callback_data="help", style=enums.ButtonStyle.PRIMARY)]
        ])
        
        # Mengembalikan ke pesan foto awal
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
