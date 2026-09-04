"""
models.py - Business logic, calculations, user authentication, and data access routines
for Personal Expense & EMI Tracker with per-user data isolation.
"""

from datetime import datetime, date
import calendar
import math
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection, seed_user_categories


def add_months(source_date: date, months: int) -> date:
    """Safely adds or subtracts months from a date without third-party dependencies."""
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ---------------------------------------------------------
# USER AUTHENTICATION & MANAGEMENT
# ---------------------------------------------------------

def register_user(username: str, password: str, full_name: str = "", email: str = "") -> dict:
    """
    Registers a new user, hashes password, seeds default categories, and returns user dict.
    """
    username = username.strip().lower()
    if not username or len(username) < 3:
        raise ValueError("Username must be at least 3 characters long.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters long.")

    conn = get_db_connection()
    cursor = conn.cursor()

    existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("Username is already taken. Please choose another.")

    pw_hash = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (username, password_hash, full_name, email)
        VALUES (?, ?, ?, ?)
    """, (username, pw_hash, full_name.strip() or username, email.strip()))
    user_id = cursor.lastrowid
    conn.commit()

    # Seed user default categories
    seed_user_categories(user_id, conn)

    user = cursor.execute("SELECT id, username, full_name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    user_dict = dict(user)
    conn.close()

    return user_dict


def authenticate_user(username: str, password: str) -> dict:
    """
    Verifies user credentials. Returns user dict on success or None on failure.
    """
    username = username.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if not user:
        return None

    if check_password_hash(user["password_hash"], password):
        user_dict = dict(user)
        user_dict.pop("password_hash", None)
        return user_dict

    return None


def get_user_by_id(user_id: int) -> dict:
    """Fetches user profile by ID without exposing password hash."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, full_name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


# ---------------------------------------------------------
# EMI & AMORTIZATION CALCULATIONS
# ---------------------------------------------------------

def calculate_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """
    Computes monthly EMI using standard reducing balance formula:
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    """
    if tenure_months <= 0 or principal <= 0:
        return 0.0

    monthly_rate = (annual_rate / 100.0) / 12.0
    if monthly_rate == 0:
        return round(principal / tenure_months, 2)

    factor = math.pow(1 + monthly_rate, tenure_months)
    emi = (principal * monthly_rate * factor) / (factor - 1)
    return round(emi, 2)


def generate_amortization_schedule(loan_id: int, principal: float, annual_rate: float,
                                   tenure_months: int, start_date_str: str,
                                   emi_day: int, emi_amount: float):
    """
    Generates and stores the full month-by-month amortization schedule for a loan.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    monthly_rate = (annual_rate / 100.0) / 12.0
    remaining = float(principal)
    
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()

    # Clear any existing schedule for this loan
    cursor.execute("DELETE FROM emi_schedule WHERE loan_id = ?", (loan_id,))

    for i in range(1, tenure_months + 1):
        due_month_dt = add_months(start_dt, i)
        max_day = calendar.monthrange(due_month_dt.year, due_month_dt.month)[1]
        actual_day = min(emi_day, max_day)
        due_date = date(due_month_dt.year, due_month_dt.month, actual_day).strftime("%Y-%m-%d")

        interest_component = round(remaining * monthly_rate, 2)
        principal_component = round(emi_amount - interest_component, 2)

        if i == tenure_months or principal_component > remaining:
            principal_component = round(remaining, 2)
            actual_emi = round(principal_component + interest_component, 2)
            remaining = 0.0
        else:
            remaining = round(remaining - principal_component, 2)
            actual_emi = emi_amount

        cursor.execute("""
            INSERT INTO emi_schedule (
                loan_id, installment_no, due_date, emi_amount,
                principal_component, interest_component, remaining_principal, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (loan_id, i, due_date, actual_emi, principal_component, interest_component, remaining))

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# ACCOUNT & BALANCE MANAGEMENT
# ---------------------------------------------------------

