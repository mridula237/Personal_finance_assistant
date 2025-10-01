import streamlit as st
import pandas as pd
from sqlalchemy import text
from db import (
    init_db, add_transaction, get_transactions, engine,
    get_budgets, set_budget,
    register_user, get_user, create_session, get_user_by_session, delete_session
)
import os
from openai import OpenAI
import matplotlib.pyplot as plt
import re
import string
import html 
import uuid
import bcrypt
from streamlit_cookies_manager import EncryptedCookieManager

# ========== INIT ==========
init_db()

# ========== COOKIE MANAGER ==========
cookies = EncryptedCookieManager(prefix="finance_", password=os.getenv("COOKIE_SECRET", "supersecret"))
if not cookies.ready():
    st.stop()

# ========== AUTH HELPERS ==========
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def login_screen():
    st.title("🔑 Login / Register")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            user = get_user(username)
            if user and verify_password(password, user["password"]):
                token = str(uuid.uuid4())
                create_session(user["id"], token)
                st.session_state["session_token"] = token
                cookies["session_token"] = token
                cookies.save()
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    with tab2:
        new_username = st.text_input("Choose Username", key="reg_user")
        new_password = st.text_input("Choose Password", type="password", key="reg_pass")
        if st.button("Register"):
            if get_user(new_username):
                st.error("⚠️ Username already exists")
            else:
                register_user(new_username, hash_password(new_password))
                st.success("✅ Registered successfully! Please login.")

def get_current_user():
    token = st.session_state.get("session_token") or cookies.get("session_token")
    if not token:
        return None
    return get_user_by_session(token)

def logout():
    token = st.session_state.get("session_token") or cookies.get("session_token")
    if token:
        delete_session(token)
    st.session_state.pop("session_token", None)
    cookies["session_token"] = ""
    cookies.save()
    st.rerun()

# ========== APP ENTRY ==========
user = get_current_user()
if not user:
    login_screen()
    st.stop()

# ===== If logged in, show dashboard =====
st.sidebar.write(f"👋 Welcome, **{user['username']}**")
if st.sidebar.button("Logout"):
    logout()

# ---------------- EXISTING APP CODE STARTS BELOW ----------------

def is_safe_sql(sql: str) -> bool:
    sql_lower = sql.lower().strip()
    if not sql_lower.startswith("select"):
        return False
    dangerous = ["drop", "delete", "alter", "insert", "update", "truncate"]
    return not any(word in sql_lower for word in dangerous)

st.title(" Personal Finance Assistant")

# ========== FILTERS ==========
st.sidebar.header("🔍 Filters")
start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")
filter_categories = st.sidebar.multiselect(
    "Category Filter",
    ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Mortgage", "Salary", "Other"]
)
apply_filters = st.sidebar.button("Apply Filters")

# Fetch transactions and apply filters
transactions = get_transactions()
df = pd.DataFrame(transactions) if transactions else pd.DataFrame()

