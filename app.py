import streamlit as st
import pandas as pd
from sqlalchemy import text
from db import (
    init_db, init_reset_tokens_table,
    add_transaction, get_transactions, engine,
    get_budgets, set_budget,
    register_user, get_user, get_user_by_email,
    create_session, get_user_by_session, delete_session,
    send_friend_request, get_friend_requests, accept_friend_request,
    get_friends, get_user_by_id, settle_split, add_split, get_splits,
    get_user_by_token, create_reset_token, delete_token
)
import os
from openai import OpenAI
import matplotlib.pyplot as plt
import re, string, html, uuid, bcrypt, secrets, smtplib
from email.mime.text import MIMEText
from streamlit_cookies_manager import EncryptedCookieManager

# ========== CACHE DB INIT ==========
@st.cache_resource
def setup_database():
    init_db()
    init_reset_tokens_table()
    return True

setup_database()

# ========== COOKIE MANAGER ==========
cookies = EncryptedCookieManager(prefix="finance_", password=os.getenv("COOKIE_SECRET", "supersecret"))
if not cookies.ready():
    st.stop()

# ========== AUTH HELPERS ==========
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

# ---------- SEND EMAIL HELPER ----------
def send_reset_email(to_email, reset_link):
    try:
        msg = MIMEText(f"Click here to reset your password: {reset_link}")
        msg["Subject"] = "Password Reset"
        msg["From"] = os.getenv("SMTP_FROM")
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            server.send_message(msg)

    except Exception as e:
        st.warning(f"⚠️ Could not send email. (Dev Mode link below)\n\nError: {e}")

# ---------- RESET PASSWORD SCREENS ----------
def reset_request_screen():
    st.title("🔑 Forgot Password")

    email = st.text_input("Enter your registered email")
    if st.button("Send Reset Link"):
        user = get_user_by_email(email)
        if not user:
            st.error("❌ Email not found")
        else:
            token = secrets.token_urlsafe(32)
            create_reset_token(user["id"], token)

            # NOTE: Replace with your deployed domain when live
            reset_link = f"http://localhost:8501/?token={token}"
            send_reset_email(email, reset_link)

            st.success("✅ Password reset link sent to your email.")
            st.info(f"(Dev Mode) Reset link: {reset_link}")  # remove in prod

def reset_password_screen(token):
    st.title("🔄 Reset Password")

    user_id = get_user_by_token(token)
    if not user_id:
        st.error("❌ Invalid or expired reset link")
        return

    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Reset Password"):
        if new_password != confirm_password:
            st.error("❌ Passwords do not match")
        else:
            hashed_pw = hash_password(new_password)
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE users SET password = :p WHERE id = :uid"),
                    {"p": hashed_pw, "uid": user_id}
                )
            delete_token(token)

            # ✅ Clear query params safely
            st.query_params.clear()

            # ✅ Rewrite URL (so ?token disappears)
            st.markdown(
                """
                <script>
                window.history.replaceState({}, document.title, window.location.pathname);
                </script>
                """,
                unsafe_allow_html=True
            )

            st.success("✅ Password reset successfully! Please login.")

            # ✅ Reset session flags
            st.session_state["show_reset_request"] = False
            st.session_state["password_reset_done"] = True

            # ✅ Stop execution cleanly, return to login
            st.stop()


# ---------- LOGIN SCREEN ----------
def login_screen():
    st.title("🔑 Login / Register")

    # Handle Forgot Password flow
    if st.session_state.get("show_reset_request", False):
        reset_request_screen()
        return

    # Handle token from query params
    qp = st.query_params
    token = None
    try:
        token = qp.get("token", None)
    except Exception:
        # Older versions may behave differently
        token = None

    if token:
        # If token is list-like in some versions, normalize
        if isinstance(token, list):
            token = token[0]
        reset_password_screen(token)
        return

    tab1, tab2 = st.tabs(["Login", "Register"])

    # ---- Login Tab ----
    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Login", use_container_width=True):
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

        with col2:
            if st.button("Forgot Password?", use_container_width=True):
                st.session_state["show_reset_request"] = True
                st.rerun()

    # ---- Register Tab ----
    with tab2:
        new_username = st.text_input("Choose Username", key="reg_user")
        new_email = st.text_input("Enter Email", key="reg_email")
        new_password = st.text_input("Choose Password", type="password", key="reg_pass")

        if st.button("Register"):
            if get_user(new_username):
                st.error("⚠️ Username already exists")
            else:
                register_user(new_username, hash_password(new_password), new_email)
                st.success("✅ Registered successfully! Please login.")

