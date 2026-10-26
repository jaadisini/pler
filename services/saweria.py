
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

    # ==========================================
    # REQUEST HANDLER
    # ==========================================

    async def request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"

        async with aiohttp.ClientSession(
            headers=self.headers,
        ) as session:
            async with session.request(
                method,
                url,
                **kwargs,
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    raw_text = await response.text()
                    logger.error(
                        "Maelyn API returned invalid JSON: %s",
                        raw_text,
                    )
                    raise Exception(
                        f"Invalid Response: {raw_text}"
                    )

                if not isinstance(data, dict):
                    raise Exception(
                        f"Invalid API response: {data}"
                    )

                if response.status >= 400 or not data.get(
                    "success", False
                ):
                    err_msg = data.get(
                        "message",
                        f"HTTP Status {response.status}",
                    )
                    logger.error(
                        "Maelyn API error [%s]: %s",
                        response.status,
                        err_msg,
                    )
                    raise Exception(err_msg)

                return data

    # ==========================================
    # CHECK ACCOUNT
    # GET /payment/saweria/check/account
    # ==========================================

    async def check_account(self, username: str):
        if not username or not username.strip():
            raise ValueError(
                "Username Saweria wajib diisi."
            )

        params = {
            "username": username.strip().lstrip("@"),
        }

        logger.info(
            "Checking Saweria account: %s",
            params["username"],
        )

        result = await self.request(
            "GET",
            "/payment/saweria/check/account",
            params=params,
        )

        user = result.get("user", {})

        logger.info(
            "Saweria account found: %s",
            user.get("username", params["username"]),
        )

        return result

    # ==========================================
    # CREATE PAYMENT
    # POST /payment/saweria/create/transaction
    # ==========================================

    async def create_transaction(
        self,
        amount: int,
        name: str = "Anonymous",
        email: str = "noreply@example.com",
        msg: str = "Pembayaran VIP",
        user_id: str = None,
    ):
        if int(amount) <= 0:
            raise ValueError(
                "Nominal pembayaran harus lebih dari 0."
            )

        account_id = str(
            user_id or SAWERIA_USER_ID or ""
        ).strip()

        if not account_id:
            raise ValueError(
                "SAWERIA_USER_ID wajib diisi."
            )

        payload = {
            "user_id": account_id,
            "amount": int(amount),
            "name": name or "Anonymous",
            "email": email or "noreply@example.com",
            "msg": msg or "Pembayaran VIP",
        }

        logger.info(
            "Creating Saweria payment: amount=%s, user_id=%s",
            payload["amount"],
            account_id,
        )

        result = await self.request(
            "POST",
            "/payment/saweria/create/transaction",
            json=payload,
        )

        payment = result.get("payment", {})

        if not payment.get("id"):
            raise Exception(
                "Respons API tidak memiliki payment.id."
            )

        if not payment.get("payment_url"):
            raise Exception(
                "Respons API tidak memiliki payment.payment_url."
            )

        logger.info(
            "Saweria payment created: %s",
            payment["id"],
        )

        return result

    # ==========================================
    # CHECK TRANSACTION
    # GET /payment/saweria/check/transaction
    # ==========================================

    async def check_transaction(
        self,
        payment_id: str = None,
        user_id: str = None,
        id: str = None,
    ):
        transaction_id = payment_id or id

        if not transaction_id:
            raise ValueError(
                "payment_id atau id wajib diisi."
            )

        account_id = str(
            user_id or SAWERIA_USER_ID or ""
        ).strip()

        if not account_id:
            raise ValueError(
                "SAWERIA_USER_ID wajib diisi."
            )

        params = {
            "user_id": account_id,
            "payment_id": str(transaction_id),
        }

        logger.info(
            "Checking Saweria transaction: %s",
            transaction_id,
        )

        result = await self.request(
            "GET",
            "/payment/saweria/check/transaction",
            params=params,
        )

        payment = result.get("payment", {})

        logger.info(
            "Saweria transaction status: %s = %s",
            transaction_id,
            payment.get("status", "UNKNOWN"),
        )

        return result


saweria = Saweria()

