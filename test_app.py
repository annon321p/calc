"""
test_app.py - Automated verification tests for Personal Expense & EMI Tracker
Including User Authentication, Session Management, and Private Data Isolation.
"""

import unittest
import json
from datetime import date
from database import init_db, get_db_connection
from models import (
    calculate_emi, generate_amortization_schedule,
    pay_loan_emi, pay_credit_card_bill, get_dashboard_summary,
    register_user, authenticate_user
)
from app import app
from seed_data import seed_database


class TestExpenseEmiTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE username = 'sourav_test'")
        conn.commit()
        conn.close()
        seed_database(user_id=1)
        cls.client = app.test_client()

    def test_01_emi_calculation(self):
        """Verify standard reducing balance EMI calculation formula."""
        emi = calculate_emi(1000000.0, 8.75, 60)
        self.assertAlmostEqual(emi, 20637.23, delta=1.0)

        zero_emi = calculate_emi(120000.0, 0.0, 12)
        self.assertEqual(zero_emi, 10000.0)

    def test_02_amortization_schedule(self):
        """Verify amortization schedule ends with 0.0 remaining principal."""
        conn = get_db_connection()
        car_loan = conn.execute("SELECT * FROM loans WHERE type = 'car_loan' LIMIT 1").fetchone()
        self.assertIsNotNone(car_loan)

        last_inst = conn.execute("""
            SELECT * FROM emi_schedule WHERE loan_id = ? ORDER BY installment_no DESC LIMIT 1
        """, (car_loan["id"],)).fetchone()
        self.assertIsNotNone(last_inst)
        self.assertEqual(last_inst["installment_no"], car_loan["tenure_months"])
        self.assertEqual(last_inst["remaining_principal"], 0.0)
        conn.close()

    def test_03_user_auth_flow(self):
        """Verify user registration, login, profile check, and duplicate rejection."""
        # 1. Register new user
        reg_res = self.client.post("/api/auth/register", json={
            "username": "sourav_test",
            "password": "mypassword123",
            "full_name": "Sourav Test",
            "email": "sourav@test.com"
        })
        self.assertEqual(reg_res.status_code, 201)
        data = reg_res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"]["username"], "sourav_test")

        # 2. Check /api/auth/me
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.get_json()["authenticated"])
        self.assertEqual(me_res.get_json()["user"]["username"], "sourav_test")

        # 3. Duplicate username should be rejected
        dup_res = self.client.post("/api/auth/register", json={
            "username": "sourav_test",
            "password": "anotherpassword",
            "full_name": "Sourav Dup"
        })
        self.assertEqual(dup_res.status_code, 400)

        # 4. Logout
        self.client.post("/api/auth/logout")
        me_logged_out = self.client.get("/api/auth/me").get_json()
        self.assertFalse(me_logged_out["authenticated"])

        # 5. Invalid credentials should fail
        bad_login = self.client.post("/api/auth/login", json={
            "username": "sourav_test",
            "password": "wrongpassword"
        })
        self.assertEqual(bad_login.status_code, 401)

        # 6. Valid login should succeed
        good_login = self.client.post("/api/auth/login", json={
            "username": "sourav_test",
            "password": "mypassword123"
        })
        self.assertEqual(good_login.status_code, 200)

    def test_04_private_data_isolation(self):
        """Verify complete data isolation between different users."""
        # Log in as user A (sourav_test)
        self.client.post("/api/auth/login", json={"username": "sourav_test", "password": "mypassword123"})
        
        # Create an account for User A
        acc_res = self.client.post("/api/accounts", json={
            "name": "Sourav Private Swiss Account",
            "type": "bank",
            "balance": 500000.0,
            "account_number_last4": "9999"
        })
        self.assertEqual(acc_res.status_code, 201)

        # Now log in as user B (admin / admin123)
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        
        # User B should NOT see User A's private account
        admin_accounts = self.client.get("/api/accounts").get_json()
        account_names = [a["name"] for a in admin_accounts]
        self.assertNotIn("Sourav Private Swiss Account", account_names)

        # User A logs back in and sees their account
        self.client.post("/api/auth/login", json={"username": "sourav_test", "password": "mypassword123"})
        user_accounts = self.client.get("/api/accounts").get_json()
        user_acc_names = [a["name"] for a in user_accounts]
        self.assertIn("Sourav Private Swiss Account", user_acc_names)

    def test_05_transaction_balance_impacts(self):
        """Verify bank debits and credit card spends impact balances correctly."""
        # Log in as admin (who has seeded accounts)
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        accounts = self.client.get("/api/accounts").get_json()
        bank = next(a for a in accounts if a["type"] == "bank")
        cc = next(a for a in accounts if a["type"] == "credit_card")
        bank_id = bank["id"]
        cc_id = cc["id"]
        init_bank_bal = bank["balance"]
        init_cc_bal = cc["balance"]

        # Log expense from bank
        res = self.client.post("/api/transactions", json={
            "type": "expense",
            "amount": 2500.0,
            "account_id": bank_id,
            "description": "Test Bank Debit"
        })
        self.assertEqual(res.status_code, 201)

        updated_bank = next(a for a in self.client.get("/api/accounts").get_json() if a["id"] == bank_id)
        self.assertEqual(updated_bank["balance"], init_bank_bal - 2500.0)

        # Log expense from CC
        res_cc = self.client.post("/api/transactions", json={
            "type": "expense",
            "amount": 1800.0,
            "account_id": cc_id,
            "description": "Test CC Spend"
        })
        self.assertEqual(res_cc.status_code, 201)

        updated_cc = next(a for a in self.client.get("/api/accounts").get_json() if a["id"] == cc_id)
        self.assertEqual(updated_cc["balance"], init_cc_bal + 1800.0)

    def test_06_pay_credit_card_bill(self):
        """Verify paying CC bill reduces bank balance and resets/reduces CC outstanding."""
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        
        accounts = self.client.get("/api/accounts").get_json()
        bank = next(a for a in accounts if a["type"] == "bank")
        cc = next(a for a in accounts if a["type"] == "credit_card")
        bank_id = bank["id"]
        cc_id = cc["id"]
        pre_bank_bal = bank["balance"]
        pre_cc_bal = cc["balance"]

        pay_amount = 5000.0
        res = self.client.post(f"/api/accounts/{cc_id}/pay-bill", json={
            "bank_account_id": bank_id,
            "amount": pay_amount,
            "notes": "Test payment"
        })
        self.assertEqual(res.status_code, 200)

        post_accounts = self.client.get("/api/accounts").get_json()
        post_bank = next(a for a in post_accounts if a["id"] == bank_id)["balance"]
        post_cc = next(a for a in post_accounts if a["id"] == cc_id)["balance"]

        self.assertEqual(post_bank, pre_bank_bal - pay_amount)
        self.assertEqual(post_cc, max(0.0, pre_cc_bal - pay_amount))

    def test_07_pay_loan_emi(self):
        """Verify paying loan EMI marks installment paid and debits bank account."""
        self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        loans = self.client.get("/api/loans").get_json()
        car_loan = next(l for l in loans if l["type"] == "car_loan")
        accounts = self.client.get("/api/accounts").get_json()
        bank = next(a for a in accounts if a["type"] == "bank")

        loan_id = car_loan["id"]
        bank_id = bank["id"]
        pre_bank_bal = bank["balance"]
        next_emi = car_loan["next_emi"]
        self.assertIsNotNone(next_emi)

        res = self.client.post(f"/api/loans/{loan_id}/pay-emi", json={
            "emi_schedule_id": next_emi["id"],
            "bank_account_id": bank_id
        })
        self.assertEqual(res.status_code, 200)

        post_bank = next(a for a in self.client.get("/api/accounts").get_json() if a["id"] == bank_id)["balance"]
        self.assertEqual(post_bank, pre_bank_bal - next_emi["emi_amount"])

    def test_08_unauthenticated_access_blocked(self):
        """Verify unauthenticated requests return 401 Unauthorized."""
        self.client.post("/api/auth/logout")

        endpoints = [
            "/api/dashboard",
            "/api/accounts",
            "/api/loans",
            "/api/transactions",
            "/api/categories"
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 401)


if __name__ == "__main__":
    unittest.main()