# ---------- SESSION HELPERS ----------
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

# ===== Sidebar =====
st.sidebar.write(f"👋 Welcome, **{user['username']}**")
if st.sidebar.button("Logout"):
    logout()

st.sidebar.header("🔍 Filters")
start_date = st.sidebar.date_input("Start Date")
end_date = st.sidebar.date_input("End Date")
filter_categories = st.sidebar.multiselect(
    "Category Filter",
    ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Bills", "Salary", "Other"]
)
apply_filters = st.sidebar.button("Apply Filters")

# Alerts Section
st.sidebar.header("🚨 Alerts")
friends_requests = get_friend_requests(user["id"])
if friends_requests:
    st.sidebar.warning(f"👥 You have {len(friends_requests)} friend request(s)")

# Fetch transactions for this user
transactions = get_transactions(user["id"])
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

# Over-budget alerts
budgets = get_budgets(user["id"])
monthly_totals = filtered_df.groupby("category")["amount"].sum() if not filtered_df.empty else {}
for category, budget in budgets.items():
    spent = float(monthly_totals.get(category, 0.0))
    if spent > budget:
        st.sidebar.error(f"⚠️ Over budget in {category}: ${spent - budget:.2f}")

# ---- Tabs Layout ----
tab1, tab3, tab4, tab5, tab6= st.tabs(
    ["📑 Transactions", "💰 Budgets", "👥 Friends", "🤖 Chatbot","💸 Splits"]
)

# ===================== TRANSACTIONS TAB =====================
with tab1:
    # ---- Summary FIRST ----
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

    st.markdown("---")  # separator

    # ---- Add Transaction Form ----
    st.subheader("➕ Add Transaction")
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            t_date = st.date_input("Date")
            t_merchant = st.text_input("Merchant")
        with col2:
            t_amount = st.number_input("Amount", min_value=0.0, step=0.01, key="txn_amount")
            t_type = st.selectbox("Type", ["Expense", "Income"], key="txn_type")
            t_category = st.selectbox(
                "Category",
                ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Bills", "Salary", "Other"],
                key="txn_category"
            )
        if st.button("Add Transaction", use_container_width=True):
            add_transaction(user["id"], t_date, t_merchant, t_amount, t_category, t_type)
            st.success("✅ Transaction added!")

    # ---- Show Transactions Table ----
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


# ===================== BUDGET TAB =====================
with tab3:
    st.subheader("💰 Budgets")
    budgets = get_budgets(user["id"])
    EXPENSE_CATEGORIES = ["Food & Drinks", "Travel", "Subscriptions", "Shopping", "Rent/Bills", "Other"]

    selected_category = st.selectbox("Select category to set budget", EXPENSE_CATEGORIES)
    budget_amount = st.number_input("Budget Amount", min_value=0, value=0, step=10)

    if st.button("Set Budget"):
        set_budget(user["id"], selected_category, budget_amount)
        st.success(f"Budget set for {selected_category}: ${budget_amount:.2f}")
        budgets = get_budgets(user["id"])

    if not filtered_df.empty:
        monthly_totals = filtered_df.groupby("category")["amount"].sum()
        for category, budget in budgets.items():
            spent = float(monthly_totals.get(category, 0.0))
            remaining = budget - spent
            st.write(f"**{category}**: ${spent:.2f} / ${budget:.2f}")
            progress = min(spent / budget, 1.0) if budget > 0 else 0
            st.progress(progress)
            if remaining < 0:
                st.error(f"⚠️ Over budget by ${-remaining:.2f}")
            else:
                st.success(f"✅ ${remaining:.2f} remaining")

# ===================== FRIENDS TAB =====================
with tab4:
    st.subheader("👥 Friends")
    current_user = get_current_user()
    if current_user:
        # Send friend request
        friend_username = st.text_input("Send request to (username):")
        if st.button("Send Friend Request"):
            friend = get_user(friend_username)
            if friend:
                send_friend_request(current_user["id"], friend["id"])
                st.success(f"✅ Friend request sent to {friend_username}")
            else:
                st.error("❌ User not found")

        # Show incoming requests
        st.subheader("Friend Requests")
        requests = get_friend_requests(current_user["id"])
        for req in requests:
            sender = get_user_by_id(req["user_id"])
            if st.button(f"Accept {sender['username']}", key=f"req_{req['id']}"):
                accept_friend_request(req["id"])
                st.success(f"✅ You are now friends with {sender['username']}")

        # Show friends
        st.subheader("My Friends")
        friends = get_friends(current_user["id"])
        if friends:
            for f in friends:
                fid = f["friend_id"] if f["user_id"] == current_user["id"] else f["user_id"]
                friend = get_user_by_id(fid)
                st.write(f"- {friend['username']}")
        else:
            st.info("No friends yet.")

