from datetime import datetime, timedelta
from fastapi import HTTPException, APIRouter, Query
from typing import Optional, List, Dict, Any
import pandas as pd

router = APIRouter(
    tags=["Конфиденцияльные файлы Физ. лиц"],
    responses={404: {"description": "Not found"}},
)

CSV_PATH = r"src\data\transactions_kz_15k_final.csv"
df = pd.read_csv(CSV_PATH, dtype={"id": int, "amount": int, "salary": int}, encoding="utf-8")

if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

# Фиксированный порядок категорий (как в датасете)
CATEGORIES = [
    "АЗС", "Доставка еды", "Играем дома", "Кофе и рестораны", "Кино",
    "Отели", "Продукты питания", "Путешествия", "Развлечения",
    "Отдых дома", "Такси"
]

PRODUCTS = {
    "BNPL": {
        "name": "BNPL (рассрочка)",
        "type": "финансирование",
        "markup_from": 300,
        "min_sum": 10_000, "max_sum": 300_000,
        "min_term_m": 1, "max_term_m": 12,
        "min_age": 18, "max_age": 63
    },
    "ISLAM_FIN": {
        "name": "Исламское финансирование",
        "type": "финансирование",
        "markup_from": 6_000,
        "min_sum": 100_000, "max_sum": 5_000_000,
        "min_term_m": 3, "max_term_m": 60,
        "min_age": 18, "max_age": 60
    },
    "ISLAM_MORT": {
        "name": "Исламская ипотека",
        "type": "финансирование",
        "markup_from": 200_000,
        "min_sum": 3_000_000, "max_sum": 75_000_000,
        "min_term_m": 12, "max_term_m": 240,
        "min_age": 25, "max_age": 60
    },
    "SAVINGS": {
        "name": "Копилка",
        "type": "инвестиционный",
        "expected_yield": "до 18%",
        "min_sum": 1_000, "max_sum": 20_000_000,
        "min_term_m": 1, "max_term_m": 12
    },
    "WAKALA": {
        "name": "Вакала",
        "type": "инвестиционный",
        "expected_yield": "до 20%",
        "min_sum": 50_000, "max_sum": None,
        "min_term_m": 3, "max_term_m": 36
    }
}

WEEKDAY_RU = {
    0: "Понедельник", 1: "Вторник", 2: "Среда",
    3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"
}


@router.get("/users/{user_id}/transactions")
def get_user_transactions(
    user_id: int,
    start_date: Optional[str] = Query(None, description="Начальная дата, формат YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Конечная дата, формат YYYY-MM-DD")
):
    """
    Возвращает все транзакции по id пользователя.
    Пример: GET /users/1/transactions
    """
    user_data = df[df["id"] == user_id]

    if user_data.empty:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Фильтрация по датам
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            user_data = user_data[user_data["date"] >= start_date]
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный формат start_date. Используй YYYY-MM-DD")

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            user_data = user_data[user_data["date"] <= end_date]
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный формат end_date. Используй YYYY-MM-DD")

    # Если после фильтрации ничего не осталось
    if user_data.empty:
        raise HTTPException(status_code=404, detail="Нет транзакций за указанный период")

    # Можно вернуть в виде списка словарей
    transactions = user_data.to_dict(orient="records")

    # В ответе добавим краткую сводку
    total_spent = int(user_data["amount"].sum())
    balance_left = int(user_data["balance_left"].iloc[0])
    salary = int(user_data["salary"].iloc[0])

    return {
        "user_id": user_id,
        "salary": salary,
        "balance_left": balance_left,
        "total_spent": total_spent,
        "transactions_count": len(transactions),
        "transactions": transactions,
    }

