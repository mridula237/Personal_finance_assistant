import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL, echo=False, future=True)

def init_db():
    """Initialize the database and ensure schema is up-to-date."""
    with engine.begin() as conn:
        # Create table if it does not exist
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

        # Ensure new column `type` exists (migration check)
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

def add_transaction(date, merchant, amount, category, txn_type):
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
                "type": txn_type   # ✅ ensure txn_type is mapped to "type"
            }
        )



def get_transactions():
    """Fetch all transactions."""
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM transactions ORDER BY date DESC"))
        return [dict(row._mapping) for row in result]
