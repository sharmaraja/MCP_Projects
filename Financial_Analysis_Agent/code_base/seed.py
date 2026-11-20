
import random
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "finance.db"

SAMPLE_MERCHANTS = [
    ("Swiggy", "Food & Dining", "UPI", "DEBIT", 250, 850),
    ("Zomato", "Food & Dining", "UPI", "DEBIT", 220, 900),
    ("Blue Tokai Coffee", "Food & Dining", "UPI", "DEBIT", 180, 450),
    ("Uber India", "Transport", "UPI", "DEBIT", 140, 620),
    ("IRCTC", "Transport", "NetBanking", "DEBIT", 450, 2400),
    ("Blinkit", "Groceries", "UPI", "DEBIT", 300, 1600),
    ("BigBasket", "Groceries", "Credit Card", "DEBIT", 800, 3200),
    ("Airtel Fiber", "Utilities & Subscriptions", "UPI AutoPay", "DEBIT", 999, 999),
    ("Spotify India", "Utilities & Subscriptions", "UPI AutoPay", "DEBIT", 119, 119),
    ("Netflix India", "Utilities & Subscriptions", "Credit Card", "DEBIT", 649, 649),
    ("Amazon Pay", "Shopping", "Credit Card", "DEBIT", 500, 4500),
    ("Apollo Pharmacy", "Healthcare", "UPI", "DEBIT", 200, 1500),
]

def init_and_seed_db(csv_path: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_date TEXT NOT NULL,
            merchant TEXT NOT NULL,
            category TEXT NOT NULL,
            payment_mode TEXT NOT NULL,
            txn_type TEXT CHECK(txn_type IN ('DEBIT', 'CREDIT')) NOT NULL,
            amount_inr REAL NOT NULL,
            notes TEXT
        )
    """)

    cursor.execute("DELETE FROM transactions")

    csv_file = Path(csv_path) if csv_path else None
    if csv_file is not None and not csv_file.is_absolute():
        csv_file = PROJECT_ROOT / csv_file

    if csv_file is not None and csv_file.exists():
        df = pd.read_csv(csv_file)
        df.to_sql("transactions", conn, if_exists="replace", index=False)
        print(f"Imported {len(df)} rows from {csv_file} into {DB_PATH}.")
    else:
        random.seed(42)
        rows = []

        # Add monthly salary credits + recurring subscriptions for Sep, Oct, Nov 2026
        for month_offset in range(3):
            month_start = datetime(2026, 9 + month_offset, 1)
            month_str = month_start.strftime("%Y-%m")
            rows.append((f"{month_str}-01", "Employer Payroll", "Salary", "NEFT", "CREDIT", 115000.0, "Monthly Salary"))
            rows.append((f"{month_str}-05", "House Rent Landlord", "Housing & Rent", "UPI", "DEBIT", 28000.0, "Monthly Flat Rent"))
            rows.append((f"{month_str}-07", "Airtel Fiber", "Utilities & Subscriptions", "UPI AutoPay", "DEBIT", 999.0, "Broadband"))
            rows.append((f"{month_str}-10", "Netflix India", "Utilities & Subscriptions", "Credit Card", "DEBIT", 649.0, "Subscription"))
            rows.append((f"{month_str}-12", "Spotify India", "Utilities & Subscriptions", "UPI AutoPay", "DEBIT", 119.0, "Subscription"))

            # Generate 40 random daily expenses per month
            for _ in range(40):
                merchant, category, mode, t_type, low, high = random.choice(SAMPLE_MERCHANTS)
                day = random.randint(1, 28)
                amount = round(random.uniform(low, high), 2)
                rows.append((f"{month_str}-{day:02d}", merchant, category, mode, t_type, amount, f"{mode} payment"))

        cursor.executemany("""
            INSERT INTO transactions (txn_date, merchant, category, payment_mode, txn_type, amount_inr, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, rows)
        print(f"Seeded {len(rows)} Indian UPI/Bank transactions into '{DB_PATH}'.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_and_seed_db()