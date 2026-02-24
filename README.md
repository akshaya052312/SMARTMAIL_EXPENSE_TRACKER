# 💰 SmartMail Expense Tracker

A **production-ready, full-stack expense tracking web application** built with Flask and SQLite. Automatically detects and logs expenses from your email inbox, supports manual entry, and provides rich analytics — all in a modern dark glassmorphism UI.

---

## ✨ Features

### 🔐 Authentication
- Secure user registration & login with hashed passwords
- Session-based authentication with Flask sessions
- Environment-variable-driven secret key for production security

### 📧 Email Auto-Sync
- Connects to Gmail / Outlook / Yahoo via IMAP
- Automatically detects transactions from emails (Zomato, Swiggy, Amazon, Flipkart, IRCTC, banks, etc.)
- Runs background sync every 60 seconds — no manual action needed
- Tracks processed emails to avoid duplicates

### 💸 Expense Management
- Add, edit, and delete expenses manually
- Fields: Amount (₹), Category, Merchant, Date, Payment Method, GST, Description
- Source tracking (Email auto-detected vs. Manual)
- Confidence score on auto-detected entries

### 📊 Dashboard
- Real-time summary cards: Total Spent, Avg Daily, Largest Transaction, Top Category, Email Detected
- Period selector: Week / Month / Year / Financial Year (Apr–Mar)
- Charts: Spending Trend, Category Breakdown, Payment Methods, Top Merchants

### 📈 Reports
- Detailed analytics with period filter
- Spending trend line chart & category distribution chart
- Full transactions table with search, category & payment filters
- Export to CSV

### 📅 Financial Calendar
- Monthly calendar view of expenses
- Click any day to see that day's transactions

### 🔔 Budget Management
- Set budgets per category or overall
- Configurable alert threshold (default 80%)
- Budget alerts stored and displayed in notifications

### 💳 Subscriptions Tracker
- Track recurring subscriptions (Netflix, Spotify, Jio, etc.)
- Frequency: Daily / Weekly / Monthly / Yearly
- Auto-detection from emails

### 📉 Investments Portfolio
- Track Mutual Funds, SIP, Stocks, FD, RD, PPF, NPS, Gold, Real Estate
- Profit/Loss calculation & portfolio breakdown chart
- Platform tracking (Groww, Zerodha, Upstox, etc.)

### ⚙️ Settings
- Indian Numbering System toggle (₹1,00,000 format)
- Date format preferences & category management
- Export all data as CSV

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.x, Flask 3.0 |
| Database | SQLite (via sqlite3) |
| Frontend | HTML5, CSS3 (Glassmorphism), Vanilla JS |
| Charts | Chart.js |
| Fonts | Google Fonts — Inter |
| Auth | Session-based (Flask sessions) |
| Email | IMAP (imaplib via EmailProcessor) |
| Config | python-dotenv |
| CORS | Flask-CORS |

---

## 📁 Project Structure

```
EXPENSE_TRACKER_IOMP/
├── app.py                  # Main Flask application & all API routes
├── email_processor.py      # IMAP email fetching & expense extraction
├── requirement.txt         # Python dependencies
├── .env                    # Environment variables (SECRET_KEY, etc.)
├── static/
│   ├── logo.svg            # App logo (SVG, theme-matched)
│   ├── style.css           # Global dark glassmorphism stylesheet
│   └── js/
│       └── app.js          # Shared JS utilities (INR formatter, auth helpers)
├── templates/
│   ├── index.html          # Landing page
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   ├── dashboard.html      # Main dashboard with charts
│   ├── reports.html        # Analytics & reports
│   ├── budgets.html        # Budget management
│   ├── subscriptions.html  # Subscription tracker
│   ├── investments.html    # Investment portfolio
│   ├── calendar.html       # Financial calendar
│   ├── notifications.html  # Notification centre
│   ├── settings.html       # App settings
│   └── email_config.html   # Email account configuration
└── instance/
    ├── expenses.db         # Main SQLite database
    └── email_configs.db    # Email configurations database
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9 or higher

### 2. Create & Activate Virtual Environment

**CMD:**
```
python -m venv akshu
akshu\Scripts\activate
```

**PowerShell:**
```
python -m venv akshu
akshu\Scripts\Activate.ps1
```

### 3. Install Dependencies
```
pip install -r requirement.txt
```

### 4. Configure Environment Variables
Edit the `.env` file in the project root:
```
SECRET_KEY=your-strong-secret-key-here
```

### 5. Run the App
```
akshu\Scripts\python.exe app.py
```

Open **http://localhost:5000** in your browser.

---

## 🔧 Environment Variables (.env)

| Variable | Description | Default |
|---|---|---|
| SECRET_KEY | Flask session secret key | smartmail-secret-key-change-in-production |

> Always change SECRET_KEY in production. Never commit .env to version control.

---

## 📧 Email Auto-Sync Setup

1. Log in → go to **Email Settings** in the navbar
2. Add your email account with an **App Password**
   - Gmail: https://myaccount.google.com/apppasswords
   - Outlook / Yahoo: Use app-specific passwords

| Provider | IMAP Server | Port |
|---|---|---|
| Gmail | imap.gmail.com | 993 |
| Outlook | outlook.office365.com | 993 |
| Yahoo | imap.mail.yahoo.com | 993 |

---

## 🌐 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/register | Register new user |
| POST | /api/login | Login |
| POST | /api/logout | Logout |
| GET | /api/expenses | Get expenses (with filters) |
| POST | /api/expenses | Add expense |
| PUT | /api/expenses/<id> | Edit expense |
| DELETE | /api/expenses/<id> | Delete expense |
| GET | /api/summary | Summary stats for a period |
| GET | /api/analytics/trends | Daily spending trend |
| GET | /api/budgets | Get budgets |
| GET | /api/subscriptions | Get subscriptions |
| GET | /api/investments | Get investments |
| GET | /api/notifications | Get notifications |
| GET | /api/email/sync-status | Check auto-sync status |

---

## 📦 Dependencies

```
flask==3.0.0
flask-cors==4.0.0
requests==2.31.0
python-dotenv==1.0.0
```

---

## 🎨 UI Theme

- **Style**: Dark Glassmorphism
- **Primary**: Indigo #6366f1 → Purple #8b5cf6
- **Background**: Deep navy #0a0a1a
- **Font**: Inter (Google Fonts)
- **Responsive**: Desktop, tablet & mobile

---

> Built with ❤️ for tracking every ₹ automatically 🇮🇳
