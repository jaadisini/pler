import logging
import aiohttp

from config import (
    MAELYN_BASE_URL,
    MAELYN_API_KEY,
    SAWERIA_USER_ID,
)

logger = logging.getLogger(__name__)


class Saweria:

    def __init__(self):
        self.base_url = MAELYN_BASE_URL.rstrip("/")
        self.headers = {
            "x-maelyn-auth": MAELYN_API_KEY,
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method,
        endpoint,
        **kwargs,
    ):
        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession(
            headers=self.headers,
        ) as session:
            async with session.request(
                method,
                url,
                **kwargs,
            ) as response:
                data = await response.json(
                    content_type=None,
                )

                if response.status >= 400 or not data.get("success", True):
                    raise Exception(
                        data.get(
                            "message",
                            "Maelyn Saweria Error",
                        )
                    )

                return data

    # ==========================================
    # CREATE TRANSACTION
    # ==========================================

    async def create_transaction(
        self,
        amount: int,
        name: str = "Anonymous",
        email: str = "noreply@example.com",
        msg: str = "Pembayaran VIP",
        user_id: str = None,
    ):
        payload = {
            "user_id": user_id or SAWERIA_USER_ID,
            "amount": amount,
            "name": name,
            "email": email,
            "msg": msg,
        }

        logger.info(
            "Create Saweria Transaction: %s for user %s",
            amount,
            payload["user_id"],
        )

        return await self.request(
            "POST",
            "/payment/saweria/create/transaction",
            json=payload,
        )

    # ==========================================
    # CHECK TRANSACTION
    # ==========================================

    async def check_transaction(
        self,
        payment_id: str,
        user_id: str = None,
    ):
        params = {
            "user_id": user_id or SAWERIA_USER_ID,
            "payment_id": payment_id,
        }

        return await self.request(
            "GET",
            "/payment/saweria/check/transaction",
            params=params,
        )


saweria = Saweria()
