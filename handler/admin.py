import os
import shutil
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import (
    RPCError, 
    FloodWait, 
    UserDeactivated, 
    PeerIdInvalid, 
    UserIsBlocked, 
    InputUserDeactivated
)
from app import app
from config import OWNER_ID, DB_NAME
from database import (
    add_channel,
    get_channels,
    delete_channel,
    update_price,
    get_all_users,  # Mengambil semua user dari tabel 'users' yang pernah /start
)

# State management untuk multi-step form dan restore
ADMIN_STATE = {}
RESTORE_MODE = set()

# Filter keamanan untuk memastikan hanya owner/admin yang bisa akses
admin_filter = filters.user(OWNER_ID)


# =====================================
# ADD CHANNEL (Langkah 1: Minta Teks)
# =====================================

@app.on_message(filters.command("addchannel") & admin_filter)
async def add_channel_cmd(client: Client, message: Message):
    ADMIN_STATE[message.from_user.id] = {"state": "ADD_CHANNEL_TEXT"}
    await message.reply_text(
        "📝 **Langkah 1:** Kirim detail channel dengan format berikut:\n\n"
        "`-1001234567890` (ID Channel)\n"
        "`50000` (Harga tanpa titik/koma)\n"
        "Deskripsi Channel bebas"
    )


# =====================================
# ADMIN TEXT HANDLER (Logic State Teks)
# =====================================

@app.on_message(filters.text & ~filters.command(["start", "help", "backup", "restore", "cancel_restore", "listchannel", "delchannel", "setprice", "broadcast"]) & admin_filter)
async def admin_text(client: Client, message: Message):
    user_id = message.from_user.id
    state_data = ADMIN_STATE.get(user_id)

    if not state_data:
        return

    if state_data.get("state") == "ADD_CHANNEL_TEXT":
        try:
            data = message.text.split("\n")
            if len(data) < 3:
                await message.reply_text("❌ Format salah. Kirim ulang sesuai format 3 baris di atas.")
                return

            channel_id = int(data[0].strip())
            price = int(data[1].strip())
            description = data[2].strip()

            chat = await client.get_chat(channel_id)
            channel_name = chat.title
            username = chat.username or ""

            ADMIN_STATE[user_id] = {
                "state": "ADD_CHANNEL_PHOTO",
                "channel_name": channel_name,
                "channel_id": channel_id,
                "price": price,
                "description": description,
                "username": username
            }

            await message.reply_text(
                "📸 **Langkah 2:** Kirimkan foto/gambar yang ingin digunakan sebagai cover list channel VIP ini."
            )
            
        except RPCError:
            ADMIN_STATE.pop(user_id, None)
            await message.reply_text("❌ Bot tidak dapat mengakses channel. Pastikan bot sudah dimasukkan ke channel tersebut dan dijadikan Admin.")
        except Exception as e:
            ADMIN_STATE.pop(user_id, None)
            await message.reply_text(f"❌ Error: {e}")


# =====================================
# ADMIN PHOTO HANDLER (Langkah 2: Foto Channel)
# =====================================

@app.on_message(filters.photo & admin_filter)
async def admin_photo(client: Client, message: Message):
    user_id = message.from_user.id
    state_data = ADMIN_STATE.get(user_id)

    if not state_data or state_data.get("state") != "ADD_CHANNEL_PHOTO":
        return

    try:
        telegram_photo_id = message.photo.file_id
        
        os.makedirs("assets", exist_ok=True)
        photo_filename = f"assets/channel_{state_data['channel_id']}.jpg"
        await message.download(file_name=photo_filename)

        await add_channel(
            name=state_data["channel_name"], 
            channel_id=str(state_data["channel_id"]), 
            price=state_data["price"], 
            description=state_data["description"],
            photo_path=telegram_photo_id  
        )

        ADMIN_STATE.pop(user_id, None)

        await message.reply_text(
            "✅ **Channel VIP Berhasil Ditambahkan!**\n\n"
            f"📺 Nama: **{state_data['channel_name']}**\n"
            f"🆔 Channel ID: `{state_data['channel_id']}`\n"
            f"🔗 Username: @{state_data['username'] if state_data['username'] else '-'}\n"
            f"💰 Harga: Rp {state_data['price']:,}\n"
            f"🖼 Photo ID: `{telegram_photo_id[:25]}...`"
        )
        
    except Exception as e:
        ADMIN_STATE.pop(user_id, None)
        await message.reply_text(f"❌ Gagal memproses penyimpanan foto & channel: {e}")


# =====================================
# LIST CHANNEL
# =====================================

@app.on_message(filters.command("listchannel") & admin_filter)
async def list_channel_cmd(client: Client, message: Message):
    channels = await get_channels()
    if not channels:
        await message.reply_text("📭 Belum ada channel VIP yang terdaftar.")
        return

    text = "📋 **DAFTAR CHANNEL VIP**\n\n"
    for channel in channels:
        text += (
            f"🔑 **ID Referensi:** `{channel['id']}`\n"
            f"📺 Nama: {channel['name']}\n"
            f"🆔 Channel ID: `{channel['channel_id']}`\n"
            f"💰 Harga: Rp {channel['price']:,}\n\n"
        )
    await message.reply_text(text)


# =====================================
# DELETE CHANNEL
# =====================================

