"""
seed_data.py - Populates realistic personal finance, car loan, and credit card data for a user.
"""

from datetime import datetime, date
from database import init_db, get_db_connection, seed_user_categories
from models import calculate_emi, generate_amortization_schedule, pay_loan_emi, add_months


def seed_database(user_id: int = 1):
    """Seeds comprehensive realistic data for the specified user."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure user exists
    user = cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        # Fallback to first user
        first_user = cursor.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
        if first_user:
            user_id = first_user["id"]
        else:
            conn.close()
            return

    # Clear existing data for this user
    # Delete transactions for this user
    cursor.execute("DELETE FROM transactions WHERE user_id = ?;", (user_id,))
    # Delete loans and their emi_schedules for this user
    loans = cursor.execute("SELECT id FROM loans WHERE user_id = ?", (user_id,)).fetchall()
    for l in loans:
        cursor.execute("DELETE FROM emi_schedule WHERE loan_id = ?", (l["id"],))
    cursor.execute("DELETE FROM loans WHERE user_id = ?;", (user_id,))
    cursor.execute("DELETE FROM accounts WHERE user_id = ?;", (user_id,))
    conn.commit()

    # Ensure user has categories
    seed_user_categories(user_id, conn)

    # 1. Insert Accounts
    cursor.execute("""
        INSERT INTO accounts (user_id, name, type, account_number_last4, balance, credit_limit, color, icon)
        VALUES 
        (?, 'HDFC Salary & Savings', 'bank', '4821', 142500.0, 0, '#0284C7', 'building-2'),
        (?, 'SBI Emergency Reserve', 'bank', '9104', 85000.0, 0, '#059669', 'landmark'),
        (?, 'Cash Wallet', 'cash', '', 4500.0, 0, '#10B981', 'wallet');
    """, (user_id, user_id, user_id))
    hdfc_bank_id = cursor.execute("SELECT id FROM accounts WHERE user_id = ? AND name = 'HDFC Salary & Savings'", (user_id,)).fetchone()[0]
    sbi_bank_id = cursor.execute("SELECT id FROM accounts WHERE user_id = ? AND name = 'SBI Emergency Reserve'", (user_id,)).fetchone()[0]

    # Credit Cards
    cursor.execute("""
        INSERT INTO accounts (user_id, name, type, account_number_last4, balance, credit_limit, billing_cycle_day, payment_due_day, color, icon)
        VALUES 
        (?, 'HDFC Regalia Gold CC', 'credit_card', '7712', 28450.0, 350000.0, 1, 20, '#6366F1', 'credit-card'),
        (?, 'ICICI Amazon Pay CC', 'credit_card', '3450', 14200.0, 200000.0, 12, 2, '#EA580C', 'credit-card');
    """, (user_id, user_id))
    hdfc_cc_id = cursor.execute("SELECT id FROM accounts WHERE user_id = ? AND name = 'HDFC Regalia Gold CC'", (user_id,)).fetchone()[0]
    icici_cc_id = cursor.execute("SELECT id FROM accounts WHERE user_id = ? AND name = 'ICICI Amazon Pay CC'", (user_id,)).fetchone()[0]
    conn.commit()

    # 2. Add Loans
    # 2.1 Personal Car Loan
    car_principal = 1000000.0  # 10 Lakhs
    car_rate = 8.75  # 8.75%
    car_tenure = 60  # 60 months (5 years)
    car_emi = calculate_emi(car_principal, car_rate, car_tenure)
    
    today = date.today()
    car_start_date = add_months(today, -6).strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO loans (
            user_id, name, type, lender_bank, vehicle_details, principal_amount,
            interest_rate, tenure_months, start_date, emi_amount, emi_day_of_month,
            linked_account_id, status, notes
        ) VALUES (
            ?, 'Car Loan - Hyundai Creta SX', 'car_loan', 'HDFC Bank',
            'Hyundai Creta SX(O) 1.5 Diesel Auto - MH 12 AB 5678',
            ?, ?, ?, ?, ?, 5, ?, 'active', '5-year auto loan on reducing balance interest rate'
        )
    """, (user_id, car_principal, car_rate, car_tenure, car_start_date, car_emi, hdfc_bank_id))
    car_loan_id = cursor.lastrowid
    conn.commit()

    generate_amortization_schedule(car_loan_id, car_principal, car_rate, car_tenure, car_start_date, 5, car_emi)

    # Mark past 5 installments as paid
    for inst_no in range(1, 6):
        pay_loan_emi(car_loan_id, user_id=user_id, installment_no=inst_no, bank_account_id=hdfc_bank_id)

    # 2.2 Credit Card EMI (e.g. MacBook purchase converted into CC EMI)
    cc_emi_principal = 120000.0
    cc_emi_rate = 14.0
    cc_emi_tenure = 6
    cc_emi_amount = calculate_emi(cc_emi_principal, cc_emi_rate, cc_emi_tenure)
    cc_emi_start = add_months(today, -2).strftime("%Y-%m-%d")

    cursor.execute("""
        INSERT INTO loans (
            user_id, name, type, lender_bank, principal_amount,
            interest_rate, tenure_months, start_date, emi_amount, emi_day_of_month,
            linked_account_id, status, notes
        ) VALUES (
            ?, 'MacBook Pro M3 CC EMI', 'credit_card_emi', 'HDFC Credit Card',
            ?, ?, ?, ?, ?, 15, ?, 'active', '6-month no-cost converted EMI on Regalia Gold card'
        )
    """, (user_id, cc_emi_principal, cc_emi_rate, cc_emi_tenure, cc_emi_start, cc_emi_amount, hdfc_bank_id))
    cc_loan_id = cursor.lastrowid
    conn.commit()

    generate_amortization_schedule(cc_loan_id, cc_emi_principal, cc_emi_rate, cc_emi_tenure, cc_emi_start, 15, cc_emi_amount)
    
    pay_loan_emi(cc_loan_id, user_id=user_id, installment_no=1, bank_account_id=hdfc_bank_id)
    pay_loan_emi(cc_loan_id, user_id=user_id, installment_no=2, bank_account_id=hdfc_bank_id)

    # 3. Add Sample Expenses & Income for current and recent months
    categories = {row["name"]: row["id"] for row in cursor.execute("SELECT name, id FROM categories WHERE user_id = ?", (user_id,)).fetchall()}

    def get_cat(name):
        return categories.get(name)

    cur_m = today.strftime("%Y-%m")
    prev_m = add_months(today, -1).strftime("%Y-%m")

    sample_txs = [
        # Income
        (user_id, f"{cur_m}-01", "income", 125000.0, get_cat("Salary"), hdfc_bank_id, None, "Monthly Corporate Salary Credit", "Salary"),
        (user_id, f"{cur_m}-03", "income", 15000.0, get_cat("Freelance / Consulting"), sbi_bank_id, None, "Freelance UI Consulting Project", "Income"),
        (user_id, f"{prev_m}-01", "income", 125000.0, get_cat("Salary"), hdfc_bank_id, None, "Monthly Corporate Salary Credit", "Salary"),

        # Credit Card Expenses (HDFC Regalia)
        (user_id, f"{cur_m}-02", "expense", 4200.0, get_cat("Fuel & Gas"), hdfc_cc_id, None, "Shell Petrol Pump - Full Tank Car Fuel", "Fuel,Car"),
        (user_id, f"{cur_m}-04", "expense", 6850.0, get_cat("Food & Dining Out"), hdfc_cc_id, None, "Weekend Dinner at Barbeque Nation", "Dining"),
        (user_id, f"{cur_m}-05", "expense", 8900.0, get_cat("Shopping & Electronics"), hdfc_cc_id, None, "Sony WH-1000XM5 Accessories", "Gadgets"),
        (user_id, f"{cur_m}-06", "expense", 8500.0, get_cat("Travel & Transportation"), hdfc_cc_id, None, "MakeMyTrip Flight Booking", "Flight"),

        # Credit Card Expenses (ICICI Amazon Pay)
        (user_id, f"{cur_m}-03", "expense", 5400.0, get_cat("Groceries & Supermarket"), icici_cc_id, None, "Amazon Fresh & Blinkit Groceries", "Grocery"),
        (user_id, f"{cur_m}-04", "expense", 3200.0, get_cat("Entertainment & Subscriptions"), icici_cc_id, None, "Netflix, Prime & Spotify Annual Subscriptions", "Sub"),
        (user_id, f"{cur_m}-06", "expense", 5600.0, get_cat("Healthcare & Medical"), icici_cc_id, None, "Apollo Pharmacy Health Checkup & Meds", "Medical"),

        # Bank Account Expenses (HDFC Bank)
        (user_id, f"{cur_m}-02", "expense", 28000.0, get_cat("Housing & Rent"), hdfc_bank_id, None, "Apartment Monthly Rent via NEFT", "Rent"),
        (user_id, f"{cur_m}-03", "expense", 3450.0, get_cat("Bills & Utilities"), hdfc_bank_id, None, "Electricity & Tata Play Fiber Bill", "Bills"),
        (user_id, f"{cur_m}-05", "expense", 5200.0, get_cat("Car Maintenance & Service"), hdfc_bank_id, None, "Hyundai Authorized Service Center Wash & Oil", "Car,Service"),

        # Past Month CC Bill Payments from Bank to CC
        (user_id, f"{prev_m}-18", "cc_bill_payment", 32500.0, get_cat("Credit Card Bill Payment"), hdfc_bank_id, hdfc_cc_id, "Paid HDFC Regalia CC Bill in Full", "BillPay"),
        (user_id, f"{prev_m}-28", "cc_bill_payment", 18200.0, get_cat("Credit Card Bill Payment"), sbi_bank_id, icici_cc_id, "Paid ICICI Amazon Pay CC Bill", "BillPay"),
    ]

    for tx in sample_txs:
        cursor.execute("""
            INSERT INTO transactions (user_id, date, type, amount, category_id, account_id, to_account_id, description, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tx)

    conn.commit()
    conn.close()
    print(f"Database successfully seeded for user_id={user_id}!")


if __name__ == "__main__":
    seed_database()
