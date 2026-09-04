"""
database.py - Database setup, migrations, and connection management for Personal Expense & EMI Tracker.
Includes multi-user support with secure password hashing and per-user data isolation.
"""

import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tracker.db"

DEFAULT_CATEGORIES = [
    # Expenses
    ("Car Loan EMI", "expense", "car", "#EF4444", 1),
    ("Credit Card EMI", "expense", "credit-card", "#F97316", 1),
    ("Fuel & Gas", "expense", "fuel", "#F59E0B", 1),
    ("Car Maintenance & Service", "expense", "wrench", "#EAB308", 1),
    ("Groceries & Supermarket", "expense", "shopping-cart", "#10B981", 1),
    ("Food & Dining Out", "expense", "utensils", "#06B6D4", 1),
    ("Shopping & Electronics", "expense", "shopping-bag", "#6366F1", 1),
    ("Bills & Utilities", "expense", "zap", "#8B5CF6", 1),
    ("Housing & Rent", "expense", "home", "#EC4899", 1),
    ("Healthcare & Medical", "expense", "heart-pulse", "#14B8A6", 1),
    ("Travel & Transportation", "expense", "plane", "#3B82F6", 1),
    ("Entertainment & Subscriptions", "expense", "film", "#A855F7", 1),
    ("Credit Card Bill Payment", "expense", "receipt", "#64748B", 1),
    ("General & Miscellaneous", "expense", "more-horizontal", "#94A3B8", 1),
    # Income
    ("Salary", "income", "briefcase", "#22C55E", 1),
    ("Freelance / Consulting", "income", "laptop", "#10B981", 1),
    ("Investments & Dividends", "income", "trending-up", "#3B82F6", 1),
    ("Cashback & Rewards", "income", "gift", "#F59E0B", 1),
    ("Other Income", "income", "plus-circle", "#8B5CF6", 1),
]


def get_db_connection():
    """Returns a SQLite connection with dict-like row access and WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def _get_table_columns(cursor, table_name):
    """Returns set of column names for a given table."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return {row[1] for row in cursor.fetchall()}


def seed_user_categories(user_id: int, conn=None):
    """Seeds default categories for a specific user if they don't already have them."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    cursor = conn.cursor()
    for name, cat_type, icon, color, is_default in DEFAULT_CATEGORIES:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (user_id, name, type, icon, color, is_default)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, name, cat_type, icon, color, is_default))

    conn.commit()
    if should_close:
        conn.close()


def init_db():
    """Initializes SQLite tables, runs migrations for user_id, and creates default admin."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 2. Accounts Table (Bank, Credit Card, Cash)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('bank', 'credit_card', 'cash')),
            account_number_last4 TEXT DEFAULT '',
            balance REAL NOT NULL DEFAULT 0.0,
            credit_limit REAL DEFAULT 0.0,
            billing_cycle_day INTEGER DEFAULT 1,
            payment_due_day INTEGER DEFAULT 20,
            color TEXT DEFAULT '#3B82F6',
            icon TEXT DEFAULT 'credit-card',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 3. Categories Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('expense', 'income')),
            icon TEXT DEFAULT 'tag',
            color TEXT DEFAULT '#64748B',
            is_default INTEGER DEFAULT 0,
            UNIQUE(user_id, name)
        );
    """)

    # 4. Loans Table (Car Loan, CC EMI, Personal Loan, Home Loan, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('car_loan', 'personal_loan', 'credit_card_emi', 'home_loan', 'other')),
            lender_bank TEXT DEFAULT '',
            vehicle_details TEXT DEFAULT '',
            principal_amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            tenure_months INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            emi_amount REAL NOT NULL,
            emi_day_of_month INTEGER DEFAULT 5,
            linked_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'closed')),
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 5. Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('expense', 'income', 'transfer', 'cc_bill_payment', 'emi_payment')),
            amount REAL NOT NULL,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            to_account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
            loan_id INTEGER REFERENCES loans(id) ON DELETE SET NULL,
            description TEXT NOT NULL,
            tags TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)

    # 6. EMI Schedule Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emi_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
            installment_no INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            paid_date TEXT DEFAULT NULL,
            emi_amount REAL NOT NULL,
            principal_component REAL NOT NULL,
            interest_component REAL NOT NULL,
            remaining_principal REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'paid', 'overdue')),
            transaction_id INTEGER DEFAULT NULL REFERENCES transactions(id) ON DELETE SET NULL
        );
    """)

    # Perform Column Migrations if user_id was missing in existing DB
    tables_to_migrate = ["accounts", "categories", "loans", "transactions"]
    for tbl in tables_to_migrate:
        cols = _get_table_columns(cursor, tbl)
        if "user_id" not in cols:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;")

    # Check if any user exists; if none, create default admin
    user_count = cursor.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
    default_user_id = 1
    if user_count == 0:
        pw_hash = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, email)
            VALUES ('admin', ?, 'Admin User', 'admin@example.com')
        """, (pw_hash,))
        default_user_id = cursor.lastrowid

    # Assign default_user_id to any pre-existing rows without user_id
    for tbl in tables_to_migrate:
        cursor.execute(f"UPDATE {tbl} SET user_id = ? WHERE user_id IS NULL;", (default_user_id,))

    # Seed default categories for default admin user
    seed_user_categories(default_user_id, conn)

    # Create Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_user ON transactions(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_date ON transactions(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_acc ON transactions(account_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_acc_user ON accounts(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_loans_user ON loans(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emi_loan ON emi_schedule(loan_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emi_due ON emi_schedule(due_date);")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with user authentication at:", DB_PATH)
