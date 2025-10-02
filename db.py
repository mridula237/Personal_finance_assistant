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
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category VARCHAR(100) NOT NULL,
        amount NUMERIC NOT NULL,
        UNIQUE(user_id, category)
    );
"""))

        # Users table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(150) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        );
        """))

        # Sessions table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL
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
def add_transaction(user_id, date, merchant, amount, category, txn_type):
    """Insert a new transaction linked to a specific user."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO transactions (user_id, date, merchant, amount, category, type)
                VALUES (:user_id, :date, :merchant, :amount, :category, :type)
            """),
            {
                "user_id": user_id,
                "date": date,
                "merchant": merchant,
                "amount": amount,
                "category": category,
                "type": txn_type
            }
        )


def get_transactions(user_id):
    """Fetch all transactions for a given user."""
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM transactions WHERE user_id = :uid ORDER BY date DESC"),
            {"uid": user_id}
        )
        return [dict(row._mapping) for row in result]


# ================= BUDGETS =================
def set_budget(user_id, category, amount):
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT * FROM budgets WHERE user_id = :uid AND category = :cat"),
            {"uid": user_id, "cat": category}
        ).fetchone()

        if existing:
            conn.execute(
                text("UPDATE budgets SET amount = :amt WHERE user_id = :uid AND category = :cat"),
                {"amt": amount, "uid": user_id, "cat": category}
            )
        else:
            conn.execute(
                text("INSERT INTO budgets (user_id, category, amount) VALUES (:uid, :cat, :amt)"),
                {"uid": user_id, "cat": category, "amt": amount}
            )


def get_budgets(user_id):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT category, amount FROM budgets WHERE user_id = :uid"),
            {"uid": user_id}
        )
        return {row[0]: float(row[1]) for row in result}


# ================= USERS =================
def register_user(username, password_hash):
    """Register a new user with hashed password."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, password) VALUES (:u, :p)"),
            {"u": username, "p": password_hash}
        )

def get_user(username):
    """Fetch a user by username."""
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE username = :u"),
            {"u": username}
        ).fetchone()
        return dict(result._mapping) if result else None

# ================= SESSIONS =================
def create_session(user_id, token):
    """Create a session for a user."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO sessions (user_id, session_token) VALUES (:uid, :tok)"),
            {"uid": user_id, "tok": token}
        )

def get_user_by_session(token):
    """Retrieve user details from a session token."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT u.* FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.session_token = :tok
            """),
            {"tok": token}
        ).fetchone()
        return dict(result._mapping) if result else None

def delete_session(token):
    """Delete a session (logout)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sessions WHERE session_token = :tok"), {"tok": token})
        # ================= FRIENDS =================
def init_friends_table():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS friends (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            friend_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending'
        );
        """))

def send_friend_request(user_id, friend_id):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO friends (user_id, friend_id, status)
            VALUES (:user_id, :friend_id, 'pending')
        """), {"user_id": user_id, "friend_id": friend_id})

def get_friend_requests(user_id):
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT * FROM friends
            WHERE friend_id = :uid AND status = 'pending'
        """), {"uid": user_id}).fetchall()
        return [dict(r._mapping) for r in result]

def accept_friend_request(request_id):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE friends SET status = 'accepted' WHERE id = :rid
        """), {"rid": request_id})

def get_friends(user_id):
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT * FROM friends
            WHERE (user_id = :uid OR friend_id = :uid) AND status = 'accepted'
        """), {"uid": user_id}).fetchall()
        return [dict(r._mapping) for r in result]

def get_user_by_id(user_id):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
        return dict(result._mapping) if result else None
    
    # Splits table
def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS splits (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            friend_id INT REFERENCES users(id) ON DELETE CASCADE,
            amount NUMERIC NOT NULL,
            description VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending'
        );
        """))

        # ================= SPLITS =================
def add_split(user_id, friend_id, amount, description):
    """Add a new split expense."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO splits (user_id, friend_id, amount, description, status)
                VALUES (:user_id, :friend_id, :amount, :desc, 'pending')
            """),
            {"user_id": user_id, "friend_id": friend_id, "amount": amount, "desc": description}
        )

def get_splits(user_id):
    """Get all splits involving this user (both owing and owed)."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT * FROM splits
                WHERE user_id = :uid OR friend_id = :uid
            """),
            {"uid": user_id}
        ).fetchall()
        return [dict(r._mapping) for r in result]

def settle_split(split_id):
    """Mark a split as settled."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE splits SET status = 'settled' WHERE id = :sid"),
            {"sid": split_id}
        )
