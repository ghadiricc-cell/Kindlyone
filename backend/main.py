import os
import sqlite3
import time
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "kindlyone.db")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "change-this-password"
)

ADMIN_SECRET = os.getenv(
    "ADMIN_SECRET",
    "change-this-secret"
)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Kindly One API",
    version="3.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# TIME
# =========================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# DATABASE
# =========================================================

class DBConnection:

    def __init__(self):

        self.is_postgres = bool(DATABASE_URL)

        if self.is_postgres:

            import psycopg
            from psycopg.rows import dict_row

            self.conn = psycopg.connect(
                DATABASE_URL,
                row_factory=dict_row
            )

        else:

            self.conn = sqlite3.connect(DB_PATH)

            self.conn.row_factory = sqlite3.Row

            self.conn.execute(
                "PRAGMA foreign_keys = ON"
            )

    def execute(self, query, params=None):

        if self.is_postgres:

            query = query.replace("?", "%s")

            cursor = self.conn.cursor()

            cursor.execute(
                query,
                params or ()
            )

            return DBCursor(
                cursor,
                self
            )

        return DBCursor(
            self.conn.execute(
                query,
                params or ()
            ),
            self
        )

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


class DBCursor:

    def __init__(
        self,
        cursor,
        connection
    ):

        self.cursor = cursor
        self.connection = connection

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):

        if not self.connection.is_postgres:
            return self.cursor.lastrowid

        result = self.connection.conn.execute(
            "SELECT lastval()"
        ).fetchone()

        if isinstance(result, dict):
            return list(result.values())[0]

        return result[0]


def get_db():
    return DBConnection()


def row_to_dict(row):
    return dict(row) if row else None


# =========================================================
# DATABASE INIT
# =========================================================