@router.get("/users/{user_id}/spending/3m")
def get_spending_summary_3m(
    user_id: int,
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD; по умолчанию — сегодня")
) -> Dict[str, Any]:
    user_data = df[df["id"] == user_id].copy()
    if user_data.empty:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # ЖЁСТКО приводим тип в рамках запроса (на случай hot-reload/старых данных)
    user_data["date"] = pd.to_datetime(user_data["date"], errors="coerce")

    # Период
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    start_dt = end_dt - timedelta(days=90)

    # Сравниваем именно даты (без времени), чтобы избежать TZ-наследования
    d0, d1 = start_dt.date(), end_dt.date()
    mask = (user_data["date"].dt.date >= d0) & (user_data["date"].dt.date <= d1)
    period_data = user_data.loc[mask].dropna(subset=["date"])

    if period_data.empty:
        raise HTTPException(status_code=404, detail="Нет транзакций за последние 3 месяца")

    grouped = (
        period_data.groupby("category")["amount"]
        .sum()
        .reindex(CATEGORIES, fill_value=0)
        .astype(int)
    )

    total_spent = int(grouped.sum())
    salary = int(period_data["salary"].iloc[0])
    salary_3m = salary * 3
    balance_left = int(salary_3m - total_spent)

    categories_summary: List[Dict[str, Any]] = [
        {"category": cat, "amount": int(grouped.loc[cat]),
         "share": round(int(grouped.loc[cat]) / total_spent, 4) if total_spent else 0.0}
        for cat in CATEGORIES
    ]

    return {
        "user_id": user_id,
        "period": {
            "start_date": d0.isoformat(),
            "end_date": d1.isoformat(),
            "days": (d1 - d0).days
        },
        "currency": "KZT",
        "salary_monthly": salary,
        "salary_3m": salary_3m,
        "total_spent_3m": total_spent,
        "balance_left_3m": balance_left,
        "categories": categories_summary
    }


def monthify_sum_3m(x: float) -> float:
    return x / 3.0

def financial_type(spent_ratio: float) -> str:
    if spent_ratio <= 0.70: return "Экономный"
    if spent_ratio <= 0.85: return "Сбалансированный"
    if spent_ratio <= 1.00: return "Тратит всё"
    return "В минусе"

def pick_products(salary_m: int,
                  free_cash_m: float,
                  spent_ratio: float,
                  period_data: pd.DataFrame,
                  cats_share: Dict[str, float]) -> List[Dict[str, Any]]:
    """Жадная логика подбора продуктов на основе CSV."""
    recs = []

    # Инвестиции — если есть свободный остаток
    if free_cash_m >= PRODUCTS["SAVINGS"]["min_sum"]:
        recs.append({
            "product": PRODUCTS["SAVINGS"]["name"],
            "reason": f"Ежемесячно свободно ~{int(free_cash_m):,} ₸ — можно копить (доходность {PRODUCTS['SAVINGS']['expected_yield']}).".replace(",", " "),
            "suggested_monthly": int(min(free_cash_m, 200_000))
        })
    if free_cash_m >= PRODUCTS["WAKALA"]["min_sum"]:
        recs.append({
            "product": PRODUCTS["WAKALA"]["name"],
            "reason": f"Достаточный остаток для инвестиций (доходность {PRODUCTS['WAKALA']['expected_yield']}).",
            "suggested_monthly": int(min(free_cash_m, 300_000))
        })

    # Финансирование — при высоком коэффициенте расходов
    max_tx = int(period_data["amount"].max()) if not period_data.empty else 0
    # BNPL — для крупных покупок до 300k, если бюджет напряжён (>=0.9)
    if spent_ratio >= 0.90 and PRODUCTS["BNPL"]["min_sum"] <= max_tx <= PRODUCTS["BNPL"]["max_sum"]:
        recs.append({
            "product": PRODUCTS["BNPL"]["name"],
            "reason": f"Крупные покупки до {PRODUCTS['BNPL']['max_sum']:,} ₸ при высоких расходах — удобно распределить платежи.".replace(",", " "),
            "limits": {"min": PRODUCTS["BNPL"]["min_sum"], "max": PRODUCTS["BNPL"]["max_sum"], "term_m": [PRODUCTS["BNPL"]["min_term_m"], PRODUCTS["BNPL"]["max_term_m"]]}
        })

    # Исламское финансирование — когда нужен буфер > 100k и расходы высокие
    if spent_ratio >= 0.90 and salary_m >= 400_000:
        recs.append({
            "product": PRODUCTS["ISLAM_FIN"]["name"],
            "reason": "Высокая доля расходов — можно покрывать покупки/потребности халяль-финансированием до 5 млн ₸.",
            "limits": {"min": PRODUCTS["ISLAM_FIN"]["min_sum"], "max": PRODUCTS["ISLAM_FIN"]["max_sum"], "term_m": [PRODUCTS["ISLAM_FIN"]["min_term_m"], PRODUCTS["ISLAM_FIN"]["max_term_m"]]},
            "note": "Проверка возраста 18–60 лет потребуется при оформлении."
        })

    # Ипотека — только по профилю дохода, без возраста (его нет в CSV)
    if salary_m >= 1_000_000 and spent_ratio <= 0.85:
        recs.append({
            "product": PRODUCTS["ISLAM_MORT"]["name"],
            "reason": "Стабильный доход и контролируемые расходы — профиль подходит для ипотеки.",
            "limits": {"min": PRODUCTS["ISLAM_MORT"]["min_sum"], "max": PRODUCTS["ISLAM_MORT"]["max_sum"], "term_m": [PRODUCTS["ISLAM_MORT"]["min_term_m"], PRODUCTS["ISLAM_MORT"]["max_term_m"]]},
            "note": "Возрастная проверка 25–60 лет при подаче заявки."
        })

    # Уточняющие персональные советы по поведению (не продукт, но полезно)
    dining_ent = cats_share.get("Кофе и рестораны", 0) + cats_share.get("Развлечения", 0)
    if dining_ent >= 0.25:
        recs.append({
            "product": "Совет по бюджету",
            "reason": f"Большая доля кафе+развлечения ({int(dining_ent*100)}%). Сократи на 10–15% и направляй разницу в Копилку.",
            "suggested_monthly": int(0.1 * salary_m)
        })

    return recs