filtered_df = df.copy()
if apply_filters and not df.empty:
    filtered_df["date"] = pd.to_datetime(filtered_df["date"])
    if start_date:
        filtered_df = filtered_df[filtered_df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered_df = filtered_df[filtered_df["date"] <= pd.to_datetime(end_date)]
    if filter_categories:
        filtered_df = filtered_df[filtered_df["category"].isin(filter_categories)]

# ========== BUDGET TRACKER ==========
st.sidebar.header("📊 Budget Tracker")
budgets = get_budgets()

EXPENSE_CATEGORIES = ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Mortgage", "Other"]

selected_category = st.sidebar.selectbox("Select category to set budget", EXPENSE_CATEGORIES)
budget_amount = st.sidebar.number_input("Budget Amount", min_value=0, value=0, step=10)

if st.sidebar.button("Set Budget"):
    set_budget(selected_category, budget_amount)
    st.sidebar.success(f"Budget set for {selected_category}: ${budget_amount:.2f}")
    budgets = get_budgets()

if not filtered_df.empty:
    monthly_totals = filtered_df.groupby("category")["amount"].sum()
    for category, budget in budgets.items():
        spent = float(monthly_totals.get(category, 0.0))
        remaining = budget - spent
        st.sidebar.write(f"**{category}**: ${spent:.2f} / ${budget:.2f}")
        progress = min(spent / budget, 1.0) if budget > 0 else 0
        st.sidebar.progress(progress)
        if remaining < 0:
            st.sidebar.error(f"⚠️ Over budget by ${-remaining:.2f}")
        else:
            st.sidebar.success(f"✅ ${remaining:.2f} remaining")

# ========== SUMMARY ==========
st.subheader("💵 Summary")
if not filtered_df.empty:
    total_income = float(filtered_df.loc[filtered_df["type"] == "Income", "amount"].sum())
    total_expenses = float(filtered_df.loc[filtered_df["type"] == "Expense", "amount"].sum())
    total_balance = total_income - total_expenses
else:
    total_income = total_expenses = total_balance = 0.0

c1, c2, c3 = st.columns(3)
c1.metric("Total Income", f"${total_income:,.2f}")
c2.metric("Total Expenses", f"${total_expenses:,.2f}")
c3.metric("Balance", f"${total_balance:,.2f}")

# ========== ADD TRANSACTION ==========
st.subheader("➕ Add Transaction")
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        t_date = st.date_input("Date")
        t_merchant = st.text_input("Merchant")
    with col2:
        t_amount = st.number_input("Amount", min_value=0.0, step=0.01)
        t_type = st.selectbox("Type", ["Expense", "Income"])
        t_category = st.selectbox(
            "Category",
            ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Mortgage", "Salary", "Other"]
        )
    if st.button("Add Transaction", use_container_width=True):
        add_transaction(t_date, t_merchant, t_amount, t_category, t_type)
        st.success("✅ Transaction added!")

# ========== TABLE + PIE ==========
if not filtered_df.empty:
    st.subheader("📊 All Transactions")
    if not st.session_state.get("show_all_transactions", False):
        preview_df = filtered_df.head(5)
        st.dataframe(preview_df, use_container_width=True)
        if len(filtered_df) > 5:
            if st.button("View All Transactions"):
                st.session_state["show_all_transactions"] = True
    else:
        st.dataframe(filtered_df, use_container_width=True)
        if st.button("Show Less"):
            st.session_state["show_all_transactions"] = False

# ========== CHATBOT ==========
st.subheader("🤖 Chatbot Assistant")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.markdown("### 🔎 Quick Questions")
preset_queries = [
    "How much did I spend on Food & Drinks this month?",
    "What’s my biggest expense this week?",
    "Show me all Travel expenses in the last 30 days.",
    "What’s my total spending by category?",
    "List my top 5 most expensive transactions.",
    "What’s my total income this month?",
    "Compare my income vs expenses this month.",
    "What’s my net savings this month?",
    "What is my budget for shopping?"
]

cols = st.columns(3)
for i, q in enumerate(preset_queries):
    if cols[i % 3].button(q):
        st.session_state["user_query"] = q

user_query = st.text_input("Or type your own question:", value=st.session_state.get("user_query", ""))

ALIAS_MAP = {
    "Food & Drinks": ["food & drinks", "food and drinks", "food", "groceries"],
    "Travel": ["travel", "trip", "flights", "tickets"],
    "Subscriptions": ["subscriptions", "subs", "netflix", "spotify", "apple", "prime"],
    "Shopping": ["shopping", "amazon", "clothes", "apparel"],
    "Rent/Mortgage": ["rent", "mortgage", "house payment"],
    "Other": ["other", "misc", "miscellaneous"]
}

def clean_text(s: str) -> str:
    s = s.lower()
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = re.sub(r"\s+", " ", s).strip()
    return s

def detect_budget_category(q: str):
    cq = clean_text(q)
    for canonical, aliases in ALIAS_MAP.items():
        for a in aliases:
            if a in cq:
                return canonical
    return None

if user_query:
    if "budget" in user_query.lower():
        cat = detect_budget_category(user_query)
        if cat:
            if cat in budgets:
                st.subheader("💡 Insight")
                st.write(f"Your budget for {cat} is set at ${budgets[cat]:.2f}.")
            else:
                st.info(f"No budget set for {cat}.")
        else:
            st.info("I couldn't detect a category from your question. Try: 'What is my budget for shopping?'")
    else:
        context = f"""
        You are an assistant that converts natural language into SQL for a PostgreSQL transactions database.
        - The table schema is: transactions(id, date, merchant, amount, category, type).
        - 'type' can be 'Expense' or 'Income'.
        - Use PostgreSQL syntax only (CURRENT_DATE, INTERVAL '30 days', DATE_TRUNC('month', CURRENT_DATE), etc.).
        - Only return SQL, no markdown.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": user_query}
            ]
        )
        sql_query = response.choices[0].message.content.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        sql_query = sql_query.replace("CURDATE()", "CURRENT_DATE")
        sql_query = re.sub(r"DATE_SUB\(CURRENT_DATE,\s*INTERVAL\s*30\s*DAY\)",
                           "CURRENT_DATE - INTERVAL '30 days'", sql_query, flags=re.I)
        if not is_safe_sql(sql_query):
            st.error("⚠️ Unsafe query detected! Only SELECT statements are allowed.")
        else:
            try:
                with engine.begin() as conn:
                    rows = [dict(r._mapping) for r in conn.execute(text(sql_query))]
                if rows:
                    df_result = pd.DataFrame(rows)
                    summary_prompt = f"""
                    You are a financial assistant. Based on these SQL query results,
                    create a concise, human-friendly summary. Avoid markdown formatting.
                    User question: {user_query}
                    Query results: {df_result.to_string(index=False)}
                    """
                    summary_response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": summary_prompt}]
                    )
                    ai_summary = summary_response.choices[0].message.content.strip()
                    ai_summary = re.sub(r"[*_]+", " ", ai_summary)
                    ai_summary = re.sub(r"\s+", " ", ai_summary).strip()
                    st.subheader("💡 Insight")
                    st.markdown(f"<pre>{html.escape(ai_summary)}</pre>", unsafe_allow_html=True)
                else:
                    st.info("ℹ️ No results found for your query.")
            except Exception as e:
                st.error(f"⚠️ Could not process query. Please try rephrasing.\n\nError: {e}")
