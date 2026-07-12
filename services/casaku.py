import logging

import aiohttp

from config import (
    CASAKU_BASE_URL,
    CASAKU_LICENSE_KEY,
    CASAKU_QRIS_ID,
)

logger = logging.getLogger(__name__)


class Casaku:

    def __init__(self):
        self.base_url = CASAKU_BASE_URL.rstrip("/")

        self.headers = {
            "x-license-key": CASAKU_LICENSE_KEY,
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

                if response.status >= 400:
                    raise Exception(
                        data.get(
                            "message",
                            "Casaku Error",
                        )
                    )

                return data

    # ==========================================
    # GENERATE QRIS
    # ==========================================

    async def generate_qris(
        self,
        amount,
        package_ids=None,
        expired=15,
        unique_code=True,
        prefix="VIP",
    ):
        if package_ids is None:
            package_ids = [
                "id.dana",
            ]

        payload = {
            "id": CASAKU_QRIS_ID,
            "amount": amount,
            "useUniqueCode": unique_code,
            "packageIds": package_ids,
            "expiredInMinutes": expired,
            "prefix": prefix,
        }

        logger.info(
            "Generate QRIS: %s",
            amount,
        )

        return await self.request(
            "POST",
            "/api/generate/qris",
            json=payload,
        )

    # ==========================================
    # GET TRANSACTION
    # ==========================================

    async def check_payment(
        self,
        transaction_id,
    ):
        return await self.request(
            "GET",
            f"/api/transaction/{transaction_id}",
        )

    # ==========================================
    # CHECK STATUS
    # ==========================================

    async def check_status(
        self,
        transaction_id,
    ):
        payload = {
            "transactionId": transaction_id,
        }

        return await self.request(
            "POST",
            "/api/generate/check-status",
            json=payload,
        )

    # ==========================================
    # CANCEL TRANSACTION
    # ==========================================

    async def cancel_transaction(
        self,
        transaction_id,
    ):
        payload = {
            "transactionId": transaction_id,
        }

        return await self.request(
            "POST",
            "/api/generate/cancel-status",
            json=payload,
        )


casaku = Casaku()