def format_kzt(x: int) -> str:
    # 1_234_567 -> "1 234 567 ₸"
    return f"{int(x):,} ₸".replace(",", " ")

def make_advice(
    salary_m: int,
    spent_ratio: float,
    cats_share: Dict[str, float],
    grouped_amounts: Dict[str, int],
    free_cash_m: float
) -> str:
    # Находим «большую» категорию для конкретики
    if grouped_amounts:
        top_cat = max(grouped_amounts.items(), key=lambda kv: kv[1])[0]
        top_cat_amt = grouped_amounts[top_cat]
    else:
        top_cat, top_cat_amt = "Продукты питания", 0

    dining_ent_share = cats_share.get("Кофе и рестораны", 0) + cats_share.get("Развлечения", 0)
    cut10_top = int(top_cat_amt * 0.10)
    suggest_save = int(min(max(0.05 * salary_m, 10_000), 200_000))
    suggest_invest = int(min(max(free_cash_m * 0.7, 50_000), 300_000))

    if spent_ratio >= 0.95:
        return (
            f"Бюджет перенапряжён: расходы ≈ {round(spent_ratio*100)}%. "
            f"Сократи «{top_cat}» на 10% (~{format_kzt(cut10_top)}) и используй BNPL для крупных покупок до 300 000 ₸. "
            f"Если нужен буфер — рассмотрите Исламское финансирование до 5 000 000 ₸."
        )
    elif 0.85 <= spent_ratio < 0.95:
        extra = ""
        if dining_ent_share >= 0.25:
            extra = " Сократи кафе+развлечения на 10–15% и направляй разницу в Копилку."
        return (
            f"На грани: расходы ≈ {round(spent_ratio*100)}%. "
            f"Начни откладывать {format_kzt(suggest_save)} в «Копилку».{extra}"
        )
    elif 0.70 <= spent_ratio < 0.85:
        return (
            f"Сбалансированный профиль: расходы ≈ {round(spent_ratio*100)}%. "
            f"Рекомендуем инвестировать {format_kzt(suggest_invest)} в «Вакала» (до 20%) "
            f"и параллельно копить {format_kzt(suggest_save)} в «Копилку»."
        )
    else:
        return (
            f"Отличный запас: расходы ≈ {round(spent_ratio*100)}%. "
            f"Ускорь достижение целей — направляй {format_kzt(suggest_invest)} в «Вакала» и "
            f"{format_kzt(suggest_save)} в «Копилку». Создай цель и привяжи автосписание."
        )

