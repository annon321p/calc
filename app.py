"""
app.py - Personal Expense & EMI Tracker Web Application
Built with Flask & SQLite with User Authentication and Private Data Isolation.
"""

import os
import json
import csv
import io
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from database import init_db, get_db_connection
from models import (
    calculate_emi, generate_amortization_schedule,
    recalculate_account_balance, update_balances_for_transaction,
    pay_loan_emi, pay_credit_card_bill, get_dashboard_summary, add_months,
    register_user, authenticate_user, get_user_by_id
)
from seed_data import seed_database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fintrack-secret-key-salt-2026-secure-session")
app.config["JSON_SORT_KEYS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# Initialize database on startup
init_db()


def login_required(f):
    """Decorator requiring a logged-in user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "auth_required": True}), 401
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------
# PAGE ROUTES
# ---------------------------------------------------------

@app.route("/")
def index():
    """Serves the main single page application."""
    return render_template("index.html")


# ---------------------------------------------------------
# AUTHENTICATION API
# ---------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip()

    try:
        user = register_user(username, password, full_name, email)
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return jsonify({"status": "success", "user": user}), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": "Registration failed. Please try again."}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    user = authenticate_user(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"status": "success", "user": user})


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"})


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 200

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 200

    return jsonify({"authenticated": True, "user": user})


# ---------------------------------------------------------
# DASHBOARD API
# ---------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard():
    """Returns aggregated summary metrics strictly for the logged-in user."""
    try:
        user_id = session["user_id"]
        data = get_dashboard_summary(user_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# ACCOUNTS API (Bank, Credit Card, Cash)
# ---------------------------------------------------------

@app.route("/api/accounts", methods=["GET"])
@login_required
def api_get_accounts():
    user_id = session["user_id"]
    conn = get_db_connection()
    accounts = [dict(r) for r in conn.execute("""
        SELECT * FROM accounts WHERE user_id = ? AND is_active = 1 ORDER BY type, name
    """, (user_id,)).fetchall()]
    conn.close()

    for acc in accounts:
        if acc["type"] == "credit_card":
            limit = acc["credit_limit"] or 0.0
            outstanding = acc["balance"] or 0.0
            acc["available_limit"] = max(0.0, limit - outstanding)
            acc["utilization_pct"] = round((outstanding / limit * 100), 1) if limit > 0 else 0.0

    return jsonify(accounts)


@app.route("/api/accounts", methods=["POST"])
@login_required
def api_create_account():
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("name", "").strip()
    acc_type = data.get("type", "bank")
    balance = float(data.get("balance", 0.0))
    limit = float(data.get("credit_limit", 0.0)) if acc_type == "credit_card" else 0.0
    last4 = data.get("account_number_last4", "").strip()
    billing_day = int(data.get("billing_cycle_day", 1)) if acc_type == "credit_card" else 1
    due_day = int(data.get("payment_due_day", 20)) if acc_type == "credit_card" else 20
    color = data.get("color", "#3B82F6")
    icon = data.get("icon", "credit-card" if acc_type == "credit_card" else "building-2")

    if not name:
        return jsonify({"error": "Account name is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO accounts (user_id, name, type, account_number_last4, balance, credit_limit,
                              billing_cycle_day, payment_due_day, color, icon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, acc_type, last4, balance, limit, billing_day, due_day, color, icon))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "id": new_id, "message": "Account created successfully"}), 201


@app.route("/api/accounts/<int:account_id>", methods=["PUT"])
@login_required
def api_update_account(account_id):
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("name")
    balance = data.get("balance")
    limit = data.get("credit_limit")
    last4 = data.get("account_number_last4")
    billing_day = data.get("billing_cycle_day")
    due_day = data.get("payment_due_day")
    color = data.get("color")
    icon = data.get("icon")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE accounts SET
            name = COALESCE(?, name),
            balance = COALESCE(?, balance),
            credit_limit = COALESCE(?, credit_limit),
            account_number_last4 = COALESCE(?, account_number_last4),
            billing_cycle_day = COALESCE(?, billing_cycle_day),
            payment_due_day = COALESCE(?, payment_due_day),
            color = COALESCE(?, color),
            icon = COALESCE(?, icon)
        WHERE id = ? AND user_id = ?
    """, (name, balance, limit, last4, billing_day, due_day, color, icon, account_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Account updated"})


@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
@login_required
def api_delete_account(account_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions WHERE account_id = ? AND user_id = ?",
                            (account_id, user_id)).fetchone()[0]
    if tx_count > 0:
        conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ? AND user_id = ?", (account_id, user_id))
    else:
        conn.execute("DELETE FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Account deleted"})


@app.route("/api/accounts/<int:account_id>/pay-bill", methods=["POST"])
@login_required
def api_pay_credit_card_bill(account_id):
    user_id = session["user_id"]
    data = request.json or {}
    bank_account_id = data.get("bank_account_id")
    amount = float(data.get("amount", 0.0))
    payment_date = data.get("payment_date") or date.today().strftime("%Y-%m-%d")
    notes = data.get("notes", "")

    if not bank_account_id or amount <= 0:
        return jsonify({"error": "Valid bank account and amount greater than 0 required"}), 400

    try:
        res = pay_credit_card_bill(account_id, int(bank_account_id), amount, user_id=user_id,
                                   payment_date=payment_date, notes=notes)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------
# LOANS & EMI API
# ---------------------------------------------------------

@app.route("/api/loans", methods=["GET"])
@login_required
def api_get_loans():
    user_id = session["user_id"]
    conn = get_db_connection()
    loans = [dict(r) for r in conn.execute("""
        SELECT l.*, a.name as linked_account_name, a.type as linked_account_type
        FROM loans l
        LEFT JOIN accounts a ON l.linked_account_id = a.id
        WHERE l.user_id = ?
        ORDER BY l.status, l.id DESC
    """, (user_id,)).fetchall()]

    for loan in loans:
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_installments,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_installments,
                SUM(CASE WHEN status = 'paid' THEN principal_component ELSE 0 END) as principal_paid,
                SUM(CASE WHEN status = 'paid' THEN interest_component ELSE 0 END) as interest_paid
            FROM emi_schedule WHERE loan_id = ?
        """, (loan["id"],)).fetchone()

        next_emi = conn.execute("""
            SELECT * FROM emi_schedule 
            WHERE loan_id = ? AND status IN ('pending', 'overdue')
            ORDER BY installment_no ASC LIMIT 1
        """, (loan["id"],)).fetchone()

        total_inst = stats["total_installments"] or loan["tenure_months"]
        paid_inst = stats["paid_installments"] or 0
        principal_paid = stats["principal_paid"] or 0.0
        remaining_principal = max(0.0, loan["principal_amount"] - principal_paid)
        progress = round((paid_inst / total_inst * 100), 1) if total_inst > 0 else 0.0

        loan["paid_installments"] = paid_inst
        loan["total_installments"] = total_inst
        loan["principal_paid"] = round(principal_paid, 2)
        loan["remaining_principal"] = round(remaining_principal, 2)
        loan["interest_paid"] = round(stats["interest_paid"] or 0.0, 2)
        loan["progress_pct"] = progress
        loan["next_emi"] = dict(next_emi) if next_emi else None

    conn.close()
    return jsonify(loans)


@app.route("/api/loans/<int:loan_id>", methods=["GET"])
@login_required
def api_get_loan_detail(loan_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    loan = conn.execute("""
        SELECT l.*, a.name as linked_account_name
        FROM loans l
        LEFT JOIN accounts a ON l.linked_account_id = a.id
        WHERE l.id = ? AND l.user_id = ?
    """, (loan_id, user_id)).fetchone()

    if not loan:
        conn.close()
        return jsonify({"error": "Loan not found"}), 404

    loan_dict = dict(loan)
    schedule = [dict(r) for r in conn.execute("""
        SELECT * FROM emi_schedule WHERE loan_id = ? ORDER BY installment_no ASC
    """, (loan_id,)).fetchall()]
    conn.close()

    loan_dict["schedule"] = schedule
    return jsonify(loan_dict)


@app.route("/api/loans", methods=["POST"])
@login_required
def api_create_loan():
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("name", "").strip()
    loan_type = data.get("type", "car_loan")
    lender = data.get("lender_bank", "").strip()
    vehicle = data.get("vehicle_details", "").strip()
    principal = float(data.get("principal_amount", 0.0))
    rate = float(data.get("interest_rate", 0.0))
    tenure = int(data.get("tenure_months", 12))
    start_date = data.get("start_date") or date.today().strftime("%Y-%m-%d")
    emi_day = int(data.get("emi_day_of_month", 5))
    linked_acc = data.get("linked_account_id")
    notes = data.get("notes", "").strip()

    if not name or principal <= 0 or tenure <= 0:
        return jsonify({"error": "Valid loan name, principal and tenure required"}), 400

    emi = calculate_emi(principal, rate, tenure)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO loans (
            user_id, name, type, lender_bank, vehicle_details, principal_amount,
            interest_rate, tenure_months, start_date, emi_amount, emi_day_of_month,
            linked_account_id, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
    """, (user_id, name, loan_type, lender, vehicle, principal, rate, tenure, start_date, emi, emi_day, linked_acc, notes))
    loan_id = cursor.lastrowid
    conn.commit()
    conn.close()

    generate_amortization_schedule(loan_id, principal, rate, tenure, start_date, emi_day, emi_amount=emi)

    return jsonify({"status": "success", "id": loan_id, "emi_amount": emi}), 201


