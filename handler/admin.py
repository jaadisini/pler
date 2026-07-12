from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from config import OWNER_ID
from database import (
    add_channel,
    get_channels,
    delete_channel,
    update_price,
)

# State management
ADMIN_STATE = {}

# Filter untuk memastikan hanya admin yang bisa akses
admin_filter = filters.user(OWNER_ID)

# =====================================
# ADD CHANNEL
# =====================================

@Client.on_message(filters.command("addchannel") & admin_filter)
async def add_channel_cmd(client: Client, message: Message):
    ADMIN_STATE[message.from_user.id] = "ADD_CHANNEL"
    await message.reply_text(
        "Format:\n\n"
        "-1001234567890\n"
        "50000\n"
        "Deskripsi Channel"
    )

# =====================================
# ADMIN TEXT HANDLER (Logic State)
# =====================================

@Client.on_message(filters.text & ~filters.command(["start", "help"]) & admin_filter)
async def admin_text(client: Client, message: Message):
    user_id = message.from_user.id
    state = ADMIN_STATE.get(user_id)

    if state == "ADD_CHANNEL":
        try:
            data = message.text.split("\n")
            if len(data) < 3:
                await message.reply_text("Format salah. Kirim ulang sesuai format.")
                return

            channel_id = int(data[0].strip())
            price = int(data[1].strip())
            description = data[2].strip()

            chat = await client.get_chat(channel_id)
            channel_name = chat.title
            username = chat.username or ""

            await add_channel(channel_name, str(channel_id), price, description)
            ADMIN_STATE.pop(user_id, None)

            await message.reply_text(
                "✅ Channel berhasil ditambahkan\n\n"
                f"Nama : {channel_name}\n"
                f"ID : {channel_id}\n"
                f"Username : @{username}\n"
                f"Harga : Rp{price:,}"
            )
        except RPCError:
            await message.reply_text("❌ Bot tidak dapat mengakses channel. Pastikan bot sudah menjadi admin di channel tersebut.")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

# =====================================
# LIST CHANNEL
# =====================================

@Client.on_message(filters.command("listchannel") & admin_filter)
async def list_channel_cmd(client: Client, message: Message):
    channels = await get_channels()
    if not channels:
        await message.reply_text("Belum ada channel.")
        return

    text = "📋 DAFTAR CHANNEL\n\n"
    for channel in channels:
        text += (
            f"ID : {channel['id']}\n"
            f"Nama : {channel['name']}\n"
            f"Channel ID : {channel['channel_id']}\n"
            f"Harga : Rp{channel['price']:,}\n\n"
        )
    await message.reply_text(text)

# =====================================
# DELETE CHANNEL
# =====================================

@Client.on_message(filters.command("delchannel") & admin_filter)
async def del_channel_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("Gunakan:\n/delchannel ID")
        return

    try:
        channel_id = int(message.command[1])
        await delete_channel(channel_id)
        await message.reply_text("✅ Channel berhasil dihapus")
    except ValueError:
        await message.reply_text("ID channel harus berupa angka.")

# =====================================
# UPDATE PRICE
# =====================================

@Client.on_message(filters.command("setprice") & admin_filter)
async def set_price_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply_text("Gunakan:\n/setprice ID HARGA")
        return

    try:
        channel_id = int(message.command[1])
        price = int(message.command[2])
        await update_price(channel_id, price)
        await message.reply_text("✅ Harga berhasil diperbarui")
    except ValueError:
        await message.reply_text("ID dan harga harus berupa angka.")