# ===================== CHATBOT TAB =====================
# ===================== CHATBOT TAB =====================
with tab5:
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
        "Rent/Bills": ["rent", "bills", "house payment"],
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
            - The table schema is: transactions(id, date, merchant, amount, category, type, user_id).
            - Always include category AND amount in results where relevant.
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
            sql_query = re.sub(
                r"DATE_SUB\(CURRENT_DATE,\s*INTERVAL\s*30\s*DAY\)",
                "CURRENT_DATE - INTERVAL '30 days'",
                sql_query,
                flags=re.I
            )

            # ✅ inject user_id safely
            if "where" in sql_query.lower():
                sql_query = re.sub(
                    r"(?i)where",
                    f"WHERE user_id = {user['id']} AND ",
                    sql_query,
                    count=1
                )
            else:
                # Look for ORDER BY or LIMIT, insert WHERE before them
                insert_pos = len(sql_query)
                for keyword in ["order by", "limit"]:
                    match = re.search(rf"(?i){keyword}", sql_query)
                    if match:
                        insert_pos = match.start()
                        break
                sql_query = (
                    sql_query[:insert_pos].rstrip() +
                    f" WHERE user_id = {user['id']} " +
                    sql_query[insert_pos:]
                )

            # ✅ Patch missing GROUP BY if aggregate is used
            if re.search(r"SUM\(|AVG\(|COUNT\(", sql_query, re.I):
                if "group by" not in sql_query.lower():
                    if "category" in sql_query.lower():
                        sql_query += " GROUP BY category"

            if not sql_query.lower().startswith("select"):
                st.error("⚠️ Unsafe query detected! Only SELECT statements are allowed.")
            else:
                try:
                    with engine.begin() as conn:
                        rows = [dict(r._mapping) for r in conn.execute(text(sql_query))]
                    if rows:
                        df_result = pd.DataFrame(rows)

                        # ✅ Summarize results in plain English
                        summary_prompt = f"""
                        You are a financial assistant. Based on these SQL query results,
                        explain the answer to the user's question in plain English.
                        
                        Always mention BOTH the category and the amount.
                        
                        User question: {user_query}
                        Query results:
                        {df_result.to_string(index=False)}
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

                        with st.expander("Show query results"):
                            st.dataframe(df_result)

                    else:
                        st.info("ℹ️ No results found for your query.")
                except Exception as e:
                    st.error(f"⚠️ Could not process query. Please try rephrasing.\n\nError: {e}")



# ===================== SPLITS SECTION =====================
with tab6:    
    st.subheader("💸 Splits")

    # Add Split Section
    friends = get_friends(user["id"])
    if friends:
        friend_options = []
        for f in friends:
            fid = f["friend_id"] if f["user_id"] == user["id"] else f["user_id"]
            friend = get_user_by_id(fid)
            friend_options.append((friend["id"], friend["username"]))

        friend_map = {name: fid for fid, name in [(fid, uname) for fid, uname in friend_options]}
        selected_friend = st.selectbox("Select Friend", [uname for _, uname in friend_options])

        amount = st.number_input("Amount", min_value=0.0, step=0.01, key="split_amount")
        description = st.text_input("Description", key="split_description")

        if st.button("Add Split"):
            add_split(user["id"], friend_map[selected_friend], amount, description)
            st.success(f"✅ Added split: {selected_friend} owes you ${amount:.2f} for {description}")

    # Show Balances
    st.subheader("📊 Balances")
    splits = get_splits(user["id"])
    for s in splits:
        if s["status"] == "pending":
            if s["user_id"] == user["id"]:
                friend = get_user_by_id(s["friend_id"])
                st.write(f"💰 {friend['username']} owes you ${s['amount']} ({s['description']})")
            else:
                friend = get_user_by_id(s["user_id"])
                st.write(f"💸 You owe {friend['username']} ${s['amount']} ({s['description']})")
            
            if st.button(f"Settle Split {s['id']}", key=f"settle_{s['id']}"):
                settle_split(s["id"])
                st.success("✅ Split settled!")
