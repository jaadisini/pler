from datetime import datetime
import logging

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from app import app
from config import LOGGER_GROUP_ID, OWNER_ID, SAWERIA_USER_ID
from database import (
    clear_user_bundle,
    create_order,
    get_active_order,
    get_channel,
    get_channels,
    get_order,
    get_user_bundle,
    update_order_status,
)
from services.saweria import saweria

logger = logging.getLogger(__name__)

ALL_VIP_PRICE = 100000
MAX_ERROR_LENGTH = 1000


# =====================================
# HELPER: ERROR MESSAGE & DICT ACCESS
# =====================================

def safe_error_text(error, max_length=MAX_ERROR_LENGTH):
    """Membatasi dan membersihkan pesan error untuk Telegram."""
    error_text = str(error) or "Terjadi kesalahan yang tidak diketahui."

    if len(error_text) > max_length:
        error_text = error_text[:max_length] + "\n... detail error dipotong."

    return error_text


def get_field(obj, key, default=None):
    """Fungsi helper untuk mengambil data dari sqlite3.Row atau dict."""
    try:
        if obj is None:
            return default
        if hasattr(obj, "keys") and key in obj.keys():
            return obj[key]
        elif isinstance(obj, dict):
            return obj.get(key, default)
        elif hasattr(obj, key):
            return getattr(obj, key)
    except Exception:
        pass
    return default


async def send_payment_error(callback_query, error):
    """Mengirim pesan error dengan aman tanpa menyebabkan MESSAGE_TOO_LONG."""
    logger.exception(
        "Operasi pembayaran gagal: %s",
        error,
    )

    message = (
        "❌ Gagal memproses pembayaran.\n\n"
        f"{safe_error_text(error)}"
    )

    try:
        await callback_query.message.reply_text(message)
    except Exception:
        logger.exception("Gagal mengirim pesan error ke pengguna")

        try:
            await callback_query.answer(
                "Gagal memproses pembayaran. Silakan coba lagi.",
                show_alert=True,
            )
        except Exception:
            logger.exception("Gagal menampilkan notifikasi error")


# =====================================
# HELPER: PROSES SUKSES PEMBAYARAN & LINK
# =====================================

