import asyncio
import contextlib
import io
import json
import logging
import re
import time
from typing import Optional

import cloudscraper25 as cloudscraper
from bs4 import BeautifulSoup

from config import SAWERIA_USER_ID
from services.qrcode import generate_qr

logger = logging.getLogger(__name__)


class Saweria:
    BACKEND = "https://backend.saweria.co"
    FRONTEND = "https://saweria.co"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://saweria.co/",
    }

    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self._lock = asyncio.Lock()
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with contextlib.suppress(Exception):
            self.scraper.close()

    async def aclose(self) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Saweria client sudah ditutup.")

    # ==========================================
    # CHECK ACCOUNT / GET USER ID
    # ==========================================

    async def check_account(self, username: str) -> dict:
        username = str(username or "").strip().lstrip("@")

        if not username:
            raise ValueError("Username Saweria wajib diisi.")

        logger.info("Checking Saweria account: %s", username)

        def request_user_id(retries: int = 3, delay: int = 5):
            self._ensure_open()
            url = f"{self.FRONTEND}/{username}"

            for attempt in range(retries):
                try:
                    with self.scraper.get(
                        url,
                        headers=self.HEADERS,
                        timeout=15,
                    ) as res:
                        if res.status_code != 200:
                            continue

                        soup = BeautifulSoup(res.text, "html.parser")
                        next_data = soup.find(id="__NEXT_DATA__")

                        if not next_data:
                            continue

                        data = json.loads(next_data.text)
                        user_data = (
                            data.get("props", {})
                            .get("pageProps", {})
                            .get("data", {})
                        )
                        user_id = user_data.get("id")

                        if user_id:
                            return {
                                "success": True,
                                "data": {
                                    "id": str(user_id),
                                    "username": username,
                                    **user_data,
                                },
                            }

                except Exception:
                    pass

                if attempt < retries - 1:
                    time.sleep(delay)

            return None

        async with self._lock:
            result = await asyncio.to_thread(request_user_id)

        if not result:
            raise Exception(f"Akun Saweria dengan username '{username}' tidak ditemukan.")

        return result

    # ==========================================
    # CREATE PAYMENT / TRANSACTION
    # ==========================================

    async def create_transaction(
        self,
        amount: int,
        name: str = "NakaStore",
        email: str = "rezaandik145@gmail.com",
        msg: str = "Terima kasih",
        message: str = None,
        user_id: str = None,
        creator_name: str = "nsdev",
    ) -> dict:
        try:
            amount = int(amount)
        except (TypeError, ValueError) as exc:
            raise ValueError("amount harus berupa angka.") from exc

        if amount < 1000:
            raise ValueError("Jumlah minimum donasi adalah 1000.")

        account_id = str(
            user_id or SAWERIA_USER_ID or ""
        ).strip()

        if not account_id:
            raise ValueError("user_id wajib diisi.")

        final_message = message or msg or "Terima kasih"

        payload = {
            "agree": True,
            "notUnderage": True,
            "message": str(final_message),
            "amount": amount,
            "payment_type": "qris",
            "vote": "",
            "currency": "IDR",
            "customer_info": {
                "first_name": str(name or "NakaStore"),
                "email": str(email or "rezaandik145@gmail.com"),
                "phone": "",
            },
        }

        logger.info(
            "Creating Saweria payment: amount=%s, user_id=%s",
            amount,
            account_id,
        )

        def create():
            self._ensure_open()

            with self.scraper.post(
                f"{self.BACKEND}/donations/{account_id}",
                json=payload,
                headers=self.HEADERS,
                timeout=15,
            ) as res:
                if not res.ok:
                    raise RuntimeError(
                        f"Gagal membuat pembayaran Saweria: "
                        f"{res.status_code} {res.text[:300]}"
                    )

                body = res.json()
                data = body.get("data")

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "Response Saweria tidak memiliki data pembayaran."
                    )

                return data

        async with self._lock:
            data = await asyncio.to_thread(create)

        qr_string = str(data.get("qr_string") or "").strip()
        transaction_id = str(data.get("id") or "").strip()
        amount_raw = int(data.get("amount_raw") or amount)

        if not transaction_id:
            raise RuntimeError("Saweria tidak mengembalikan transaction ID.")

        if not qr_string:
            raise RuntimeError("Saweria tidak mengembalikan QR string.")

        qr_stream = generate_qr(qr_string)
        qr_stream.name = f"{transaction_id}.png"

        normalized_payment = {
            "id": transaction_id,
            "status": "unpaid",
            "qr_string": qr_string,
            "payment_url": f"https://saweria.co/qris/{transaction_id}",
            "amount": amount_raw,
            **data,
        }

        return {
            "success": True,
            "payment": normalized_payment,
            "transaction_id": transaction_id,
            "data": data,
            "qr_url": f"https://saweria.co/qris/{transaction_id}",
            "qr_stream": qr_stream,
            "amount": amount_raw,
        }

    # ==========================================
    # CHECK TRANSACTION STATUS
    # ==========================================

    async def check_transaction(
        self,
        payment_id: str = None,
        user_id: str = None,
        id: str = None,
    ) -> dict:
        transaction_id = str(payment_id or id or "").strip()

        if not transaction_id:
            raise ValueError("Query payment_id atau id wajib diisi.")

        logger.info("Checking Saweria transaction: %s", transaction_id)

        def check():
            self._ensure_open()

            with self.scraper.get(
                f"{self.BACKEND}/donations/qris/{transaction_id}",
                headers=self.HEADERS,
                timeout=15,
            ) as res:
                if not res.ok:
                    raise RuntimeError(
                        f"Transaction ID tidak ditemukan: {res.status_code}"
                    )

                body = res.json()
                data = body.get("data") or {}
                return data

        async with self._lock:
            data = await asyncio.to_thread(check)

        is_paid = str(data.get("qr_string") or "") == ""
        normalized_status = "paid" if is_paid else "unpaid"

        payment_obj = {
            "id": transaction_id,
            "status": normalized_status,
            **data,
        }

        logger.info(
            "Saweria transaction status: %s = %s",
            transaction_id,
            normalized_status,
        )

        return {
            "success": True,
            "payment": payment_obj,
            "data": data,
        }

    # ==========================================
    # CHECK PAID STATUS (HELPER BOOLEAN)
    # ==========================================

    async def check_paid_status(self, transaction_id: str) -> bool:
        transaction_id = str(transaction_id or "").strip()
        if not transaction_id:
            return False

        try:
            result = await self.check_transaction(payment_id=transaction_id)
            payment = result.get("payment", {})
            return payment.get("status") == "paid"
        except Exception:
            return False


saweria = Saweria()