def init_db():

    conn = get_db()

    if conn.is_postgres:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                goal DOUBLE PRECISION NOT NULL DEFAULT 0,
                raised DOUBLE PRECISION NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'USDT',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id SERIAL PRIMARY KEY,
                currency TEXT NOT NULL,
                network TEXT NOT NULL,
                address TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                telegram_id TEXT NOT NULL,
                currency TEXT NOT NULL,
                network TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                wallet_address TEXT NOT NULL,
                tx_hash TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            )
        """)

    else:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                goal REAL NOT NULL DEFAULT 0,
                raised REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'USDT',
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                language TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT NOT NULL,
                network TEXT NOT NULL,
                address TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                telegram_id TEXT NOT NULL,
                currency TEXT NOT NULL,
                network TEXT NOT NULL,
                amount REAL NOT NULL,
                wallet_address TEXT NOT NULL,
                tx_hash TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            )
        """)

    conn.commit()

    # =====================================================
    # CASE SEED
    # =====================================================

    count = conn.execute(
        "SELECT COUNT(*) AS count FROM cases"
    ).fetchone()["count"]

    if count == 0:

        now = utc_now()

        conn.execute("""
            INSERT INTO cases
            (
                title,
                description,
                goal,
                raised,
                currency,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "کمک برای هزینه درمان",
            "یک انسان برای تأمین هزینه درمان خود به کمک نیاز دارد.",
            500,
            120,
            "USDT",
            "active",
            now
        ))

        conn.execute("""
            INSERT INTO cases
            (
                title,
                description,
                goal,
                raised,
                currency,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "کمک برای زندگی",
            "این کمک برای تأمین نیازهای ضروری زندگی یک خانواده است.",
            1000,
            350,
            "USDT",
            "active",
            now
        ))

    # =====================================================
    # WALLET SEED
    # =====================================================

    wallet_count = conn.execute(
        "SELECT COUNT(*) AS count FROM wallets"
    ).fetchone()["count"]

    if wallet_count == 0:

        now = utc_now()

        wallets = [

            (
                "USDT",
                "TRC20",
                "TEST_USDT_TRC20_ADDRESS"
            ),

            (
                "USDT",
                "BEP20",
                "TEST_USDT_BEP20_ADDRESS"
            ),

            (
                "BTC",
                "Bitcoin",
                "TEST_BTC_ADDRESS"
            ),

            (
                "ETH",
                "Ethereum",
                "TEST_ETH_ADDRESS"
            ),

            (
                "BNB",
                "BSC",
                "TEST_BNB_ADDRESS"
            ),

            (
                "SOL",
                "Solana",
                "TEST_SOL_ADDRESS"
            ),

            (
                "XAUT",
                "Ethereum",
                "TEST_XAUT_ADDRESS"
            ),

            (
                "XRP",
                "XRP Ledger",
                "TEST_XRP_ADDRESS"
            ),

            (
                "TRX",
                "TRON",
                "TEST_TRX_ADDRESS"
            )
        ]

        for currency, network, address in wallets:

            conn.execute("""
                INSERT INTO wallets
                (
                    currency,
                    network,
                    address,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (
                currency,
                network,
                address,
                now,
                now
            ))

    conn.commit()
    conn.close()


init_db()


# =========================================================
# MODELS
# =========================================================

class UserCreate(BaseModel):

    telegram_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    language: Optional[str] = None


class DonationCreate(BaseModel):

    case_id: int
    telegram_id: Optional[str] = None
    currency: str
    network: str
    amount: float


class DonationConfirm(BaseModel):

    tx_hash: str


class WalletCreate(BaseModel):

    currency: str
    network: str
    address: str
    status: str = "active"


class AdminLogin(BaseModel):

    password: str


class CaseCreate(BaseModel):

    title: str
    description: str
    goal: float
    currency: str = "USDT"
    status: str = "active"


class CaseUpdate(BaseModel):

    title: Optional[str] = None
    description: Optional[str] = None
    goal: Optional[float] = None
    raised: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None


class DonationStatusUpdate(BaseModel):

    status: str


# =========================================================
# HELPERS
# =========================================================

def normalize_telegram_id(value: Optional[str]) -> str:

    if value is None:
        return "web-user"

    value = str(value).strip()

    if not value:
        return "web-user"

    return value


# =========================================================
# ADMIN AUTH
# =========================================================

def create_admin_token():

    timestamp = str(int(time.time()))

    signature = hmac.new(
        ADMIN_SECRET.encode(),
        timestamp.encode(),
        hashlib.sha256
    ).hexdigest()

    raw = (
        f"{timestamp}.{signature}"
    ).encode()

    return base64.urlsafe_b64encode(
        raw
    ).decode()


def verify_admin_token(
    token: Optional[str]
):

    if not token:

        raise HTTPException(
            status_code=401,
            detail="Admin authentication required"
        )

    if token.startswith("Bearer "):
        token = token[7:]

    try:

        decoded = base64.urlsafe_b64decode(
            token.encode()
        ).decode()

        timestamp, signature = decoded.split(
            ".",
            1
        )

        expected = hmac.new(
            ADMIN_SECRET.encode(),
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            signature,
            expected
        ):

            raise HTTPException(
                status_code=401,
                detail="Invalid admin token"
            )

        if (
            int(time.time())
            - int(timestamp)
            > 86400
        ):

            raise HTTPException(
                status_code=401,
                detail="Admin token expired"
            )

        return True

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
            status_code=401,
            detail="Invalid admin token"
        )


def require_admin(
    authorization: Optional[str]
):

    verify_admin_token(
        authorization
    )


# =========================================================
# GENERAL
# =========================================================

@app.get("/")
def root():

    return {
        "success": True,
        "name": "Kindly One API",
        "version": "3.1.0",
        "database":
            "postgresql"
            if DATABASE_URL
            else "sqlite"
    }


@app.get("/api/health")
def health():

    return {
        "success": True,
        "status": "ok",
        "database":
            "postgresql"
            if DATABASE_URL
            else "sqlite"
    }


# =========================================================
# CASES
# =========================================================

@app.get("/api/cases")
def get_cases():

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM cases
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "cases": [
            row_to_dict(row)
            for row in rows
        ]
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: int):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM cases
        WHERE id = ?
        """,
        (case_id,)
    ).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    return {
        "success": True,
        "case": row_to_dict(row)
    }