async def process_successful_payment(
    client: Client,
    callback_query: CallbackQuery,
    order,
    transaction_id: str,
):
    """Memproses order yang sudah paid: membuat invite link, update DB, kirim pesan & testimoni."""
    order_status = str(get_field(order, "status", "")).lower()

    if order_status == "paid":
        return

    await update_order_status(transaction_id, "paid")

    raw_channel_ids = str(
        get_field(order, "channel_id", "")
    ).split(",")

    invite_links = []
    channel_names = []

    for channel_id_str in raw_channel_ids:
        channel_id_str = channel_id_str.strip()

        if not channel_id_str:
            continue

        try:
            channel = await get_channel(int(channel_id_str))
        except Exception:
            logger.exception(
                "Gagal mengambil data channel %s",
                channel_id_str,
            )
            continue

        if not channel:
            continue

        try:
            invite = await client.create_chat_invite_link(
                chat_id=int(get_field(channel, "channel_id")),
                member_limit=1,
            )

            ch_name = str(get_field(channel, "name", "Channel"))
            invite_links.append(
                f"• {ch_name}:\n"
                f"{invite.invite_link}"
            )
            channel_names.append(ch_name)

        except Exception:
            logger.exception(
                "Gagal membuat invite link channel %s",
                channel_id_str,
            )

    invite_str = (
        "\n\n".join(invite_links)
        if invite_links
        else "Hubungi admin untuk mendapatkan link akses."
    )

    success_text = (
        "✅ PEMBAYARAN BERHASIL\n\n"
        "Berikut link akses VIP kamu:\n\n"
        f"{invite_str}\n\n"
        "Link undangan bersifat sekali pakai untuk setiap channel."
    )

    # Ambil ID buyer dari order database agar aman baik diakses user maupun di-acc manual owner
    buyer_id = int(get_field(order, "user_id"))

    try:
        await client.send_message(
            chat_id=buyer_id,
            text=success_text,
            disable_web_page_preview=True,
        )
    except Exception:
        logger.exception(
            "Gagal mengirim link VIP kepada user %s",
            buyer_id,
        )

    # Coba edit caption jika callback berasal dari chat pesan QR bot dengan user
    try:
        await callback_query.edit_message_caption(
            caption=success_text,
        )
    except Exception:
        pass

    # =====================================
    # LOG TESTIMONI KE GRUP
    # =====================================
    waktu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    bought_channels_str = (
        ", ".join(channel_names)
        if channel_names
        else str(get_field(order, "channel_id", ""))
    )

    unique_amount = int(
        get_field(order, "unique_amount") or get_field(order, "amount") or 0
    )

    log_text = (
        "🔔 TESTIMONI — NAKA VIP\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🗓 Tanggal: {waktu}\n"
        f"🆔 ID Buyer: {buyer_id}\n"
        f"🛍 VIP: {bought_channels_str}\n"
        f"🧾 Order ID: {transaction_id}\n"
        f"💰 Total: Rp {unique_amount:,}\n"
        "🏦 Metode: Saweria (Auto / Manual ACC)\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Terima kasih sudah order layanan bot VIP kami.\n\n"
        "👋🏻 Pengen Order Cepat?\n"
        "Transaksi mudah dan otomatis!\n"
        "Silakan klik tombol di bawah 👇"
    )

    try:
        bot_info = await client.get_me()

        log_keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛒 Hubungi Bot / Order",
                        url=f"https://t.me/{bot_info.username}",
                    )
                ]
            ]
        )

        await client.send_message(
            chat_id=int(LOGGER_GROUP_ID),
            text=log_text,
            reply_markup=log_keyboard,
        )

    except Exception:
        logger.exception(
            "Gagal mengirim log testimoni ke grup %s",
            LOGGER_GROUP_ID,
        )


# =====================================
# CREATE PAYMENT (SINGLE, BUNDLE & ALL)
# =====================================

