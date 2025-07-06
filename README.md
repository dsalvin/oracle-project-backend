# 🔮 **Oracle (Backend)**

This is the backend API for **Project Oracle** — a full-stack **Sales Forecasting Dashboard**.  
Built with **Python** & **FastAPI**, it handles **secure auth**, data processing, and **AI-powered time series forecasting**.

---

## ✨ **Features**

✅ **Secure Auth** — JWT-based user registration & login  
✅ **Social Logins** — Google OAuth2  
✅ **Data Upload** — Upload and validate CSV sales data  
✅ **AI Forecasting** — 30-day forecasts using Meta’s Prophet  
✅ **Insights & Analysis** — Historical trend analytics  
✅ **Exports** — Download forecast results as CSV

---

## ⚙️ **Tech Stack**

| Purpose          | Tech                                          |
|------------------|-----------------------------------------------|
| 🚀 Framework     | [FastAPI](https://fastapi.tiangolo.com/)      |
| 🗄️ Database      | SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| 🔒 Auth          | Passlib (hashing), python-jose (JWT), Authlib (OAuth) |
| 📊 Data & ML     | Pandas, Prophet                               |
| ⚡ ASGI Server   | Uvicorn                                       |

---

## ⚡ **Quickstart (Local Dev)**

### 1️⃣ Clone the project
```bash
git clone <your-repo-url>
cd oracle-project

2️⃣ Create & activate a virtual environment
bash
Copy
Edit
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
3️⃣ Install dependencies
bash
Copy
Edit
pip install -r requirements.txt
4️⃣ Configure environment variables
Create a .env file in the project root:

env
Copy
Edit
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
JWT_SECRET_KEY=a_long_random_string
SESSION_SECRET_KEY=another_long_random_string
⚠️ Do not commit .env — keep your secrets safe!

5️⃣ Run the server
bash
Copy
Edit
uvicorn main:app --reload
Your API will be running at: http://localhost:8000

📚 Project Structure
bash
Copy
Edit
oracle-project/
│
├── main.py          # FastAPI app entry point
├── auth.py          # Auth logic (JWT, OAuth)
├── models.py        # SQLAlchemy models
├── schemas.py       # Pydantic schemas
├── database.py      # DB connection & session
├── uploads/         # Uploaded CSV files
├── requirements.txt # Python dependencies
└── .env             # Environment variables (DO NOT COMMIT)
🙌 Contributing
PRs are welcome! For major changes, please open an issue first to discuss your ideas.
Don’t forget to add tests where applicable.

💙 License
MIT — do awesome stuff, but give credit.


