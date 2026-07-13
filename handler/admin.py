import os
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from app import app
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

@app.on_message(filters.command("addchannel") & admin_filter)
async def add_channel_cmd(client: Client, message: Message):
    # Set state awal untuk menerima teks detail
    ADMIN_STATE[message.from_user.id] = {"state": "ADD_CHANNEL_TEXT"}
    await message.reply_text(
        "📝 **Langkah 1:** Kirim detail channel dengan format berikut:\n\n"
        "-1001234567890\n"
        "50000\n"
        "Deskripsi Channel"
    )

# =====================================
# ADMIN TEXT HANDLER (Menerima Detail Channel)
# =====================================

@app.on_message(filters.text & ~filters.command(["start", "help"]) & admin_filter)
async def admin_text(client: Client, message: Message):
    user_id = message.from_user.id
    state_data = ADMIN_STATE.get(user_id)

    if not state_data:
        return

    if state_data.get("state") == "ADD_CHANNEL_TEXT":
        try:
            data = message.text.split("\n")
            if len(data) < 3:
                await message.reply_text("❌ Format salah. Kirim ulang sesuai format di atas.")
                return

            channel_id = int(data[0].strip())
            price = int(data[1].strip())
            description = data[2].strip()

            chat = await client.get_chat(channel_id)
            channel_name = chat.title
            username = chat.username or ""

            # Simpan data sementara ke state dan ubah status ke langkah berikutnya
            ADMIN_STATE[user_id] = {
                "state": "ADD_CHANNEL_PHOTO",
                "channel_name": channel_name,
                "channel_id": channel_id,
                "price": price,
                "description": description,
                "username": username
            }

            await message.reply_text(
                "📸 **Langkah 2:** Kirimkan foto yang ingin digunakan untuk welcome/list cover channel ini."
            )
            
        except RPCError:
            ADMIN_STATE.pop(user_id, None)
            await message.reply_text("❌ Bot tidak dapat mengakses channel. Pastikan bot sudah menjadi admin di channel tersebut.")
        except Exception as e:
            ADMIN_STATE.pop(user_id, None)
            await message.reply_text(f"❌ Error: {e}")

# =====================================
# ADMIN PHOTO HANDLER (Menerima Foto Channel)
# =====================================

@app.on_message(filters.photo & admin_filter)
async def admin_photo(client: Client, message: Message):
    user_id = message.from_user.id
    state_data = ADMIN_STATE.get(user_id)

    if not state_data or state_data.get("state") != "ADD_CHANNEL_PHOTO":
        return

    try:
        # Buat folder assets jika belum ada
        os.makedirs("assets", exist_ok=True)
        
        # Simpan file secara lokal dengan nama unik berdasarkan channel_id
        photo_filename = f"assets/channel_{state_data['channel_id']}.jpg"
        await message.download(file_name=photo_filename)

        # Simpan seluruh data ke database termasuk path foto
        await add_channel(
            name=state_data["channel_name"], 
            channel_id=str(state_data["channel_id"]), 
            price=state_data["price"], 
            description=state_data["description"],
            photo_path=photo_filename  # <-- Pastikan fungsi database-mu menerima parameter ini
        )

        # Hapus state setelah sukses
        ADMIN_STATE.pop(user_id, None)

        await message.reply_text(
            "✅ **Channel & Foto Berhasil Ditambahkan!**\n\n"
            f"📺 Nama : {state_data['channel_name']}\n"
            f"🆔 ID : {state_data['channel_id']}\n"
            f"🔗 Username : @{state_data['username']}\n"
            f"💰 Harga : Rp{state_data['price']:,}\n"
            f"🖼 Foto : Terpanah di `{photo_filename}`"
        )
        
    except Exception as e:
        ADMIN_STATE.pop(user_id, None)
        await message.reply_text(f"❌ Gagal menyimpan foto & channel: {e}")

# =====================================
# LIST CHANNEL
# =====================================

@app.on_message(filters.command("listchannel") & admin_filter)
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

@app.on_message(filters.command("delchannel") & admin_filter)
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

@app.on_message(filters.command("setprice") & admin_filter)
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