@app.on_callback_query(
    filters.regex(r"^(buy:\d+|buy_bundle|buy:all)$")
)
async def create_payment(
    client: Client,
    callback_query: CallbackQuery,
):
    user = callback_query.from_user
    data_str = callback_query.data

    await callback_query.answer()

    try:
        active = await get_active_order(user.id)
    except Exception:
        logger.exception("Gagal memeriksa order aktif user %s", user.id)
        return await callback_query.message.reply_text(
            "❌ Gagal memeriksa pembayaran aktif. Silakan coba lagi."
        )

    if active:
        active_trx_id = get_field(active, "transaction_id") or get_field(active, "order_id")
        if active_trx_id:
            try:
                is_paid = await saweria.check_paid_status(str(active_trx_id))
                if is_paid:
                    await process_successful_payment(client, callback_query, active, str(active_trx_id))
                    return
            except Exception:
                pass

        return await callback_query.message.reply_text(
            "⚠️ Kamu masih memiliki pembayaran aktif."
        )

    channels_to_buy = []
    is_buy_all = False
    total_price = 0

    if data_str == "buy:all":
        all_channels = await get_channels()
        if not all_channels:
            return await callback_query.message.reply_text(
                "❌ Belum ada Channel VIP tersedia."
            )
        channels_to_buy = all_channels
        total_price = ALL_VIP_PRICE
        is_buy_all = True

    elif data_str.startswith("buy:"):
        channel_id = int(data_str.split(":", 1)[1])
        channel = await get_channel(channel_id)
        if not channel:
            return await callback_query.message.reply_text(
                "❌ Channel tidak ditemukan."
            )
        channels_to_buy.append(channel)
        total_price = int(get_field(channel, "price", 0))

    elif data_str == "buy_bundle":
        selected_ids = await get_user_bundle(user.id)
        if not selected_ids:
            return await callback_query.message.reply_text(
                "⚠️ Silakan pilih minimal satu channel!"
            )
        for channel_id in selected_ids:
            channel = await get_channel(channel_id)
            if channel:
                channels_to_buy.append(channel)

        if not channels_to_buy:
            return await callback_query.message.reply_text(
                "❌ Channel pilihan tidak ditemukan."
            )

        total_price = sum(
            int(get_field(channel, "price", 0))
            for channel in channels_to_buy
        )

    if not channels_to_buy:
        return await callback_query.message.reply_text(
            "❌ Tidak ada channel yang dipilih."
        )

    if total_price <= 0:
        return await callback_query.message.reply_text(
            "❌ Nominal pembayaran tidak valid."
        )

    channel_names = ", ".join(
        str(get_field(channel, "name", "Channel"))
        for channel in channels_to_buy
    )

    channel_ids_str = ",".join(
        str(get_field(channel, "id", ""))
        for channel in channels_to_buy
    )

    try:
        user_fullname = (
            f"{user.first_name} {user.last_name or ''}"
        ).strip()

        result = await saweria.create_transaction(
            user_id=str(SAWERIA_USER_ID),
            amount=total_price,
            name=user_fullname or f"User_{user.id}",
            email=f"{user.id}@telegram.org",
            message=f"VIP Access: {channel_names[:30]}",
            creator_name="nsdev",
        )

        if not isinstance(result, dict):
            raise ValueError(
                "Respons API Saweria bukan objek JSON yang valid."
            )

        transaction_id = result.get("transaction_id")
        payment_url = result.get("qr_url")
        amount = int(result.get("amount") or total_price)
        qr_stream = result.get("qr_stream")

        if not transaction_id:
            raise ValueError(
                "ID transaksi (transaction_id) tidak ditemukan dari respons Saweria."
            )

        transaction_id = str(transaction_id)

        await create_order(
            user.id,
            user.username or "",
            channel_ids_str,
            transaction_id,
            total_price,
            amount,
            payment_url or f"https://saweria.co/qris/{transaction_id}",
            "-",
        )

        if data_str == "buy_bundle":
            await clear_user_bundle(user.id)

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Cek Pembayaran",
                        callback_data=f"check:{transaction_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Batalkan",
                        callback_data=f"cancel:{transaction_id}",
                    )
                ],
            ]
        )

        if is_buy_all:
            package_title = (
                "🔥 PAKET AKSES SEMUA VIP "
                f"({len(channels_to_buy)} Channel)"
            )
        elif len(channels_to_buy) > 1:
            package_title = (
                f"📦 VIP Bundle ({len(channels_to_buy)} Channel)"
            )
        else:
            package_title = f"📦 Channel: {channel_names}"

        caption_text = (
            "💳 Pembayaran VIP (Saweria)\n\n"
            f"{package_title}\n"
            f"📋 Detail VIP: {channel_names}\n"
            f"💰 Nominal: Rp {amount:,}\n\n"
            f"🆔 Invoice: {transaction_id}\n\n"
            "Scan QR di atas untuk melakukan pembayaran. "
            "Setelah membayar, tekan Cek Pembayaran."
        )

        await callback_query.message.reply_photo(
            photo=qr_stream,
            caption=caption_text,
            reply_markup=keyboard,
        )

        try:
            admin_log_msg = (
                "🔔 LOG PEMBAYARAN BARU (SAWERIA)\n\n"
                f"👤 User: {user.first_name} ({user.id})\n"
                f"🏷 Username: @{user.username or '-'}\n"
                f"📺 Channel/Bundle: {package_title}\n"
                f"💰 Nominal: Rp {amount:,}\n"
                f"🆔 Invoice: {transaction_id}"
            )

            admin_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "✅ ACC Manual",
                            callback_data=f"manual_acc:{transaction_id}"
                        )
                    ]
                ]
            )

            await client.send_message(
                chat_id=OWNER_ID,
                text=admin_log_msg,
                reply_markup=admin_keyboard,
            )

        except Exception:
            logger.exception(
                "Gagal mengirim log pembayaran ke admin"
            )

    except Exception as error:
        await send_payment_error(callback_query, error)


