"""Pure amortisation, interest, affordability, and settlement calculations."""

from collections.abc import Iterator
from decimal import Decimal, ROUND_DOWN


PAYOFF_MONTH_LIMIT = 10_000


class IncompletePayoffError(ValueError):
    def __init__(self, months: int, balance: float) -> None:
        self.months = months
        self.balance = balance
        super().__init__(f"Balance of {balance:,.2f} remains after {months} months.")


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


def _to_cents(amount: float) -> int:
    return round(Decimal(str(amount)) * 100)


def _payment_cap_cents(payment: float) -> int:
    return int((Decimal(str(payment)) * 100).to_integral_value(rounding=ROUND_DOWN))


def _monthly_interest_cents(balance: int, annual_rate: Decimal) -> int:
    return round(balance * annual_rate / 1200)


def _schedule_rows(
    balance: int, annual_rate: Decimal, payment: int, months: int, adjust_final: bool
) -> Iterator[tuple[int, int, int, int]]:
    for month in range(1, months + 1):
        if balance <= 0:
            break
        interest = _monthly_interest_cents(balance, annual_rate)
        if adjust_final and month == months:
            principal = balance
        elif not adjust_final and payment <= interest:
            break
        else:
            principal = min(payment - interest, balance)
        balance -= principal
        yield month, interest, principal, balance


def build_schedule(
    amount: float,
    annual_rate: float,
    months: int,
    extra_monthly: float = 0.0,
    payment_override: float | None = None,
) -> list[dict]:
    """Build a schedule; capped payments may leave a balance at the term limit."""
    adjust_final = payment_override is None and extra_monthly == 0
    balance_cents = _to_cents(amount)
    rate = Decimal(str(annual_rate))
    if payment_override is None:
        regular_payment = max(
            _to_cents(calculate_monthly_payment(amount, annual_rate, months)),
            _monthly_interest_cents(balance_cents, rate),
        )
        payment = regular_payment + _payment_cap_cents(extra_monthly)
        limit = months if adjust_final else PAYOFF_MONTH_LIMIT
    else:
        payment = _payment_cap_cents(payment_override) + _payment_cap_cents(
            extra_monthly
        )
        limit = months

    return [
        {
            "month": month,
            "payment": (interest + principal) / 100,
            "interest": interest / 100,
            "principal": principal / 100,
            "balance": balance / 100,
        }
        for month, interest, principal, balance in _schedule_rows(
            balance_cents, rate, payment, limit, adjust_final
        )
    ]


def _require_payoff(schedule: list[dict], amount: float) -> None:
    balance = schedule[-1]["balance"] if schedule else _to_cents(amount) / 100
    if balance > 0:
        raise IncompletePayoffError(len(schedule), balance)


def build_payoff_schedule(amount: float, annual_rate: float, payment: float) -> list[dict]:
    """Build a capped schedule, raising if it cannot clear within the payoff limit."""
    schedule = build_schedule(
        amount, annual_rate, PAYOFF_MONTH_LIMIT, payment_override=payment
    )
    _require_payoff(schedule, amount)
    return schedule


def calculate_schedule_totals(schedule: list[dict]) -> tuple[float, float]:
    """Return (total_repaid, total_interest) summed from schedule rows."""
    total_repaid = sum(_to_cents(row["payment"]) for row in schedule) / 100
    total_interest = sum(_to_cents(row["interest"]) for row in schedule) / 100
    return total_repaid, total_interest


def calculate_schedule_quote(schedule: list[dict]) -> tuple[float, float, float, float]:
    """Return the first and last payments, total repaid, and interest."""
    if not schedule:
        return 0.0, 0.0, 0.0, 0.0
    total_repaid, total_interest = calculate_schedule_totals(schedule)
    return schedule[0]["payment"], schedule[-1]["payment"], total_repaid, total_interest


def evaluate_extra_payment(loan: dict, extra_monthly: float) -> dict:
    """Calculate time and interest saved by adding `extra_monthly` each month."""
    base_schedule = loan["schedule"]
    accelerated_schedule = build_schedule(
        loan["amount"],
        loan["annual_rate"],
        loan["months"],
        extra_monthly=extra_monthly,
    )
    _require_payoff(accelerated_schedule, loan["amount"])
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
    payment_cents = _payment_cap_cents(payment)
    low, high = 0, payment_cents * months
    if annual_rate == 0:
        return high / 100

    rate = Decimal(str(annual_rate))
    while low < high:
        principal = (low + high + 1) // 2
        balance = principal
        for _, _, _, balance in _schedule_rows(
            principal, rate, payment_cents, months, adjust_final=False
        ):
            pass
        if balance == 0:
            low = principal
        else:
            high = principal - 1
    return low / 100


def calculate_months_needed(
    amount: float, annual_rate: float, payment: float
) -> int | None:
    """Return the capped payoff term, or None if the payment cannot reduce principal."""
    try:
        return len(build_payoff_schedule(amount, annual_rate, payment))
    except IncompletePayoffError as error:
        if error.months == 0:
            return None
        raise


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