def recalculate_account_balance(account_id: int, user_id: int = None):
    """
    Recomputes the current balance/outstanding of an account based on its transactions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        acc = cursor.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id)).fetchone()
    else:
        acc = cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()

    if not acc:
        conn.close()
        return

    acc_type = acc["type"]

    if acc_type == "credit_card":
        spends = cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE account_id = ? AND type = 'expense'
        """, (account_id,)).fetchone()[0]

        payments = cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE to_account_id = ? AND type = 'cc_bill_payment'
        """, (account_id,)).fetchone()[0]

        refunds = cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE account_id = ? AND type = 'income'
        """, (account_id,)).fetchone()[0]

        new_outstanding = max(0.0, spends - payments - refunds)
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (round(new_outstanding, 2), account_id))
        conn.commit()

    conn.close()


def update_balances_for_transaction(tx_id: int, user_id: int = None, reverse: bool = False):
    """
    Adjusts account balances when a transaction is added, updated, or deleted.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id:
        tx = cursor.execute("SELECT * FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)).fetchone()
    else:
        tx = cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()

    if not tx:
        conn.close()
        return

    mult = -1 if reverse else 1
    amount = tx["amount"] * mult
    tx_type = tx["type"]
    acc_id = tx["account_id"]
    to_acc_id = tx["to_account_id"]

    acc = cursor.execute("SELECT * FROM accounts WHERE id = ?", (acc_id,)).fetchone()
    if acc:
        acc_type = acc["type"]
        if tx_type in ("expense", "emi_payment"):
            if acc_type in ("bank", "cash"):
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc_id))
            elif acc_type == "credit_card":
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, acc_id))
        elif tx_type == "income":
            if acc_type in ("bank", "cash"):
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, acc_id))
            elif acc_type == "credit_card":
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc_id))
        elif tx_type == "cc_bill_payment":
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc_id))
            if to_acc_id:
                cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, to_acc_id))
        elif tx_type == "transfer":
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, acc_id))
            if to_acc_id:
                cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_acc_id))

    conn.commit()
    conn.close()


# ---------------------------------------------------------
# LOAN & EMI ACTIONS
# ---------------------------------------------------------

def pay_loan_emi(loan_id: int, user_id: int = None, emi_schedule_id: int = None, installment_no: int = None,
                 payment_date: str = None, bank_account_id: int = None) -> dict:
    """
    Marks an EMI installment as paid and logs the corresponding expense in transactions,
    debiting the linked or selected bank account.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        loan = cursor.execute("SELECT * FROM loans WHERE id = ? AND user_id = ?", (loan_id, user_id)).fetchone()
    else:
        loan = cursor.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()

    if not loan:
        conn.close()
        raise ValueError("Loan not found")

    actual_user_id = user_id or loan["user_id"]
    pay_date = payment_date or date.today().strftime("%Y-%m-%d")
    debit_acc_id = bank_account_id or loan["linked_account_id"]

    if not debit_acc_id:
        fallback_acc = cursor.execute("""
            SELECT id FROM accounts WHERE user_id = ? AND type = 'bank' AND is_active = 1 LIMIT 1
        """, (actual_user_id,)).fetchone()
        if fallback_acc:
            debit_acc_id = fallback_acc["id"]
        else:
            conn.close()
            raise ValueError("No bank account available to debit EMI from.")

    # Find the installment
    if emi_schedule_id:
        installment = cursor.execute("SELECT * FROM emi_schedule WHERE id = ? AND loan_id = ?",
                                     (emi_schedule_id, loan_id)).fetchone()
    elif installment_no:
        installment = cursor.execute("SELECT * FROM emi_schedule WHERE installment_no = ? AND loan_id = ?",
                                     (installment_no, loan_id)).fetchone()
    else:
        installment = cursor.execute("""
            SELECT * FROM emi_schedule 
            WHERE loan_id = ? AND status IN ('pending', 'overdue')
            ORDER BY installment_no ASC LIMIT 1
        """, (loan_id,)).fetchone()

    if not installment:
        conn.close()
        raise ValueError("No pending installments found for this loan.")

    # Find category
    cat_name = "Car Loan EMI" if loan["type"] == "car_loan" else ("Credit Card EMI" if loan["type"] == "credit_card_emi" else "Bills & Utilities")
    cat = cursor.execute("SELECT id FROM categories WHERE user_id = ? AND name = ?", (actual_user_id, cat_name)).fetchone()
    cat_id = cat["id"] if cat else None

    desc = f"EMI Payment: {loan['name']} (Inst #{installment['installment_no']})"
    notes = f"Principal: ₹{installment['principal_component']:,.2f}, Interest: ₹{installment['interest_component']:,.2f}"

    cursor.execute("""
        INSERT INTO transactions (
            user_id, date, type, amount, category_id, account_id, loan_id, description, tags, notes
        ) VALUES (?, ?, 'emi_payment', ?, ?, ?, ?, ?, 'EMI,AutoDebit', ?)
    """, (actual_user_id, pay_date, installment["emi_amount"], cat_id, debit_acc_id, loan_id, desc, notes))
    tx_id = cursor.lastrowid

    cursor.execute("""
        UPDATE emi_schedule 
        SET status = 'paid', paid_date = ?, transaction_id = ?
        WHERE id = ?
    """, (pay_date, tx_id, installment["id"]))

    # Debit bank account
    cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (installment["emi_amount"], debit_acc_id))

    # Check if all installments are now paid
    pending_count = cursor.execute("""
        SELECT COUNT(*) FROM emi_schedule WHERE loan_id = ? AND status != 'paid'
    """, (loan_id,)).fetchone()[0]

    if pending_count == 0:
        cursor.execute("UPDATE loans SET status = 'closed' WHERE id = ?", (loan_id,))

    conn.commit()

    updated_inst = cursor.execute("SELECT * FROM emi_schedule WHERE id = ?", (installment["id"],)).fetchone()
    conn.close()

    return dict(updated_inst)