@router.get("/analytics/{user_id}")
def analytics_user(
    user_id: int,
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD; по умолчанию — сегодня")
) -> Dict[str, Any]:
    user_df = df[df["id"] == user_id].copy()
    if user_df.empty:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Период 3 месяца до end_date
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    start_dt = end_dt - timedelta(days=90)
    mask = (user_df["date"].dt.date >= start_dt.date()) & (user_df["date"].dt.date <= end_dt.date())
    period = user_df.loc[mask]
    if period.empty:
        raise HTTPException(status_code=404, detail="Нет транзакций за последние 3 месяца")

    # Базовые метрики
    salary_m = int(period["salary"].iloc[0])  # зарплата в месяц
    spent_3m = int(period["amount"].sum())
    spent_m = monthify_sum_3m(spent_3m)
    salary_3m = salary_m * 3
    spent_ratio = float(spent_3m / salary_3m) if salary_3m > 0 else 0.0
    free_cash_3m = salary_3m - spent_3m
    free_cash_m = max(0.0, monthify_sum_3m(free_cash_3m))

    # Категории
    grouped = (period.groupby("category")["amount"].sum()
                      .reindex(CATEGORIES, fill_value=0)
                      .astype(int))
    total = int(grouped.sum()) or 1
    cats = [{"category": c, "amount": int(grouped[c]), "share": round(int(grouped[c]) / total, 4)} for c in CATEGORIES]
    cats_share = {c["category"]: c["share"] for c in cats}
    grouped_amounts = {c: int(grouped[c]) for c in CATEGORIES}
    top3 = sorted(cats, key=lambda x: x["amount"], reverse=True)[:3]

    # Тип пользователя и рекомендации/продукты
    ftype = financial_type(spent_ratio)
    products = pick_products(salary_m, free_cash_m, spent_ratio, period, cats_share)

    # Доп. быстрые инсайты
    avg_ticket = int(period["amount"].mean())
    tx_count = int(period.shape[0])
    days = (end_dt.date() - start_dt.date()).days
    tx_per_day = round(tx_count / max(1, days), 2)

    # --- Интересные факты (4 шт.) ---
    insights: List[str] = []
    dining = period[period["category"] == "Кофе и рестораны"]["amount"]
    if not dining.empty:
        insights.append(f"Средний чек в «Кофе и рестораны»: {int(dining.mean()):,} ₸".replace(",", " "))
    else:
        insights.append("В категории «Кофе и рестораны» не было покупок за период.")

    by_day = period.copy()
    by_day["weekday"] = by_day["date"].dt.weekday
    wd_avg = by_day.groupby("weekday")["amount"].mean()
    if not wd_avg.empty:
        wd = int(wd_avg.idxmax())
        insights.append(f"Самый затратный день недели: {WEEKDAY_RU[wd]} (средний чек {int(wd_avg.max()):,} ₸)".replace(",", " "))

    top_cat = max(cats, key=lambda x: x["amount"]) if cats else None
    if top_cat:
        insights.append(f"Топ-категория: {top_cat['category']} — {round(top_cat['share'] * 100, 1)}% всех трат.")

    idx = period["amount"].idxmax()
    if pd.notna(idx):
        row = period.loc[idx]
        insights.append(f"Макс. транзакция: {int(row['amount']):,} ₸ — {row['category']} — {row['date'].date()}".replace(",", " "))

    # --- НОВОЕ: персональный совет ---
    advice = make_advice(salary_m, spent_ratio, cats_share, grouped_amounts, free_cash_m)

    return {
        "user_id": user_id,
        "period": {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "days": days
        },
        "profile": {
            "salary_monthly": salary_m,
            "spent_3m": spent_3m,
            "spent_monthly": int(spent_m),
            "spent_ratio": round(spent_ratio, 3),
            "balance_left_3m": int(free_cash_3m),
            "balance_left_monthly": int(free_cash_m),
            "financial_type": ftype
        },
        "activity": {
            "transactions_count": tx_count,
            "avg_ticket": avg_ticket,
            "tx_per_day": tx_per_day
        },
        "categories": {
            "breakdown": cats,
            "top3": top3
        },
        "recommendations": products,
        "insights": insights,
        "advice": advice
    }
