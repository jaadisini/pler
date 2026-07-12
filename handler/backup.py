import os
import shutil
from pyrogram import Client, filters
from pyrogram.types import Message
from config import OWNER_ID, DB_NAME

# Menggunakan set untuk menyimpan ID user yang sedang dalam mode restore
RESTORE_MODE = set()

# Filter admin untuk penggunaan ulang
admin_filter = filters.user(OWNER_ID)

# =====================================
# BACKUP DATABASE
# =====================================

@Client.on_message(filters.command("backup") & admin_filter)
async def backup_cmd(client: Client, message: Message):
    if not os.path.exists(DB_NAME):
        await message.reply_text("Database tidak ditemukan.")
        return

    await message.reply_document(
        document=DB_NAME,
        caption="✅ Backup database berhasil."
    )

# =====================================
# RESTORE DATABASE
# =====================================

@Client.on_message(filters.command("restore") & admin_filter)
async def restore_cmd(client: Client, message: Message):
    RESTORE_MODE.add(message.from_user.id)
    await message.reply_text("Kirim file database (.db) untuk restore.")

# =====================================
# RECEIVE DATABASE FILE
# =====================================

@Client.on_message(filters.document & admin_filter)
async def restore_file(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in RESTORE_MODE:
        return

    # Validasi ekstensi file
    if not message.document.file_name.endswith(".db"):
        await message.reply_text("File harus berformat .db")
        return

    try:
        # Download file ke direktori sementara
        temp_file = await message.download(file_name="restore_temp.db")
        
        # Timpa file database lama dengan yang baru
        shutil.copyfile(temp_file, DB_NAME)
        
        # Hapus file sementara
        os.remove(temp_file)
        
        RESTORE_MODE.remove(user_id)
        await message.reply_text("✅ Database berhasil direstore.\n\nSilakan restart bot.")

    except Exception as e:
        await message.reply_text(f"❌ Restore gagal:\n{e}")