@app.post("/api/admin/cases")
def admin_create_case(
    data: CaseCreate,
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    if data.goal < 0:

        raise HTTPException(
            status_code=400,
            detail="Goal cannot be negative"
        )

    conn = get_db()

    now = utc_now()

    cur = conn.execute("""
        INSERT INTO cases
        (
            title,
            description,
            goal,
            raised,
            currency,
            status,
            created_at
        )
        VALUES (?, ?, ?, 0, ?, ?, ?)
    """, (
        data.title,
        data.description,
        data.goal,
        data.currency,
        data.status,
        now
    ))

    conn.commit()

    case_id = cur.lastrowid

    row = conn.execute(
        """
        SELECT *
        FROM cases
        WHERE id = ?
        """,
        (case_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "case": row_to_dict(row)
    }


@app.put("/api/admin/cases/{case_id}")
def admin_update_case(
    case_id: int,
    data: CaseUpdate,
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    existing = conn.execute(
        """
        SELECT *
        FROM cases
        WHERE id = ?
        """,
        (case_id,)
    ).fetchone()

    if not existing:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )

    updates = data.model_dump(
        exclude_unset=True
    )

    allowed = {
        "title",
        "description",
        "goal",
        "raised",
        "currency",
        "status"
    }

    fields = []
    values = []

    for key, value in updates.items():

        if key in allowed:

            fields.append(
                f"{key} = ?"
            )

            values.append(value)

    if fields:

        values.append(case_id)

        conn.execute(
            f"""
            UPDATE cases
            SET {", ".join(fields)}
            WHERE id = ?
            """,
            values
        )

        conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM cases
        WHERE id = ?
        """,
        (case_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "case": row_to_dict(row)
    }


# =========================================================
# USERS
# =========================================================

@app.post("/api/users")
def create_or_update_user(
    data: UserCreate
):

    telegram_id = normalize_telegram_id(
        data.telegram_id
    )

    conn = get_db()

    now = utc_now()

    existing = conn.execute(
        """
        SELECT id
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    if existing:

        conn.execute("""
            UPDATE users
            SET first_name = ?,
                last_name = ?,
                username = ?,
                language = ?,
                last_seen = ?
            WHERE telegram_id = ?
        """, (
            data.first_name,
            data.last_name,
            data.username,
            data.language,
            now,
            telegram_id
        ))

    else:

        conn.execute("""
            INSERT INTO users
            (
                telegram_id,
                first_name,
                last_name,
                username,
                language,
                status,
                created_at,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            telegram_id,
            data.first_name,
            data.last_name,
            data.username,
            data.language,
            now,
            now
        ))

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "user": row_to_dict(row)
    }


@app.get("/api/users/{telegram_id}")
def get_user(
    telegram_id: str
):

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return {
        "success": True,
        "user": row_to_dict(row)
    }


@app.get("/api/users/{telegram_id}/donations")
def get_user_donations(
    telegram_id: str
):

    conn = get_db()

    rows = conn.execute("""
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        WHERE d.telegram_id = ?
        ORDER BY d.id DESC
    """, (
        telegram_id,
    )).fetchall()

    conn.close()

    return {
        "success": True,
        "donations": [
            row_to_dict(row)
            for row in rows
        ]
    }


# =========================================================
# WALLETS
# =========================================================

@app.get("/api/wallets")
def get_wallets():

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM wallets
        WHERE status = 'active'
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "wallets": [
            row_to_dict(row)
            for row in rows
        ]
    }


@app.get("/api/wallets/{currency}/{network}")
def get_wallet(
    currency: str,
    network: str
):

    conn = get_db()

    row = conn.execute("""
        SELECT *
        FROM wallets
        WHERE UPPER(currency) = UPPER(?)
          AND UPPER(network) = UPPER(?)
          AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
    """, (
        currency,
        network
    )).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    return {
        "success": True,
        "wallet": row_to_dict(row)
    }


@app.post("/api/wallets")
def create_wallet(
    data: WalletCreate,
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    now = utc_now()

    cur = conn.execute("""
        INSERT INTO wallets
        (
            currency,
            network,
            address,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.currency,
        data.network,
        data.address,
        data.status,
        now,
        now
    ))

    conn.commit()

    wallet_id = cur.lastrowid

    row = conn.execute(
        """
        SELECT *
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "wallet": row_to_dict(row)
    }


@app.put("/api/admin/wallets/{wallet_id}")
def update_wallet(
    wallet_id: int,
    data: WalletCreate,
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    existing = conn.execute(
        """
        SELECT id
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,)
    ).fetchone()

    if not existing:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    now = utc_now()

    conn.execute("""
        UPDATE wallets
        SET currency = ?,
            network = ?,
            address = ?,
            status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        data.currency,
        data.network,
        data.address,
        data.status,
        now,
        wallet_id
    ))

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM wallets
        WHERE id = ?
        """,
        (wallet_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "wallet": row_to_dict(row)
    }


# =========================================================
# DONATIONS
# =========================================================

@app.post("/api/donations")
def create_donation(
    data: DonationCreate
):

    conn = get_db()

    if data.amount <= 0:

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    case = conn.execute("""
        SELECT *
        FROM cases
        WHERE id = ?
          AND status = 'active'
    """, (
        data.case_id,
    )).fetchone()

    if not case:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Active case not found"
        )

    wallet = conn.execute("""
        SELECT *
        FROM wallets
        WHERE UPPER(currency) = UPPER(?)
          AND UPPER(network) = UPPER(?)
          AND status = 'active'
        ORDER BY id DESC
        LIMIT 1
    """, (
        data.currency,
        data.network
    )).fetchone()

    if not wallet:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Active wallet not found"
        )

    telegram_id = normalize_telegram_id(
        data.telegram_id
    )

    now = utc_now()

    cur = conn.execute("""
        INSERT INTO donations
        (
            case_id,
            telegram_id,
            currency,
            network,
            amount,
            wallet_address,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        data.case_id,
        telegram_id,
        data.currency,
        data.network,
        data.amount,
        wallet["address"],
        now,
        now
    ))

    conn.commit()

    donation_id = cur.lastrowid

    row = conn.execute(
        """
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        WHERE d.id = ?
        """,
        (donation_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,

        "donation_id": donation_id,

        "donation": row_to_dict(row),

        "wallet": {
            "id": wallet["id"],
            "currency": wallet["currency"],
            "network": wallet["network"],
            "address": wallet["address"]
        },

        "wallet_address": wallet["address"]
    }


@app.post("/api/donations/{donation_id}/confirm")
def confirm_donation(
    donation_id: int,
    data: DonationConfirm
):

    tx_hash = data.tx_hash.strip()

    if not tx_hash:

        raise HTTPException(
            status_code=400,
            detail="Transaction hash cannot be empty"
        )

    conn = get_db()

    row = conn.execute(
        """
        SELECT *
        FROM donations
        WHERE id = ?
        """,
        (donation_id,)
    ).fetchone()

    if not row:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Donation not found"
        )

    if row["status"] == "approved":

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Donation has already been approved"
        )

    if row["status"] == "rejected":

        conn.close()

        raise HTTPException(
            status_code=400,
            detail="Rejected donation cannot be confirmed"
        )

    now = utc_now()

    conn.execute("""
        UPDATE donations
        SET tx_hash = ?,
            status = 'submitted',
            updated_at = ?
        WHERE id = ?
    """, (
        tx_hash,
        now,
        donation_id
    ))

    conn.commit()

    updated = conn.execute(
        """
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        WHERE d.id = ?
        """,
        (donation_id,)
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "donation": row_to_dict(updated)
    }


@app.get("/api/donations/{donation_id}")
def get_donation(
    donation_id: int
):

    conn = get_db()

    row = conn.execute("""
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        WHERE d.id = ?
    """, (
        donation_id,
    )).fetchone()

    conn.close()

    if not row:

        raise HTTPException(
            status_code=404,
            detail="Donation not found"
        )

    return {
        "success": True,
        "donation": row_to_dict(row)
    }


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.post("/api/admin/login")
def admin_login(
    data: AdminLogin
):

    if not hmac.compare_digest(
        data.password,
        ADMIN_PASSWORD
    ):

        raise HTTPException(
            status_code=401,
            detail="Wrong password"
        )

    return {
        "success": True,
        "token": create_admin_token()
    }


# =========================================================
# ADMIN STATS
# =========================================================

@app.get("/api/admin/stats")
def admin_stats(
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    users = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    cases = conn.execute(
        "SELECT COUNT(*) AS count FROM cases"
    ).fetchone()["count"]

    active_cases = conn.execute("""
        SELECT COUNT(*) AS count
        FROM cases
        WHERE status = 'active'
    """).fetchone()["count"]

    donations = conn.execute(
        "SELECT COUNT(*) AS count FROM donations"
    ).fetchone()["count"]

    submitted = conn.execute("""
        SELECT COUNT(*) AS count
        FROM donations
        WHERE status = 'submitted'
    """).fetchone()["count"]

    approved = conn.execute("""
        SELECT COUNT(*) AS count
        FROM donations
        WHERE status = 'approved'
    """).fetchone()["count"]

    rejected = conn.execute("""
        SELECT COUNT(*) AS count
        FROM donations
        WHERE status = 'rejected'
    """).fetchone()["count"]

    total_approved = conn.execute("""
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total
        FROM donations
        WHERE status = 'approved'
    """).fetchone()["total"]

    conn.close()

    return {
        "success": True,
        "stats": {
            "users": users,
            "cases": cases,
            "active_cases": active_cases,
            "donations": donations,
            "submitted": submitted,
            "approved": approved,
            "rejected": rejected,
            "total_approved": total_approved
        }
    }


# =========================================================
# ADMIN USERS
# =========================================================

@app.get("/api/admin/users")
def admin_users(
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM users
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "users": [
            row_to_dict(row)
            for row in rows
        ]
    }


# =========================================================
# ADMIN CASES
# =========================================================

@app.get("/api/admin/cases")
def admin_cases(
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM cases
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "cases": [
            row_to_dict(row)
            for row in rows
        ]
    }


# =========================================================
# ADMIN WALLETS
# =========================================================

@app.get("/api/admin/wallets")
def admin_wallets(
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM wallets
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "wallets": [
            row_to_dict(row)
            for row in rows
        ]
    }


# =========================================================
# ADMIN DONATIONS
# =========================================================

@app.get("/api/admin/donations")
def admin_donations(
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    conn = get_db()

    rows = conn.execute("""
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        ORDER BY d.id DESC
    """).fetchall()

    conn.close()

    return {
        "success": True,
        "donations": [
            row_to_dict(row)
            for row in rows
        ]
    }


# =========================================================
# ADMIN DONATION STATUS
# =========================================================

@app.put("/api/admin/donations/{donation_id}/status")
def admin_update_donation_status(
    donation_id: int,
    data: DonationStatusUpdate,
    authorization: Optional[str] = Header(None)
):

    require_admin(authorization)

    allowed = {
        "pending",
        "submitted",
        "approved",
        "rejected"
    }

    if data.status not in allowed:

        raise HTTPException(
            status_code=400,
            detail="Invalid donation status"
        )

    conn = get_db()

    donation = conn.execute("""
        SELECT *
        FROM donations
        WHERE id = ?
    """, (
        donation_id,
    )).fetchone()

    if not donation:

        conn.close()

        raise HTTPException(
            status_code=404,
            detail="Donation not found"
        )

    old_status = donation["status"]
    new_status = data.status

    # =====================================================
    # APPROVE
    # =====================================================

    if (
        old_status != "approved"
        and new_status == "approved"
    ):

        conn.execute("""
            UPDATE cases
            SET raised = raised + ?
            WHERE id = ?
        """, (
            donation["amount"],
            donation["case_id"]
        ))

    # =====================================================
    # REMOVE APPROVAL
    # =====================================================

    elif (
        old_status == "approved"
        and new_status != "approved"
    ):

        if conn.is_postgres:

            conn.execute("""
                UPDATE cases
                SET raised = GREATEST(
                    0,
                    raised - ?
                )
                WHERE id = ?
            """, (
                donation["amount"],
                donation["case_id"]
            ))

        else:

            conn.execute("""
                UPDATE cases
                SET raised = MAX(
                    0,
                    raised - ?
                )
                WHERE id = ?
            """, (
                donation["amount"],
                donation["case_id"]
            ))

    now = utc_now()

    conn.execute("""
        UPDATE donations
        SET status = ?,
            updated_at = ?
        WHERE id = ?
    """, (
        new_status,
        now,
        donation_id
    ))

    conn.commit()

    updated = conn.execute("""
        SELECT
            d.*,
            c.title AS case_title
        FROM donations d
        LEFT JOIN cases c
            ON c.id = d.case_id
        WHERE d.id = ?
    """, (
        donation_id,
    )).fetchone()

    conn.close()

    return {
        "success": True,
        "donation": row_to_dict(updated)
    }