# ==================================
# MANUAL ACC PAYMENT (KHUSUS OWNER)
# ==================================

@app.on_callback_query(filters.regex(r"^manual_acc:"))
async def manual_acc_payment(
    client: Client,
    callback_query: CallbackQuery,
):
    if callback_query.from_user.id != OWNER_ID:
        return await callback_query.answer(
            "❌ Perintah ini hanya dapat diakses oleh Owner!",
            show_alert=True,
        )

    transaction_id = callback_query.data.split(":", 1)[1]
    await callback_query.answer()

    order = await get_order(transaction_id)

    if not order:
        return await callback_query.answer(
            "❌ Order tidak ditemukan di database.",
            show_alert=True,
        )

    order_status = str(get_field(order, "status", "")).lower()

    if order_status == "paid":
        return await callback_query.answer(
            "✅ Pembayaran ini sudah pernah diproses sebelumnya.",
            show_alert=True,
        )

    await process_successful_payment(client, callback_query, order, transaction_id)

    try:
        updated_log_text = callback_query.message.text + "\n\n✨ Status: DI-ACC MANUAL OLEH OWNER ✅"
        await callback_query.edit_message_text(
            text=updated_log_text,
            reply_markup=None,
        )
    except Exception:
        pass

    return await callback_query.answer(
        "✅ Berhasil melakukan ACC manual pembayaran!",
        show_alert=True,
    )


# ==================================
# CHECK PAYMENT
# ==================================

@app.on_callback_query(filters.regex(r"^check:"))
async def check_payment(
    client: Client,
    callback_query: CallbackQuery,
):
    transaction_id = callback_query.data.split(":", 1)[1]

    await callback_query.answer()

    order = await get_order(transaction_id)

    if not order:
        return await callback_query.answer(
            "❌ Order tidak ditemukan di database.",
            show_alert=True,
        )

    order_status = str(get_field(order, "status", "")).lower()

    if order_status == "paid":
        return await callback_query.answer(
            "✅ Pembayaran ini sudah diproses.",
            show_alert=True,
        )

    try:
        is_paid = await saweria.check_paid_status(transaction_id)
    except Exception:
        logger.exception(
            "Gagal mengecek transaksi %s",
            transaction_id,
        )

        return await callback_query.answer(
            "Gagal mengecek pembayaran. Silakan coba lagi.",
            show_alert=True,
        )

    if not is_paid:
        return await callback_query.answer(
            "⏳ Pembayaran belum diterima.",
            show_alert=True,
        )

    await process_successful_payment(client, callback_query, order, transaction_id)

    return await callback_query.answer(
        "✅ Pembayaran berhasil!",
        show_alert=True,
    )


# ==================================
# CANCEL PAYMENT
# ==================================

@app.on_callback_query(filters.regex(r"^cancel:"))
async def cancel_payment(
    client: Client,
    callback_query: CallbackQuery,
):
    transaction_id = callback_query.data.split(":", 1)[1]

    order = await get_order(transaction_id)

    if not order:
        return await callback_query.answer(
            "❌ Order tidak ditemukan.",
            show_alert=True,
        )

    order_status = str(get_field(order, "status", "")).lower()

    if order_status == "paid":
        return await callback_query.answer(
            "Pembayaran yang sudah berhasil tidak bisa dibatalkan.",
            show_alert=True,
        )

    try:
        await update_order_status(
            transaction_id,
            "cancel",
        )

        try:
            await callback_query.edit_message_caption(
                caption="❌ Pembayaran dibatalkan.",
            )
        except Exception:
            await callback_query.message.reply_text(
                "❌ Pembayaran dibatalkan."
            )

        await callback_query.answer(
            "Pembayaran dibatalkan.",
            show_alert=True,
        )

    except Exception:
        logger.exception(
            "Gagal membatalkan transaksi %s",
            transaction_id,
        )

        await callback_query.answer(
            "Gagal membatalkan pembayaran.",
            show_alert=True,
        )
