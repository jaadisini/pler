import aiosqlite
from config import DB_NAME

# ==========================================
# DATABASE
# ==========================================

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Menambahkan kolom photo_path ke tabel channels
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel_id TEXT NOT NULL UNIQUE,
                price INTEGER NOT NULL,
                description TEXT,
                photo_path TEXT
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                channel_id INTEGER NOT NULL,
                transaction_id TEXT NOT NULL UNIQUE,
                amount INTEGER NOT NULL,
                unique_amount INTEGER NOT NULL,
                qr_string TEXT NOT NULL,
                expired_at TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


# ==========================================
# CHANNEL
# ==========================================

async def add_channel(
    name,
    channel_id,
    price,
    description,
    photo_path,  # <-- Menerima parameter foto baru
):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            INSERT INTO channels(
                name,
                channel_id,
                price,
                description,
                photo_path
            )
            VALUES(?,?,?,?,?)
            ON CONFLICT(channel_id)
            DO UPDATE SET
                name=excluded.name,
                price=excluded.price,
                description=excluded.description,
                photo_path=excluded.photo_path
            """,
            (
                name,
                str(channel_id),
                price,
                description,
                photo_path,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM channels
            ORDER BY id ASC
            """
        )
        return await cursor.fetchall()


async def get_channel(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM channels
            WHERE id=?
            """,
            (channel_id,),
        )
        return await cursor.fetchone()


async def delete_channel(channel_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            DELETE FROM channels
            WHERE id=?
            """,
            (channel_id,),
        )
        await db.commit()


async def update_price(channel_id, price):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE channels
            SET price=?
            WHERE id=?
            """,
            (
                price,
                channel_id,
            ),
        )
        await db.commit()


# ==========================================
# ORDER
# ==========================================

async def create_order(
    user_id,
    username,
    channel_id,
    transaction_id,
    amount,
    unique_amount,
    qr_string,
    expired_at,
):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders(
                user_id,
                username,
                channel_id,
                transaction_id,
                amount,
                unique_amount,
                qr_string,
                expired_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                username,
                channel_id,
                transaction_id,
                amount,
                unique_amount,
                qr_string,
                expired_at,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(transaction_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM orders
            WHERE transaction_id=?
            """,
            (transaction_id,),
        )
        return await cursor.fetchone()


async def get_order_by_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return await cursor.fetchone()


async def get_active_order(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM orders
            WHERE user_id=?
            AND status='pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return await cursor.fetchone()


async def get_pending_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM orders
            WHERE status='pending'
            ORDER BY id ASC
            """
        )
        return await cursor.fetchall()


async def update_order_status(transaction_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            UPDATE orders
            SET status=?
            WHERE transaction_id=?
            """,
            (
                status,
                transaction_id,
            ),
        )
        await db.commit()


async def delete_expired_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """
            DELETE FROM orders
            WHERE status='expired'
            """
        )
        await db.commit()
