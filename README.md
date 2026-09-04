# FinTrack • Personal Expense & EMI Tracker App

A full-featured personal finance web application specifically built to track **Credit Card spends**, **Bank Account expenses**, **Personal Car Loan EMIs**, and **Credit Card EMIs**, with automated balance deductions, amortization schedules, and interactive financial dashboards.

Now equipped with **User ID & Password Authentication** and **Complete Multi-User Data Isolation** so you can safely run it on a local network or on the internet with full privacy.

---

## 🔒 User Privacy & Authentication

- **User Accounts**: Register your own private User ID and Password.
- **Salted Password Hashing**: Passwords are cryptographically hashed using `werkzeug.security` (`scrypt`/`pbkdf2:sha256`) before being stored in SQLite.
- **Per-User Data Isolation**: When you log in with your credentials, all bank accounts, credit cards, car loans, and expenses are strictly tied to your account. Other users cannot view or edit your data.
- **Default Demo Account**:
  - **User ID**: `admin`
  - **Password**: `admin123`
  *(Pre-loaded with sample Hyundai Creta car loan, HDFC Regalia credit card, and categorized expenses)*

---

## 🌟 Key Features

### 1. Dual-Source Expense Tracking (Bank Account vs. Credit Card)
- **Credit Card Spends**: Logs expenses to your specific credit card (e.g. HDFC Regalia, ICICI Amazon Pay), increasing current outstanding and updating available credit limit.
- **Bank Account Expenses**: Logs debits to your bank account (e.g. HDFC Salary, SBI Emergency Reserve), decreasing your available balance.
- **Credit Card Bill Payments**: One-click "Pay Bill" action that debits your chosen Bank Account and reduces/resets your Credit Card outstanding balance.

### 2. Personal Car Loan & EMI Management Hub
- **Dedicated Vehicle Loan Profile**: Displays car model/details, registration, lender bank, interest rate (reducing balance), tenure, and monthly EMI.
- **Payoff Countdown & Progress**: Visual progress bar showing principal paid vs. remaining balance and number of EMIs completed.
- **Complete Amortization Schedule**: Full month-by-month principal vs. interest breakdown, due dates, and payment status (`Paid` vs `Pending`).
- **Pay Next EMI**: Automatically debits the linked bank account and logs the EMI payment transaction with principal/interest split.
- **Credit Card EMI Support**: Converts large card transactions into 3/6/9/12 month EMIs.

### 3. Real-Time Visual Analytics & Dashboards
- **KPI Summary Cards**: Liquid Bank Balance, Credit Card Outstanding, Monthly Net Cashflow (Income vs Expenses), and Total Monthly EMI Outflow.
- **Upcoming Due Dates & Overdue Alerts**: Highlights loan EMIs and credit card bill payments due in the next 35 days.
- **Interactive Charts (Chart.js)**:
  - Donut Chart: Monthly spending by category.
  - Source Bar Chart: Bank Debits vs. Credit Card Spends vs. Loan EMIs.
  - 6-Month Trend Chart: Income vs Expenses vs EMI share over time.

### 4. Interactive EMI Calculator
- Simulate car loans or credit card purchases with sliders/inputs for Principal, Annual Interest Rate %, and Tenure.
- Instant Amortization table preview and Principal vs Interest ratio chart.

### 5. Private & Offline Local Storage
- Built-in SQLite database (`tracker.db`) with WAL mode.
- One-click CSV export of transaction ledger.
- One-click realistic Demo Data Reset & Seeding for your account.

---

## 🚀 Quickstart Guide

### Running the App:
Double-click `run.bat` or run the following command in PowerShell / Terminal:

```powershell
cd C:\Users\Sourav\.gemini\antigravity\scratch\expense-emi-tracker
py app.py
```

Then open your browser at:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🧪 Running Automated Tests

Run the test suite to verify user authentication, data isolation, EMI calculations, balance deductions, and API routes:

```powershell
py test_app.py
```
*(8/8 tests pass in ~2 seconds)*
