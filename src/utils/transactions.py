import pandas as pd


def get_user_transactions(user_id: int):
    CSV_PATH = r"src\data\transactions_kz_15k_final.csv"
    df = pd.read_csv(CSV_PATH, dtype={"id": int, "amount": int, "salary": int}, encoding="utf-8")

    user_data = df[df["id"] == user_id]
    if user_data.empty:
        return None

    transactions = user_data.to_dict(orient="records")

    return transactions
