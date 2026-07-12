import asyncio
import logging
from pyrogram import Client
from config import LOGGER_GROUP_ID
from database import (
    get_pending_orders,
    update_order_status,
    get_channel,
)
from services.casaku import casaku

logger = logging.getLogger(__name__)

class PaymentChecker:
    def __init__(self, client: Client):
        # Menyimpan instance client Pyrogram
        self.client = client

    async def start(self):
        while True:
            try:
                await self.check_orders()
            except Exception:
                logger.exception("Payment Checker Error")
            await asyncio.sleep(5)

    async def check_orders(self):
        orders = await get_pending_orders()
        if not orders:
            return

        for order in orders:
            try:
                result = await casaku.check_status(order["transaction_id"])
                data = result["data"]
                status = data["status"].lower()

                if status in ["pending", "cancel", "expired"]:
                    if status != "pending":
                        await update_order_status(order["transaction_id"], status)
                    continue

                if status == "paid":
                    await update_order_status(order["transaction_id"], "paid")
                    await self.send_invite(order)

            except Exception:
                logger.exception(f"Checker error for {order['transaction_id']}")

    async def send_invite(self, order):
        channel = await get_channel(order["channel_id"])
        if not channel:
            return

        try:
            # Menggunakan client Pyrogram untuk membuat invite link
            invite = await self.client.create_chat_invite_link(
                chat_id=int(channel["channel_id"]),
                member_limit=1,
            )

            await self.client.send_message(
                chat_id=order["user_id"],
                text=(
                    "✅ Pembayaran berhasil.\n\n"
                    "Silakan bergabung ke Channel VIP:\n\n"
                    f"{invite.invite_link}"
                ),
            )

            # Logging ke grup admin
            await self.client.send_message(
                chat_id=LOGGER_GROUP_ID,
                text=(
                    "✅ PAYMENT SUCCESS\n\n"
                    f"User : {order['user_id']}\n"
                    f"Invoice : {order['transaction_id']}\n"
                    f"Channel : {channel['name']}"
                ),
            )
        except Exception:
            logger.exception("Invite/Notification Error")
