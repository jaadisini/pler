
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
            timeout=aiohttp.ClientTimeout(total=30),
        ) as session:
            async with session.request(
                method,
                url,
                **kwargs,
            ) as response:
                raw_text = await response.text()

                try:
                    data = await response.json(
                        content_type=None
                    )
                except Exception as exc:
                    logger.error(
                        "Maelyn API returned invalid JSON. "
                        "HTTP=%s, Response=%s",
                        response.status,
                        raw_text,
                    )
                    raise Exception(
                        f"Respons API bukan JSON "
                        f"(HTTP {response.status}): {raw_text[:1000]}"
                    ) from exc

                if not isinstance(data, dict):
                    logger.error(
                        "Maelyn API returned unexpected data: %s",
                        data,
                    )
                    raise Exception(
                        f"Format respons API tidak valid: {data}"
                    )

                if response.status >= 400 or not data.get(
                    "success", False
                ):
                    err_msg = (
                        data.get("message")
                        or data.get("error")
                        or f"HTTP Status {response.status}"
                    )

                    logger.error(
                        "Maelyn API error | HTTP=%s | "
                        "Message=%s | Response=%s",
                        response.status,
                        err_msg,
                        data,
                    )

                    raise Exception(
                        f"{err_msg} | Detail: {data}"
                    )

                return data

    # ==========================================
    # NORMALIZE PAYMENT RESPONSE
    # ==========================================

    @staticmethod
    def _extract_payment(result):
        """
        Membaca objek pembayaran dari beberapa kemungkinan
        struktur respons API.

        Format utama:
        {
            "success": true,
            "payment": {
                "id": "...",
                "payment_url": "..."
            }
        }

        Format alternatif yang juga didukung:
        {
            "success": true,
            "data": {
                "payment": {
                    "id": "...",
                    "payment_url": "..."
                }
            }
        }
        """

        payment = result.get("payment")

        if isinstance(payment, dict):
            return payment

        data = result.get("data")

        if isinstance(data, dict):
            nested_payment = data.get("payment")

            if isinstance(nested_payment, dict):
                return nested_payment

            # Beberapa API langsung menyimpan detail transaksi
            # di dalam objek data.
            if any(
                key in data
                for key in (
                    "id",
                    "payment_id",
                    "transaction_id",
                    "transactionId",
                    "payment_url",
                    "paymentUrl",
                )
            ):
                return data

        # Mendukung respons yang langsung berisi ID transaksi.
        if any(
            key in result
            for key in (
                "id",
                "payment_id",
                "transaction_id",
                "transactionId",
                "payment_url",
                "paymentUrl",
            )
        ):
            return result

        return None

    @staticmethod
    def _normalize_payment(result, payment):
        """
        Menormalkan nama field supaya handler lama tetap bisa
        menggunakan result["payment"]["id"] dan
        result["payment"]["payment_url"].
        """

        payment_id = (
            payment.get("id")
            or payment.get("payment_id")
            or payment.get("transaction_id")
            or payment.get("transactionId")
        )

        payment_url = (
            payment.get("payment_url")
            or payment.get("paymentUrl")
            or payment.get("url")
        )

        if not payment_id:
            logger.error(
                "Transaction ID tidak ditemukan. "
                "Respons API lengkap: %s",
                result,
            )
            raise Exception(
                "Respons API tidak memiliki ID transaksi. "
                f"Respons API: {result}"
            )

        if not payment_url:
            logger.error(
                "Payment URL tidak ditemukan. "
                "Respons API lengkap: %s",
                result,
            )
            raise Exception(
                "Respons API tidak memiliki URL pembayaran. "
                f"Respons API: {result}"
            )

        normalized_payment = dict(payment)
        normalized_payment["id"] = str(payment_id)
        normalized_payment["payment_url"] = payment_url

        # Mempertahankan format yang dipakai handler pembayaran.
        normalized_result = dict(result)
        normalized_result["payment"] = normalized_payment

        return normalized_result

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

        user = result.get("user")

        if not isinstance(user, dict):
            data = result.get("data")
            if isinstance(data, dict):
                user = data.get("user", data)

        if isinstance(user, dict):
            logger.info(
                "Saweria account found: %s",
                user.get("username", params["username"]),
            )
        else:
            logger.warning(
                "Account check returned an unexpected structure: %s",
                result,
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
        try:
            amount = int(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Nominal pembayaran harus berupa angka."
            ) from exc

        if amount <= 0:
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
            "amount": amount,
            "name": name or "Anonymous",
            "email": email or "noreply@example.com",
            "msg": msg or "Pembayaran VIP",
        }

        logger.info(
            "Creating Saweria payment: amount=%s, user_id=%s",
            amount,
            account_id,
        )

        result = await self.request(
            "POST",
            "/payment/saweria/create/transaction",
            json=payload,
        )

        logger.info(
            "Create transaction response: %s",
            result,
        )

        payment = self._extract_payment(result)

        if not isinstance(payment, dict):
            logger.error(
                "Payment object not found in API response: %s",
                result,
            )
            raise Exception(
                "Respons API tidak memiliki objek pembayaran. "
                f"Respons API: {result}"
            )

        result = self._normalize_payment(
            result,
            payment,
        )

        logger.info(
            "Saweria payment created: %s",
            result["payment"]["id"],
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

        payment = self._extract_payment(result)

        if isinstance(payment, dict):
            logger.info(
                "Saweria transaction status: %s = %s",
                transaction_id,
                payment.get("status", "UNKNOWN"),
            )
        else:
            logger.warning(
                "Payment detail not found while checking "
                "transaction %s. Response: %s",
                transaction_id,
                result,
            )

        return result


saweria = Saweria()

