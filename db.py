import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL, echo=False, future=True)

# ================= INIT =================
def init_db():
    """Initialize the database and ensure schema is up-to-date."""
    with engine.begin() as conn:
        # Transactions table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            merchant VARCHAR(255),
            amount NUMERIC NOT NULL,
            category VARCHAR(100),
            type VARCHAR(50) DEFAULT 'Expense'
        );
        """))

        # Budgets table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY,
            category VARCHAR(100) UNIQUE,
            amount NUMERIC NOT NULL
        );
        """))

        # Migration check: ensure `type` column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='transactions';
        """))
        existing_columns = [row[0] for row in result]

        if "type" not in existing_columns:
            conn.execute(text("""
                ALTER TABLE transactions
                ADD COLUMN type VARCHAR(50) DEFAULT 'Expense';
            """))

# ================= TRANSACTIONS =================
def add_transaction(date, merchant, amount, category, txn_type):
    """Insert a new transaction."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO transactions (date, merchant, amount, category, type)
                VALUES (:date, :merchant, :amount, :category, :type)
            """),
            {
                "date": date,
                "merchant": merchant,
                "amount": amount,
                "category": category,
                "type": txn_type
            }
        )

def get_transactions():
    """Fetch all transactions."""
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM transactions ORDER BY date DESC"))
        return [dict(row._mapping) for row in result]

# ================= BUDGETS =================
def set_budget(category, amount):
    """Insert or update a budget for a given category."""
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT * FROM budgets WHERE category = :cat"),
            {"cat": category}
        ).fetchone()

        if existing:
            conn.execute(
                text("UPDATE budgets SET amount = :amt WHERE category = :cat"),
                {"amt": amount, "cat": category}
            )
        else:
            conn.execute(
                text("INSERT INTO budgets (category, amount) VALUES (:cat, :amt)"),
                {"cat": category, "amt": amount}
            )

def get_budgets():
    """Fetch all budgets as a dictionary {category: amount}."""
    with engine.begin() as conn:
        result = conn.execute(text("SELECT category, amount FROM budgets"))
        return {row[0]: float(row[1]) for row in result}
