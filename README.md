# 💸 Personal Finance Assistant

A full-featured personal finance tracker built with **Streamlit** and **PostgreSQL**.  
It helps you track expenses, set budgets, split bills with friends (Splitwise-style), and get AI-powered insights with OpenAI.

---

## 🚀 Features
- 🔑 **User Authentication** (login/register with secure sessions)
- 📑 **Transactions** – Add & view income/expenses
- 💵 **Budgets** – Set monthly category-wise budgets
- 👥 **Friends** – Send/accept friend requests
- 💸 **Splits** – Share bills with friends (Splitwise-style) & settle balances
- 🚨 **Alerts** – Over-budget warnings, pending friend requests
- 📊 **Summary** – Income vs expenses overview + category pie chart
- 🤖 **AI Chatbot** – Natural language queries like:
  - *“How much did I spend on Food this month?”*
  - *“What’s my net savings?”*

---

## 🛠️ Tech Stack
- **Frontend:** Streamlit
- **Database:** PostgreSQL (via SQLAlchemy)
- **AI Assistant:** OpenAI GPT-4o
- **Auth & Cookies:** Bcrypt + EncryptedCookieManager

---

## 📂 Project Structure
Personal_Finance_Assistant/
├── app.py # Main Streamlit app
├── db.py # Database models & queries
├── requirements.txt # Python dependencies
├── README.md # Project documentation
└── .env.example # Environment variable template

## ⚙️ Setup & Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/Personal_Finance_Assistant.git
   cd Personal_Finance_Assistant
2. **Create a virtual environment**
```
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
```
3. **Install dependencies**
```
pip install -r requirements.txt
```
4. **Setup environment variables**
Copy .env.example → .env and update with your credentials:
```
cp .env.example .env
```
.env file should contain:
```
DATABASE_URL=postgresql+psycopg2://username:password@host:5432/your_database
OPENAI_API_KEY=your_openai_api_key_here
COOKIE_SECRET=your_cookie_secret_here
```
👉 Generate a secure cookie secret:
```
python -c "import secrets; print(secrets.token_hex(32))"
```
5. **Run the app**
```
streamlit run app.py
```