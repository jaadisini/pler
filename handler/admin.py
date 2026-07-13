import os
import shutil
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait, UserDeactivated, PeerIdInvalid
from app import app
from config import OWNER_ID, DB_NAME
from database import (
    add_channel,
    get_channels,
    delete_channel,
    update_price,
    get_all_users,  # Pastikan fungsi ini sudah ditambahkan di database.py
)

# State management untuk multi-step form, restore, dan broadcast
ADMIN_STATE = {}
RESTORE_MODE = set()
BROADCAST_STATE = set()

# Filter keamanan untuk memastikan hanya owner/admin yang bisa akses
admin_filter = filters.user(OWNER_ID)


# =====================================
# ADD CHANNEL (Langkah 1: Minta Teks)
# =====================================

@app.on_message(filters.command("addchannel") & admin_filter)
async def add_channel_cmd(client: Client, message: Message):
    # Set state awal untuk menerima teks detail channel
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

@app.on_message(filters.text & ~filters.command(["start", "help", "backup", "restore", "cancel_restore", "listchannel", "delchannel", "setprice", "broadcast", "cancel_bc"]) & admin_filter)
async def admin_text(client: Client, message: Message):
    user_id = message.from_user.id
    state_data = ADMIN_STATE.get(user_id)

    if not state_data:
        return

    # Menangani input teks saat menambah channel
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

            # Simpan data teks sementara ke state dan lanjut ke langkah foto
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
        # Buat folder assets jika belum dibuat di server
        os.makedirs("assets", exist_ok=True)
        
        # Simpan file secara lokal dengan penamaan ID channel yang unik
        photo_filename = f"assets/channel_{state_data['channel_id']}.jpg"
        await message.download(file_name=photo_filename)

        # Simpan data lengkap ke database (termasuk path foto)
        await add_channel(
            name=state_data["channel_name"], 
            channel_id=str(state_data["channel_id"]), 
            price=state_data["price"], 
            description=state_data["description"],
            photo_path=photo_filename  
        )

        # Bersihkan state admin
        ADMIN_STATE.pop(user_id, None)

        await message.reply_text(
            "✅ **Channel VIP Berhasil Ditambahkan!**\n\n"
            f"📺 Nama: **{state_data['channel_name']}**\n"
            f"🆔 Channel ID: `{state_data['channel_id']}`\n"
            f"🔗 Username: @{state_data['username'] if state_data['username'] else '-'}\n"
            f"💰 Harga: Rp {state_data['price']:,}\n"
            f"🖼 Path Foto: `{photo_filename}`"
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
            caption="✅ **Backup database berhasil dibuat.**\n\nSimpan berkas `.db` ini baik-baik."
        )
    except Exception as e:
        await message.reply_text(f"❌ Backup gagal dikirim: {e}")


# =====================================
# RESTORE DATABASE (Memicu State)
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


# =====================================
# CANCEL RESTORE
# =====================================

@app.on_message(filters.command("cancel_restore") & admin_filter & filters.private)
async def cancel_restore_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in RESTORE_MODE:
        RESTORE_MODE.remove(user_id)
        await message.reply_text("🔴 Mode restore telah dibatalkan.")
    else:
        await message.reply_text("Anda tidak sedang berada dalam mode restore database.")


# =====================================
# RECEIVE DATABASE FILE (Eksekusi Dokumen)
# =====================================

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

    try:
        temp_file = "restore_temp.db"
        await message.download(file_name=temp_file)

        shutil.copyfile(temp_file, DB_NAME)
        
        if os.path.exists(temp_file):
            os.remove(temp_file)

        RESTORE_MODE.remove(user_id)

        await status_msg.edit_text(
            "✅ **Database berhasil direstore secara penuh.**\n\n"
            "⚠️ **Rekomendasi:** Harap jalankan ulang / restart proses script Bot kamu agar data cache internal memuat database baru secara sempurna."
        )

    except Exception as e:
        if os.path.exists("restore_temp.db"):
            os.remove("restore_temp.db")
        await status_msg.edit_text(f"❌ Restore gagal dieksekusi:\n`{e}`")


# =====================================
# COMMAND BROADCAST (Memicu Mode)
# =====================================

@app.on_message(filters.command("broadcast") & admin_filter & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    BROADCAST_STATE.add(user_id)
    await message.reply_text(
        "📢 **Mode Broadcast Aktif**\n\n"
        "Silakan kirim pesan yang ingin disebarkan ke seluruh user.\n"
        "Bisa berupa Teks biasa, Foto, Video, atau Dokumen terformat.\n\n"
        "Ketik `/cancel_bc` untuk membatalkan."
    )


# =====================================
# CANCEL BROADCAST
# =====================================

@app.on_message(filters.command("cancel_bc") & admin_filter & filters.private)
async def cancel_bc_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in BROADCAST_STATE:
        BROADCAST_STATE.remove(user_id)
        await message.reply_text("🔴 Mode broadcast telah dibatalkan.")
    else:
        await message.reply_text("Anda tidak sedang dalam mode broadcast.")


# =====================================
# PROSES EKSEKUSI BROADCAST (Teks & Media)
# =====================================

@app.on_message(admin_filter & filters.private & ~filters.command(["start", "help", "broadcast", "cancel_bc", "backup", "restore", "cancel_restore", "listchannel", "delchannel", "setprice"]))
async def execute_broadcast(client: Client, message: Message):
    user_id = message.from_user.id

    if user_id not in BROADCAST_STATE:
        return

    BROADCAST_STATE.remove(user_id)

    # Ambil semua user unik dari database riwayat order
    users = await get_all_users()
    if not users:
        await message.reply_text("📭 Tidak ada data user unik yang terdata untuk menerima broadcast.")
        return

    status_msg = await message.reply_text(f"⏳ Mengirim materi broadcast ke {len(users)} user...")

    sukses = 0
    gagal = 0

    for target_user_id in users:
        try:
            # Menyalin pesan secara identik beserta format teks/medianya
            await message.copy(chat_id=int(target_user_id))
            sukses += 1
            await asyncio.sleep(0.05)  # Anti-spam delay kecil
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.copy(chat_id=int(target_user_id))
            sukses += 1
        except (UserDeactivated, PeerIdInvalid):
            gagal += 1
        except Exception:
            gagal += 1

    await status_msg.edit_text(
        "📢 **Broadcast Selesai Disiarkan!**\n\n"
        f"✅ Berhasil terkirim: `{sukses}` user\n"
        f"❌ Gagal/Blokir/Hapus: `{gagal}` user"
    )