@app.route("/api/loans/<int:loan_id>", methods=["DELETE"])
@login_required
def api_delete_loan(loan_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    conn.execute("DELETE FROM loans WHERE id = ? AND user_id = ?", (loan_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Loan and schedule deleted"})


@app.route("/api/loans/<int:loan_id>/pay-emi", methods=["POST"])
@login_required
def api_pay_loan_emi(loan_id):
    user_id = session["user_id"]
    data = request.json or {}
    schedule_id = data.get("emi_schedule_id")
    inst_no = data.get("installment_no")
    pay_date = data.get("payment_date") or date.today().strftime("%Y-%m-%d")
    bank_acc_id = data.get("bank_account_id")

    try:
        updated_inst = pay_loan_emi(
            loan_id=loan_id,
            user_id=user_id,
            emi_schedule_id=schedule_id,
            installment_no=inst_no,
            payment_date=pay_date,
            bank_account_id=bank_acc_id
        )
        return jsonify({"status": "success", "installment": updated_inst})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------
# TRANSACTIONS & EXPENSES API
# ---------------------------------------------------------

@app.route("/api/transactions", methods=["GET"])
@login_required
def api_get_transactions():
    user_id = session["user_id"]
    month = request.args.get("month")
    account_id = request.args.get("account_id")
    category_id = request.args.get("category_id")
    tx_type = request.args.get("type")
    query = request.args.get("q", "").strip()

    sql = """
        SELECT t.*, c.name as category_name, c.icon as category_icon, c.color as category_color,
               a.name as account_name, a.type as account_type,
               to_a.name as to_account_name, l.name as loan_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts to_a ON t.to_account_id = to_a.id
        LEFT JOIN loans l ON t.loan_id = l.id
        WHERE t.user_id = ?
    """
    params = [user_id]

    if month:
        sql += " AND strftime('%Y-%m', t.date) = ?"
        params.append(month)

    if account_id:
        sql += " AND (t.account_id = ? OR t.to_account_id = ?)"
        params.extend([account_id, account_id])

    if category_id:
        sql += " AND t.category_id = ?"
        params.append(category_id)

    if tx_type:
        sql += " AND t.type = ?"
        params.append(tx_type)

    if query:
        sql += " AND (t.description LIKE ? OR t.tags LIKE ? OR t.notes LIKE ?)"
        like_term = f"%{query}%"
        params.extend([like_term, like_term, like_term])

    sql += " ORDER BY t.date DESC, t.id DESC LIMIT 250"

    conn = get_db_connection()
    txs = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    return jsonify(txs)


@app.route("/api/transactions", methods=["POST"])
@login_required
def api_create_transaction():
    user_id = session["user_id"]
    data = request.json or {}
    tx_date = data.get("date") or date.today().strftime("%Y-%m-%d")
    tx_type = data.get("type", "expense")
    amount = float(data.get("amount", 0.0))
    cat_id = data.get("category_id")
    acc_id = data.get("account_id")
    to_acc_id = data.get("to_account_id")
    desc = data.get("description", "").strip()
    tags = data.get("tags", "").strip()
    notes = data.get("notes", "").strip()

    if not desc or amount <= 0 or not acc_id:
        return jsonify({"error": "Description, valid amount, and source account are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, date, type, amount, category_id, account_id, to_account_id, description, tags, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, tx_date, tx_type, amount, cat_id, acc_id, to_acc_id, desc, tags, notes))
    tx_id = cursor.lastrowid
    conn.commit()
    conn.close()

    update_balances_for_transaction(tx_id, user_id=user_id, reverse=False)

    return jsonify({"status": "success", "id": tx_id}), 201


@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
@login_required
def api_delete_transaction(tx_id):
    user_id = session["user_id"]
    update_balances_for_transaction(tx_id, user_id=user_id, reverse=True)

    conn = get_db_connection()
    conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Transaction deleted"})


# ---------------------------------------------------------
# CATEGORIES API
# ---------------------------------------------------------

@app.route("/api/categories", methods=["GET"])
@login_required
def api_get_categories():
    user_id = session["user_id"]
    conn = get_db_connection()
    cats = [dict(r) for r in conn.execute("""
        SELECT * FROM categories WHERE user_id = ? ORDER BY type, name
    """, (user_id,)).fetchall()]
    conn.close()
    return jsonify(cats)


@app.route("/api/categories", methods=["POST"])
@login_required
def api_create_category():
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("name", "").strip()
    cat_type = data.get("type", "expense")
    icon = data.get("icon", "tag")
    color = data.get("color", "#64748B")

    if not name:
        return jsonify({"error": "Category name required"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categories (user_id, name, type, icon, color) VALUES (?, ?, ?, ?, ?)",
                       (user_id, name, cat_type, icon, color))
        cid = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "id": cid}), 201
    except Exception as e:
        return jsonify({"error": "Category already exists or invalid"}), 400


# ---------------------------------------------------------
# EMI CALCULATOR API (Simulations)
# ---------------------------------------------------------

@app.route("/api/calculator/emi", methods=["POST"])
def api_calculator_emi():
    """Simulates an EMI and returns the full schedule without saving to DB."""
    data = request.json or {}
    principal = float(data.get("principal", 1000000.0))
    annual_rate = float(data.get("annual_rate", 8.5))
    tenure_months = int(data.get("tenure_months", 60))

    emi = calculate_emi(principal, annual_rate, tenure_months)
    monthly_rate = (annual_rate / 100.0) / 12.0

    schedule = []
    remaining = principal
    total_interest = 0.0

    for i in range(1, tenure_months + 1):
        interest = round(remaining * monthly_rate, 2)
        total_interest += interest
        principal_comp = round(emi - interest, 2)

        if i == tenure_months or principal_comp > remaining:
            principal_comp = round(remaining, 2)
            actual_emi = round(principal_comp + interest, 2)
            remaining = 0.0
        else:
            remaining = round(remaining - principal_comp, 2)
            actual_emi = emi

        schedule.append({
            "month": i,
            "emi": actual_emi,
            "principal": principal_comp,
            "interest": interest,
            "remaining": remaining
        })

    return jsonify({
        "principal": principal,
        "annual_rate": annual_rate,
        "tenure_months": tenure_months,
        "monthly_emi": emi,
        "total_interest": round(total_interest, 2),
        "total_payable": round(principal + total_interest, 2),
        "schedule": schedule
    })


# ---------------------------------------------------------
# DATA EXPORT & SEEDING API
# ---------------------------------------------------------

@app.route("/api/seed", methods=["POST"])
@login_required
def api_seed_data():
    """Seeds realistic demo data specifically for the logged-in user."""
    try:
        user_id = session["user_id"]
        seed_database(user_id=user_id)
        return jsonify({"status": "success", "message": "Demo data loaded successfully for your account!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export", methods=["GET"])
@login_required
def api_export_json():
    user_id = session["user_id"]
    conn = get_db_connection()
    data = {
        "export_date": datetime.now().isoformat(),
        "user_id": user_id,
        "accounts": [dict(r) for r in conn.execute("SELECT * FROM accounts WHERE user_id = ?", (user_id,)).fetchall()],
        "categories": [dict(r) for r in conn.execute("SELECT * FROM categories WHERE user_id = ?", (user_id,)).fetchall()],
        "loans": [dict(r) for r in conn.execute("SELECT * FROM loans WHERE user_id = ?", (user_id,)).fetchall()],
        "transactions": [dict(r) for r in conn.execute("SELECT * FROM transactions WHERE user_id = ?", (user_id,)).fetchall()]
    }
    conn.close()

    json_str = json.dumps(data, indent=2)
    return Response(
        json_str,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=fintrack_backup_{session.get('username')}_{date.today()}.json"}
    )


@app.route("/api/export/csv", methods=["GET"])
@login_required
def api_export_csv():
    user_id = session["user_id"]
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT t.date, t.type, t.amount, c.name as category, a.name as account,
               to_a.name as to_account, t.description, t.tags, t.notes
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts to_a ON t.to_account_id = to_a.id
        WHERE t.user_id = ?
        ORDER BY t.date DESC
    """, (user_id,)).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Amount (INR)", "Category", "From Account", "To Account", "Description", "Tags", "Notes"])
    for r in rows:
        writer.writerow([r["date"], r["type"], r["amount"], r["category"] or "", r["account"] or "", r["to_account"] or "", r["description"], r["tags"], r["notes"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=transactions_{session.get('username')}_{date.today()}.csv"}
    )


# ---------------------------------------------------------
# APPLICATION ENTRYPOINT
# ---------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Personal Expense & EMI Tracker on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