def pay_credit_card_bill(credit_card_id: int, bank_account_id: int, amount: float,
                         user_id: int, payment_date: str = None, notes: str = "") -> dict:
    """
    Pays credit card bill from bank account:
    - Debits bank account
    - Reduces credit card outstanding
    - Logs transaction of type 'cc_bill_payment'
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cc = cursor.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ? AND type = 'credit_card'",
                        (credit_card_id, user_id)).fetchone()
    bank = cursor.execute("SELECT * FROM accounts WHERE id = ? AND user_id = ? AND type in ('bank', 'cash')",
                          (bank_account_id, user_id)).fetchone()

    if not cc:
        conn.close()
        raise ValueError("Invalid Credit Card account.")
    if not bank:
        conn.close()
        raise ValueError("Invalid Bank Account to pay from.")

    pay_date = payment_date or date.today().strftime("%Y-%m-%d")
    cat = cursor.execute("SELECT id FROM categories WHERE user_id = ? AND name = 'Credit Card Bill Payment'", (user_id,)).fetchone()
    cat_id = cat["id"] if cat else None

    desc = f"Credit Card Bill Payment: {cc['name']}"

    cursor.execute("""
        INSERT INTO transactions (
            user_id, date, type, amount, category_id, account_id, to_account_id, description, tags, notes
        ) VALUES (?, ?, 'cc_bill_payment', ?, ?, ?, ?, ?, 'CCPayment,Bill', ?)
    """, (user_id, pay_date, amount, cat_id, bank_account_id, credit_card_id, desc, notes))
    tx_id = cursor.lastrowid

    # Deduct from bank
    cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, bank_account_id))
    # Deduct outstanding from credit card
    cursor.execute("UPDATE accounts SET balance = MAX(0.0, balance - ?) WHERE id = ?", (amount, credit_card_id))

    conn.commit()
    conn.close()

    return {"status": "success", "transaction_id": tx_id, "amount": amount}


# ---------------------------------------------------------
# DASHBOARD METRICS & ANALYTICS (PER USER)
# ---------------------------------------------------------

def get_dashboard_summary(user_id: int):
    """
    Returns aggregated metrics for the dashboard strictly isolated to the given user_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    cur_year_month = now.strftime("%Y-%m")
    cur_date_str = now.strftime("%Y-%m-%d")

    # 1. Accounts Totals for this user
    accounts = [dict(row) for row in cursor.execute("""
        SELECT * FROM accounts WHERE user_id = ? AND is_active = 1
    """, (user_id,)).fetchall()]
    
    total_bank_balance = sum(a["balance"] for a in accounts if a["type"] in ("bank", "cash"))
    total_cc_outstanding = sum(a["balance"] for a in accounts if a["type"] == "credit_card")
    total_cc_limit = sum(a["credit_limit"] for a in accounts if a["type"] == "credit_card")
    cc_utilization = round((total_cc_outstanding / total_cc_limit * 100), 1) if total_cc_limit > 0 else 0.0

    # 2. Current Month Totals
    month_income = cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'income'
    """, (user_id, cur_year_month)).fetchone()[0]

    month_expenses = cursor.execute("""
        SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
        WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type IN ('expense', 'emi_payment')
    """, (user_id, cur_year_month)).fetchone()[0]

    month_bank_spends = cursor.execute("""
        SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type IN ('expense', 'emi_payment') AND a.type = 'bank'
    """, (user_id, cur_year_month)).fetchone()[0]

    month_cc_spends = cursor.execute("""
        SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type = 'expense' AND a.type = 'credit_card'
    """, (user_id, cur_year_month)).fetchone()[0]

    month_emi_outflow = cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'emi_payment'
    """, (user_id, cur_year_month)).fetchone()[0]

    # 3. Dedicated Car Loan Widget data for this user
    car_loans = cursor.execute("""
        SELECT * FROM loans WHERE user_id = ? AND type = 'car_loan' AND status = 'active'
    """, (user_id,)).fetchall()
    car_loan_widget = None
    if car_loans:
        car_loan = dict(car_loans[0])
        sched = cursor.execute("""
            SELECT 
                COUNT(*) as total_installments,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_installments,
                SUM(CASE WHEN status = 'paid' THEN principal_component ELSE 0 END) as principal_paid,
                SUM(CASE WHEN status = 'paid' THEN interest_component ELSE 0 END) as interest_paid
            FROM emi_schedule WHERE loan_id = ?
        """, (car_loan["id"],)).fetchone()

        next_emi = cursor.execute("""
            SELECT * FROM emi_schedule 
            WHERE loan_id = ? AND status IN ('pending', 'overdue')
            ORDER BY installment_no ASC LIMIT 1
        """, (car_loan["id"],)).fetchone()

        total_inst = sched["total_installments"] or car_loan["tenure_months"]
        paid_inst = sched["paid_installments"] or 0
        principal_paid = sched["principal_paid"] or 0.0
        remaining_principal = max(0.0, car_loan["principal_amount"] - principal_paid)
        progress_pct = round((paid_inst / total_inst * 100), 1) if total_inst > 0 else 0.0

        car_loan_widget = {
            "loan": car_loan,
            "total_installments": total_inst,
            "paid_installments": paid_inst,
            "remaining_installments": total_inst - paid_inst,
            "principal_paid": round(principal_paid, 2),
            "remaining_principal": round(remaining_principal, 2),
            "interest_paid": round(sched["interest_paid"] or 0.0, 2),
            "progress_pct": progress_pct,
            "next_emi": dict(next_emi) if next_emi else None
        }

    # 4. Upcoming EMIs & Due Dates
    upcoming_emis = cursor.execute("""
        SELECT s.*, l.name as loan_name, l.type as loan_type, l.lender_bank, l.vehicle_details,
               a.name as linked_account_name
        FROM emi_schedule s
        JOIN loans l ON s.loan_id = l.id
        LEFT JOIN accounts a ON l.linked_account_id = a.id
        WHERE l.user_id = ? AND l.status = 'active' 
          AND (
            s.status = 'overdue' OR 
            (s.status = 'pending' AND s.due_date <= date(?, '+35 days'))
          )
        ORDER BY s.due_date ASC
        LIMIT 10
    """, (user_id, cur_date_str)).fetchall()

    upcoming_emis_list = []
    for emi_row in upcoming_emis:
        item = dict(emi_row)
        due_d = datetime.strptime(item["due_date"], "%Y-%m-%d").date()
        today_d = now.date()
        days_diff = (due_d - today_d).days
        item["days_left"] = days_diff
        if days_diff < 0 and item["status"] == "pending":
            item["status"] = "overdue"
        upcoming_emis_list.append(item)

    # 5. Credit Card Bill Payment Due Dates
    cc_dues = []
    for card in [a for a in accounts if a["type"] == "credit_card"]:
        due_day = card.get("payment_due_day") or 20
        if now.day > due_day:
            next_month_dt = add_months(now.date(), 1)
            due_date = date(next_month_dt.year, next_month_dt.month, min(due_day, calendar.monthrange(next_month_dt.year, next_month_dt.month)[1]))
        else:
            due_date = date(now.year, now.month, min(due_day, calendar.monthrange(now.year, now.month)[1]))

        days_left = (due_date - now.date()).days
        cc_dues.append({
            "account_id": card["id"],
            "name": card["name"],
            "last4": card["account_number_last4"],
            "outstanding": card["balance"],
            "limit": card["credit_limit"],
            "due_date": due_date.strftime("%Y-%m-%d"),
            "days_left": days_left
        })

    # 6. Expenses by Category (Current Month)
    category_spends = cursor.execute("""
        SELECT c.name, c.color, c.icon, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type IN ('expense', 'emi_payment')
        GROUP BY c.id
        ORDER BY total DESC
    """, (user_id, cur_year_month)).fetchall()

    category_data = [{
        "name": row["name"],
        "color": row["color"],
        "icon": row["icon"],
        "amount": round(row["total"], 2)
    } for row in category_spends]

    # 7. Recent 10 Transactions
    recent_transactions = cursor.execute("""
        SELECT t.*, c.name as category_name, c.icon as category_icon, c.color as category_color,
               a.name as account_name, a.type as account_type,
               to_a.name as to_account_name, l.name as loan_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts to_a ON t.to_account_id = to_a.id
        LEFT JOIN loans l ON t.loan_id = l.id
        WHERE t.user_id = ?
        ORDER BY t.date DESC, t.id DESC
        LIMIT 10
    """, (user_id,)).fetchall()

    # 8. Monthly 6-month Trend
    months_trend = []
    for m in range(5, -1, -1):
        target_month_dt = add_months(now.date(), -m)
        m_str = target_month_dt.strftime("%Y-%m")
        m_label = target_month_dt.strftime("%b %Y")

        inc = cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'income'
        """, (user_id, m_str)).fetchone()[0]

        bank_exp = cursor.execute("""
            SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type IN ('expense', 'emi_payment') AND a.type = 'bank'
        """, (user_id, m_str)).fetchone()[0]

        cc_exp = cursor.execute("""
            SELECT COALESCE(SUM(t.amount), 0) FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id = ? AND strftime('%Y-%m', t.date) = ? AND t.type = 'expense' AND a.type = 'credit_card'
        """, (user_id, m_str)).fetchone()[0]

        emi_exp = cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions
            WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'emi_payment'
        """, (user_id, m_str)).fetchone()[0]

        months_trend.append({
            "month": m_str,
            "label": m_label,
            "income": round(inc, 2),
            "bank_expenses": round(bank_exp, 2),
            "cc_expenses": round(cc_exp, 2),
            "emi_expenses": round(emi_exp, 2),
            "total_expenses": round(bank_exp + cc_exp, 2)
        })

    conn.close()

    return {
        "total_bank_balance": round(total_bank_balance, 2),
        "total_cc_outstanding": round(total_cc_outstanding, 2),
        "total_cc_limit": round(total_cc_limit, 2),
        "cc_utilization": cc_utilization,
        "month_income": round(month_income, 2),
        "month_expenses": round(month_expenses, 2),
        "month_bank_spends": round(month_bank_spends, 2),
        "month_cc_spends": round(month_cc_spends, 2),
        "month_emi_outflow": round(month_emi_outflow, 2),
        "net_cashflow": round(month_income - month_expenses, 2),
        "accounts": accounts,
        "car_loan_widget": car_loan_widget,
        "upcoming_emis": upcoming_emis_list,
        "cc_dues": cc_dues,
        "category_data": category_data,
        "recent_transactions": [dict(r) for r in recent_transactions],
        "months_trend": months_trend
    }
