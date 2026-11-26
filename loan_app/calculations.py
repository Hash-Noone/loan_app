"""Pure amortisation, interest, affordability, and settlement calculations."""

import math


def calculate_exact_payment(amount: float, annual_rate: float, months: int) -> float:
    """Fixed monthly payment (unrounded): P*r / (1 - (1+r)^-n)."""
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        return amount / months
    return amount * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def calculate_monthly_payment(amount: float, annual_rate: float, months: int) -> float:
    """Fixed monthly payment rounded to two decimal places."""
    return round(calculate_exact_payment(amount, annual_rate, months), 2)


def calculate_formula_totals(
    amount: float, annual_rate: float, months: int
) -> tuple[float, float, float]:
    """Return (monthly_payment, total_repaid, total_interest) from formula."""
    exact = calculate_exact_payment(amount, annual_rate, months)
    total_repaid = round(exact * months, 2)
    total_interest = round(total_repaid - amount, 2)
    return round(exact, 2), total_repaid, total_interest


def build_schedule(
    amount: float,
    annual_rate: float,
    months: int,
    extra_monthly: float = 0.0,
    payment_override: float | None = None,
) -> list[dict]:
    
    """Generate a monthly amortisation schedule ending at a 0.00 balance."""
    monthly_rate = annual_rate / 100 / 12
    regular_payment = (
        calculate_monthly_payment(amount, annual_rate, months)
        if payment_override is None
        else payment_override
    )

    balance = round(amount, 2)
    schedule = []
    month = 0

    while balance > 0:
        month += 1
        interest = round(balance * monthly_rate, 2)
        principal = round(regular_payment - interest + extra_monthly, 2)

        if principal >= balance or (extra_monthly == 0 and month >= months):
            principal = balance

        paid = round(interest + principal, 2)
        balance = round(balance - principal, 2)
        schedule.append(
            {
                "month": month,
                "payment": paid,
                "interest": interest,
                "principal": principal,
                "balance": balance,
            }
        )
        if month > 5000:  # Guard against runaway loops
            break

    return schedule



def calculate_schedule_totals(schedule: list[dict]) -> tuple[float, float]:
    """Return (total_repaid, total_interest) summed from schedule rows."""
    total_repaid = round(sum(row["payment"] for row in schedule), 2)
    total_interest = round(sum(row["interest"] for row in schedule), 2)
    return total_repaid, total_interest


def evaluate_extra_payment(loan: dict, extra_monthly: float) -> dict:
    """Calculate time and interest saved by adding `extra_monthly` each month."""
    base_schedule = loan["schedule"]
    accelerated_schedule = build_schedule(
        loan["amount"],
        loan["annual_rate"],
        loan["months"],
        extra_monthly=extra_monthly,
    )
    _, base_interest = calculate_schedule_totals(base_schedule)
    _, accelerated_interest = calculate_schedule_totals(accelerated_schedule)

    return {
        "new_months": len(accelerated_schedule),
        "months_saved": len(base_schedule) - len(accelerated_schedule),
        "interest_saved": round(base_interest - accelerated_interest, 2),
        "new_interest": accelerated_interest,
        "schedule": accelerated_schedule,
    }


def calculate_flat_rate_loan(amount: float, annual_rate: float, months: int) -> dict:
    """Calculate interest, total repayment, and payment for a flat-rate loan."""
    interest = round(amount * annual_rate / 100 * months / 12, 2)
    total = round(amount + interest, 2)
    return {
        "interest": interest,
        "total": total,
        "payment": round(total / months, 2),
    }


def find_equivalent_reducing_rate(
    amount: float, payment: float, months: int
) -> float:
    """Approximate annual reducing-balance rate matching `payment` via bisection."""
    low, high = 0.0, 1000.0
    for _ in range(200):
        mid = (low + high) / 2
        if calculate_exact_payment(amount, mid, months) < payment:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def calculate_max_loan_for_payment(
    payment: float, annual_rate: float, months: int
) -> float:
    """Largest principal affordable given a monthly payment cap, rate, and term."""
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        return payment * months
    return payment * (1 - (1 + monthly_rate) ** -months) / monthly_rate


def calculate_months_needed(
    amount: float, annual_rate: float, payment: float
) -> int | None:
    """Months required to clear `amount` at `payment`, or None if never repaid."""
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        return math.ceil(amount / payment)
    if payment <= amount * monthly_rate:
        return None
    raw_months = -math.log(1 - amount * monthly_rate / payment) / math.log(
        1 + monthly_rate
    )
    return math.ceil(raw_months - 1e-9)


def calculate_early_settlement(loan: dict, after_month: int) -> dict:
    """Compute payoff figure and interest impact right after `after_month`."""
    schedule = loan["schedule"]
    clamped_month = max(0, min(after_month, len(schedule)))

    balance = (
        loan["amount"]
        if clamped_month == 0
        else schedule[clamped_month - 1]["balance"]
    )
    paid_so_far = sum(row["payment"] for row in schedule[:clamped_month])
    interest_paid = sum(row["interest"] for row in schedule[:clamped_month])
    _, total_interest = calculate_schedule_totals(schedule)

    return {
        "month": clamped_month,
        "settlement": round(balance, 2),
        "paid_so_far": round(paid_so_far, 2),
        "interest_paid": round(interest_paid, 2),
        "interest_saved": round(total_interest - interest_paid, 2),
    }