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
        base_url = MAELYN_BASE_URL or "https://api.maelyn.eu/api"
        self.base_url = base_url.rstrip("/")
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
        Membaca objek pembayaran dari struktur respons API,
        termasuk struktur nested di dalam payment['data'].
        """
        payment = result.get("payment")

        if isinstance(payment, dict):
            payment_data = payment.get("data")
            if isinstance(payment_data, dict):
                merged_payment = dict(payment)
                merged_payment.update(payment_data)
                return merged_payment
            return payment

        data = result.get("data")

        if isinstance(data, dict):
            nested_payment = data.get("payment")
            if isinstance(nested_payment, dict):
                return nested_payment

            if any(
                key in data
                for key in (
                    "id",
                    "payment_id",
                    "transaction_id",
                    "transactionId",
                    "payment_url",
                    "paymentUrl",
                    "qr_string",
                )
            ):
                return data

        if any(
            key in result
            for key in (
                "id",
                "payment_id",
                "transaction_id",
                "transactionId",
                "payment_url",
                "paymentUrl",
                "qr_string",
            )
        ):
            return result

        return None

    @staticmethod
    def _normalize_payment(result, payment):
        """
        Menormalkan nama field pada objek pembayaran, termasuk qr_string, payment_url, dan status.
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

        qr_string = payment.get("qr_string")

        # Normalisasi status (mengatasi format boolean seperti true/false dari API)
        status = payment.get("status")
        if status is True or status == "true":
            normalized_status = "paid"
        elif status is False or status == "false":
            normalized_status = "unpaid"
        else:
            normalized_status = str(status).lower() if status is not None else "unknown"

        if not payment_url and payment_id:
            payment_url = f"https://saweria.co/pay/{payment_id}"

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

        normalized_payment = dict(payment)
        normalized_payment["id"] = str(payment_id)
        normalized_payment["status"] = normalized_status
        if payment_url:
            normalized_payment["payment_url"] = payment_url
        if qr_string:
            normalized_payment["qr_string"] = qr_string

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

        return result

    # ==========================================
    # CREATE PAYMENT
    # POST /payment/saweria/create/transaction
    # ==========================================

    async def create_transaction(
        self,
        amount: int,
        name: str = "John Doe",
        email: str = "john@example.com",
        msg: str = "Terima kasih",
        user_id: str = None,
    ):
        try:
            amount = int(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "amount harus berupa angka."
            ) from exc

        if amount <= 0:
            raise ValueError(
                "amount harus lebih dari 0."
            )

        account_id = str(
            user_id or SAWERIA_USER_ID or ""
        ).strip()

        if not account_id:
            raise ValueError(
                "user_id wajib diisi."
            )

        payload = {
            "user_id": account_id,
            "amount": amount,
            "name": name or "rezaandik",
            "email": email or "rezaandik145@gmail.com",
            "msg": msg or "Terima kasih",
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
                "Query payment_id atau id wajib diisi."
            )

        account_id = str(
            user_id or SAWERIA_USER_ID or ""
        ).strip()

        if not account_id:
            raise ValueError(
                "Query user_id wajib diisi."
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
            # Normalisasi status saat pengecekan transaksi
            status = payment.get("status")
            if status is True or status == "true":
                normalized_status = "paid"
            elif status is False or status == "false":
                normalized_status = "unpaid"
            else:
                normalized_status = str(status).lower() if status is not None else "unknown"

            logger.info(
                "Saweria transaction status: %s = %s",
                transaction_id,
                normalized_status,
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
