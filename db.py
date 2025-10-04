import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import datetime

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL, echo=False, future=True)

# ================= INIT =================
def init_db():
    with engine.begin() as conn:
        # Ensure users table exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(150) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            );
        """))

        # ✅ Ensure email column exists
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='users' AND column_name='email';
        """)).fetchone()

        if not result:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) UNIQUE;"))

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

        # Sessions table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL
        );
        """))

        # Reset tokens table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL
        );
        """))

        # Splits table
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

        # Friends table
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS friends (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            friend_id INT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending'
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
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO transactions (user_id, date, merchant, amount, category, type)
                VALUES (:user_id, :date, :merchant, :amount, :category, :type)
            """),
            {"user_id": user_id, "date": date, "merchant": merchant,
             "amount": amount, "category": category, "type": txn_type}
        )

def get_transactions(user_id):
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
def register_user(username, password_hash, email):
    """Register a new user with hashed password and email."""
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO users (username, password, email) VALUES (:u, :p, :e)"),
            {"u": username, "p": password_hash, "e": email}
        )

def get_user(username):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE username = :u"),
            {"u": username}
        ).fetchone()
        return dict(result._mapping) if result else None

def get_user_by_email(email):
    """Fetch a user by email."""
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE email = :e"),
            {"e": email}
        ).fetchone()
        return dict(result._mapping) if result else None



# ================= SESSIONS =================
def create_session(user_id, token):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO sessions (user_id, session_token) VALUES (:uid, :tok)"),
            {"uid": user_id, "tok": token}
        )

def get_user_by_session(token):
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
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sessions WHERE session_token = :tok"), {"tok": token})


# ================= FRIENDS =================
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
        conn.execute(text("UPDATE friends SET status = 'accepted' WHERE id = :rid"),
                     {"rid": request_id})

def get_friends(user_id):
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT * FROM friends
            WHERE (user_id = :uid OR friend_id = :uid) AND status = 'accepted'
        """), {"uid": user_id}).fetchall()
        return [dict(r._mapping) for r in result]

def get_user_by_id(user_id):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT * FROM users WHERE id = :uid"),
                              {"uid": user_id}).fetchone()
        return dict(result._mapping) if result else None


# ================= SPLITS =================
def add_split(user_id, friend_id, amount, description):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO splits (user_id, friend_id, amount, description, status)
                VALUES (:user_id, :friend_id, :amount, :desc, 'pending')
            """),
            {"user_id": user_id, "friend_id": friend_id, "amount": amount, "desc": description}
        )

def get_splits(user_id):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM splits WHERE user_id = :uid OR friend_id = :uid"),
            {"uid": user_id}
        ).fetchall()
        return [dict(r._mapping) for r in result]

def settle_split(split_id):
    with engine.begin() as conn:
        conn.execute(text("UPDATE splits SET status = 'settled' WHERE id = :sid"),
                     {"sid": split_id})


# ================= RESET TOKENS =================



def create_reset_token(user_id, token, expiry_minutes=60):
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiry_minutes)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO reset_tokens (user_id, token, expires_at)
            VALUES (:uid, :tok, :exp)
        """), {"uid": user_id, "tok": token, "exp": expires_at})

def get_user_by_token(token):
    """Get user_id from valid reset token."""
    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT u.id FROM users u
            JOIN reset_tokens r ON u.id = r.user_id
            WHERE r.token = :tok AND r.expires_at > NOW()
        """), {"tok": token}).fetchone()
        return result[0] if result else None   # ✅ return just user_id


def delete_token(token):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM reset_tokens WHERE token = :tok"), {"tok": token})
# ================= RESET TOKENS TABLE INIT (optional standalone) =================
def init_reset_tokens_table():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL
        );
        """))