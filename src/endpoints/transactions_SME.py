from datetime import datetime, timedelta
from fastapi import HTTPException, APIRouter, Query
from typing import Optional, List, Dict, Any
import pandas as pd

router = APIRouter(
    tags=["Конфиденцияльные файлы Юр. лиц"],
    prefix="/SME",
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

# ВМЕСТО старого PRODUCTS — вставь это
PRODUCTS = {
    "BIZ_OVERDRAFT": {  # Бизнес карта (овердрафт)
        "name": "Бизнес карта — исламский кредитный лимит (овердрафт)",
        "type": "овердрафт",
        "markup_from": 3_000,
        "min_sum": 100_000, "max_sum": 10_000_000,
        "min_term_d": None, "max_term_d": 30,
        "min_age": 21, "max_age": 63
    },
    "BIZ_ISLAM_UNSEC": {  # Исламское финансирование (беззалоговое)
        "name": "Исламское финансирование — беззалоговое",
        "type": "финансирование",
        "markup_from": 12_000,
        "min_sum": 100_000, "max_sum": 10_000_000,
        "min_term_m": 3, "max_term_m": 60,
        "min_age": 21, "max_age": 63
    },
    "BIZ_ISLAM_SEC": {  # Исламское финансирование (залоговое)
        "name": "Исламское финансирование — залоговое",
        "type": "финансирование",
        "markup_from": 12_000,
        "min_sum": 100_000, "max_sum": 10_000_000,
        "min_term_m": 3, "max_term_m": 60,
        "min_age": 21, "max_age": 63
    },
    "BIZ_OVERNIGHT": {  # Депозит «Овернайт»
        "name": "Овернайт",
        "type": "депозит",
        "expected_yield": "12%",
        "min_sum": 1_000_000, "max_sum": 100_000_000,
        "min_term_m": 1, "max_term_m": 12
    },
    "BIZ_PROFIT": {  # Депозит «Выгодный»
        "name": "Выгодный",
        "type": "депозит",
        "expected_yield": "17%",
        "min_sum": 500_000, "max_sum": 100_000_000,
        "min_term_m": 3, "max_term_m": 12
    },
    "BIZ_CARD": {  # Платёжная бизнес-карта
        "name": "Бизнес-карта",
        "type": "платежный",
        "daily_limit": 10_000_000,
        "service_fee": 0,
        "cashout_rule": "до 1 000 000 ₸ — 0%; свыше — 1%",
        "cashback": "до 1% на бизнес-категории"
    },
    "BIZ_TARIFFS": {  # Тарифные пакеты РКО
        "name": "Тарифные пакеты РКО",
        "type": "РКО",
        "payments_per_month": "10–200",
        "fee_range": "0–15 000 ₸/мес",
        "extras": ["Скидки на валютные операции", "Скидки на бизнес-карту",
                   "Проверка контрагентов", "Налоговая отчётность", "Сервисы по развитию бизнеса"]
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

# ВМЕСТО старой pick_products — вставь это
def pick_products_business(
    salary_m: int,
    free_cash_m: float,
    spent_ratio: float,
    period_data: pd.DataFrame,
    cats_share: Dict[str, float],
    tx_count: int
) -> List[Dict[str, Any]]:
    """
    Подбор БИЗНЕС-продуктов:
    - Овердрафт при высокой нагрузке на бюджет или кассовых разрывах
    - Беззалоговое/залоговое исламское финансирование для оборотки/инвестиций
    - Депозиты «Овернайт» и «Выгодный» при наличии свободного кэша
    - Бизнес-карта с кэшбэком — почти всегда релевантна
    - Тарифные пакеты РКО — по активности платежей
    """
    recs: List[Dict[str, Any]] = []
    max_tx = int(period_data["amount"].max()) if not period_data.empty else 0
    avg_tx = int(period_data["amount"].mean()) if not period_data.empty else 0
    tx_pm = max(1, round(tx_count / 3))  # транзакций в месяц (грубо)

    # 1) Овердрафт — при напряженном бюджете или больших разовых платежах
    if spent_ratio >= 0.90 or max_tx >= 300_000:
        recs.append({
            "product": PRODUCTS["BIZ_OVERDRAFT"]["name"],
            "reason": ("Высокая нагрузка на бюджет или крупные платежи — овердрафт до "
                       f"{PRODUCTS['BIZ_OVERDRAFT']['max_sum']:,} ₸ помогает сгладить кассовые разрывы.").replace(",", " "),
            "limits": {"min": PRODUCTS["BIZ_OVERDRAFT"]["min_sum"], "max": PRODUCTS["BIZ_OVERDRAFT"]["max_sum"], "max_term_days": PRODUCTS["BIZ_OVERDRAFT"]["max_term_d"]},
            "note": "Исламский кредитный лимит на счёт (овердрафт) до 30 дней."
        })

    # 2) Исламское финансирование — беззалоговое / залоговое (выбор по величине потребности)
    # эвристика: если средний месячный дефицит > 200k или планируются инвестиции — предлагать беззалоговое
    monthly_gap = max(0, int((spent_ratio - 1.0) * salary_m)) if spent_ratio > 1 else 0
    if spent_ratio >= 0.85 or monthly_gap > 200_000 or max_tx > 500_000:
        recs.append({
            "product": PRODUCTS["BIZ_ISLAM_UNSEC"]["name"],
            "reason": ("Оборотные потребности/закуп — беззалоговое исламское финансирование до "
                       f"{PRODUCTS['BIZ_ISLAM_UNSEC']['max_sum']:,} ₸.").replace(",", " "),
            "limits": {"min": PRODUCTS["BIZ_ISLAM_UNSEC"]["min_sum"], "max": PRODUCTS["BIZ_ISLAM_UNSEC"]["max_sum"],
                       "term_m": [PRODUCTS["BIZ_ISLAM_UNSEC"]["min_term_m"], PRODUCTS["BIZ_ISLAM_UNSEC"]["max_term_m"]]}
        })
        # если потребность крупнее (эвристика > 5 млн) — добавить залоговое
        if max_tx >= 5_000_000 or free_cash_m < 200_000:
            recs.append({
                "product": PRODUCTS["BIZ_ISLAM_SEC"]["name"],
                "reason": ("Крупные потребности/инвестиции — залоговое исламское финансирование до "
                           f"{PRODUCTS['BIZ_ISLAM_SEC']['max_sum']:,} ₸.").replace(",", " "),
                "limits": {"min": PRODUCTS["BIZ_ISLAM_SEC"]["min_sum"], "max": PRODUCTS["BIZ_ISLAM_SEC"]["max_sum"],
                           "term_m": [PRODUCTS["BIZ_ISLAM_SEC"]["min_term_m"], PRODUCTS["BIZ_ISLAM_SEC"]["max_term_m"]]}
            })

    # 3) Депозиты — если есть свободный кэш
    if free_cash_m >= PRODUCTS["BIZ_OVERNIGHT"]["min_sum"]:
        recs.append({
            "product": PRODUCTS["BIZ_OVERNIGHT"]["name"],
            "reason": f"Свободный кэш ≥ {PRODUCTS['BIZ_OVERNIGHT']['min_sum']:,} ₸ — разместить на депозите «Овернайт», доходность {PRODUCTS['BIZ_OVERNIGHT']['expected_yield']}. ".replace(",", " "),
            "suggested_monthly": int(min(free_cash_m, 2_000_000))
        })
    elif free_cash_m >= PRODUCTS["BIZ_PROFIT"]["min_sum"]:
        recs.append({
            "product": PRODUCTS["BIZ_PROFIT"]["name"],
            "reason": f"Свободный кэш ≥ {PRODUCTS['BIZ_PROFIT']['min_sum']:,} ₸ — депозит «Выгодный», доходность {PRODUCTS['BIZ_PROFIT']['expected_yield']}. ".replace(",", " "),
            "suggested_monthly": int(min(free_cash_m, 1_000_000))
        })

    # 4) Бизнес-карта — полезна почти всем (кэшбэк, лимиты, снятие)
    recs.append({
        "product": PRODUCTS["BIZ_CARD"]["name"],
        "reason": (f"Кэшбэк {PRODUCTS['BIZ_CARD']['cashback']}, лимит по операциям до "
                   f"{PRODUCTS['BIZ_CARD']['daily_limit']:,} ₸ в сутки, обслуживание {PRODUCTS['BIZ_CARD']['service_fee']} ₸. "
                   f"Снятие: {PRODUCTS['BIZ_CARD']['cashout_rule']}.").replace(",", " ")
    })

    # 5) Тарифные пакеты РКО — под активность
    def pick_tariff(n: int) -> str:
        if n <= 20: return "Пакет S (до ~20 платежей/мес, абонплата ближе к 0)"
        if n <= 80: return "Пакет M (до ~80 платежей/мес, оптимален по цене/объёму)"
        return "Пакет L (100–200 платежей/мес, максимальные скидки)"

    recs.append({
        "product": PRODUCTS["BIZ_TARIFFS"]["name"],
        "reason": f"Активность ~{tx_pm} платежей/мес — рекомендуем: {pick_tariff(tx_pm)}.",
        "note": "Дополнительно: " + ", ".join(PRODUCTS["BIZ_TARIFFS"]["extras"])
    })

    return recs


def format_kzt(x: int) -> str:
    # 1_234_567 -> "1 234 567 ₸"
    return f"{int(x):,} ₸".replace(",", " ")

# ВМЕСТО make_advice — вставь бизнес-версию
def make_advice_business(
    salary_m: int,
    spent_ratio: float,
    cats_share: Dict[str, float],
    grouped_amounts: Dict[str, int],
    free_cash_m: float
) -> str:
    top_cat = max(grouped_amounts.items(), key=lambda kv: kv[1])[0] if grouped_amounts else "Продукты питания"
    top_amt = grouped_amounts.get(top_cat, 0)

    if spent_ratio >= 0.95:
        return (f"Высокая загрузка бюджета (расходы ≈ {round(spent_ratio*100)}%). "
                f"Сократи «{top_cat}» на 10% (~{format_kzt(int(top_amt*0.1))}) и используй овердрафт для сглаживания "
                f"кассовых разрывов. Для закупов — подумай о беззалоговом исламском финансировании.")
    elif 0.85 <= spent_ratio < 0.95:
        return (f"Бюджет на грани (≈ {round(spent_ratio*100)}%). Проведи ревизию постоянных трат, "
                f"перенеси часть платежей на бизнес-карту (кэшбэк до 1%), а свободный кэш размещай на «Выгодный» депозит.")
    elif 0.70 <= spent_ratio < 0.85:
        return (f"Сбалансировано (≈ {round(spent_ratio*100)}%). Свободный остаток направляй в «Овернайт» "
                f"или «Выгодный», чтобы деньги не лежали без дела; платежи веди через тарифный пакет М.")
    else:
        return (f"Отличный запас (≈ {round(spent_ratio*100)}%). Ускорь рост подушки — часть кэша ежедневно размещай в «Овернайт», "
                f"для операций — бизнес-карта (кэшбэк), для платежей — подходящий тариф РКО.")


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

    # >>> ПЕРЕНЕСЕНО ВВЕРХ <<<
    tx_count = int(period.shape[0])
    avg_ticket = int(period["amount"].mean())
    days = (end_dt.date() - start_dt.date()).days
    tx_per_day = round(tx_count / max(1, days), 2)
    # >>> ПЕРЕНЕСЕНО ВВЕРХ ^^^ <<<

    # Тип пользователя и рекомендации/бизнес-продукты
    products = pick_products_business(salary_m, free_cash_m, spent_ratio, period, cats_share, tx_count)

    # Интересные факты (как раньше)
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
        from_week = {0:"Понедельник",1:"Вторник",2:"Среда",3:"Четверг",4:"Пятница",5:"Суббота",6:"Воскресенье"}
        wd = int(wd_avg.idxmax())
        insights.append(f"Самый затратный день недели: {from_week[wd]} (средний чек {int(wd_avg.max()):,} ₸)".replace(",", " "))

    top_cat = max(cats, key=lambda x: x["amount"]) if cats else None
    if top_cat:
        insights.append(f"Топ-категория: {top_cat['category']} — {round(top_cat['share'] * 100, 1)}% всех трат.")

    idx = period["amount"].idxmax()
    if pd.notna(idx):
        row = period.loc[idx]
        insights.append(f"Макс. транзакция: {int(row['amount']):,} ₸ — {row['category']} — {row['date'].date()}".replace(",", " "))

    # Совет (бизнес-версия)
    advice = make_advice_business(salary_m, spent_ratio, cats_share, grouped_amounts, free_cash_m)

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
            "financial_type": financial_type(spent_ratio)
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