@app.on_message(filters.command("delchannel") & admin_filter)
async def del_channel_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("💡 Gunakan perintah:\n`/delchannel ID` (Gunakan ID Referensi dari /listchannel)")
        return

    try:
        channel_id = int(message.command[1])
        await delete_channel(channel_id)
        await message.reply_text("✅ Channel VIP berhasil dihapus dari database.")
    except ValueError:
        await message.reply_text("❌ ID channel harus berupa angka.")


# =====================================
# UPDATE PRICE
# =====================================

@app.on_message(filters.command("setprice") & admin_filter)
async def set_price_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        await message.reply_text("💡 Gunakan perintah:\n`/setprice ID HARGA` (Contoh: `/setprice 1 75000`)")
        return

    try:
        channel_id = int(message.command[1])
        price = int(message.command[2])
        await update_price(channel_id, price)
        await message.reply_text(f"✅ Harga channel ID {channel_id} berhasil diperbarui menjadi Rp {price:,}.")
    except ValueError:
        await message.reply_text("❌ ID dan harga harus dimasukkan dalam bentuk angka tunggal.")


# =====================================
# BACKUP DATABASE
# =====================================

@app.on_message(filters.command("backup") & admin_filter & filters.private)
async def backup_cmd(client: Client, message: Message):
    if not os.path.exists(DB_NAME):
        await message.reply_text("❌ File database utama tidak ditemukan.")
        return

    try:
        await message.reply_document(
            document=DB_NAME,
            file_name="database_backup.db",
            caption="✅ **Backup database berhasil dibuat.**"
        )
    except Exception as e:
        await message.reply_text(f"❌ Backup gagal dikirim: {e}")


# =====================================
# RESTORE DATABASE
# =====================================

@app.on_message(filters.command("restore") & admin_filter & filters.private)
async def restore_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    RESTORE_MODE.add(user_id)
    await message.reply_text(
        "📥 **Mode Restore Database Aktif**\n\n"
        "Silakan kirimkan file database cadangan dengan format `.db` ke sini.\n"
        "Ketik /cancel_restore jika ingin membatalkan."
    )


@app.on_message(filters.command("cancel_restore") & admin_filter & filters.private)
async def cancel_restore_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in RESTORE_MODE:
        RESTORE_MODE.remove(user_id)
        await message.reply_text("🔴 Mode restore telah dibatalkan.")
    else:
        await message.reply_text("Anda tidak sedang berada dalam mode restore database.")


@app.on_message(filters.document & admin_filter & filters.private)
async def receive_restore_file(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in RESTORE_MODE:
        return

    document = message.document
    if not document.file_name or not document.file_name.endswith(".db"):
        await message.reply_text("❌ File ditolak! Ekstensi file wajib berupa `.db`.")
        return

    status_msg = await message.reply_text("⏳ Memproses file restore database...")
    temp_file_path = os.path.abspath("restore_temp.db")

    try:
        downloaded_path = await message.download(file_name=temp_file_path)
        if not downloaded_path or not os.path.exists(downloaded_path):
            raise FileNotFoundError("File gagal diunduh.")

        shutil.copyfile(downloaded_path, DB_NAME)
        
        if os.path.exists(downloaded_path):
            os.remove(downloaded_path)

        RESTORE_MODE.remove(user_id)
        await status_msg.edit_text("✅ **Database berhasil direstore secara penuh.**\n\nJalankan ulang script bot kamu.")

    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        await status_msg.edit_text(f"❌ Restore gagal dieksekusi:\n`{e}`")


# =====================================
# COMMAND BROADCAST (Sistem Reply)
# =====================================

@app.on_message(filters.command("broadcast") & admin_filter & filters.private)
async def execute_broadcast(client: Client, message: Message):
    # Validasi apakah user melakukan reply ke pesan yang mau disiarkan
    if not message.reply_to_message:
        return await message.reply_text("❌ **Reply Goblok**")

    # Mengambil list user_id dari fungsi get_all_users()
    users = await get_all_users()
    if not users:
        return await message.reply_text("📭 Belum ada database user yang terekam.")

    broadcast_msg = message.reply_to_message
    total = 0
    successful = 0
    blocked = 0
    deleted = 0
    unsuccessful = 0

    pls_wait = await message.reply_text("⏳ **SABAR NGENTOT**")

    for chat_id in users:
        try:
            # Mengirim salinan pesan secara utuh ke setiap user ID
            await broadcast_msg.copy(chat_id=int(chat_id))
            successful += 1
            await asyncio.sleep(0.05)  # Delay 50ms anti-spam limit telegram
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await broadcast_msg.copy(chat_id=int(chat_id))
            successful += 1
        except UserIsBlocked:
            blocked += 1
        except InputUserDeactivated:
            deleted += 1
        except Exception:
            unsuccessful += 1
        
        total += 1

    status = (
        "📢 **Berhasil Mengirim pesan ke:**\n\n"
        f"✅ Berhasil: `{successful}`\n"
        f"❌ Gagal: `{unsuccessful}`\n"
        f"🚫 Pengguna Diblokir: `{blocked}`\n"
        f"💀 Akun Dihapus: `{deleted}`\n"
        f"📊 Total Pengguna: `{total}`"
    )

    return await pls_wait.edit_text(status)
