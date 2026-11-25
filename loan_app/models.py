"""Shared data structures and domain constants for the loan calculator."""

MAX_RATE = 100.0  # Sensible upper limit for annual interest rate (%)
MAX_MONTHS = 600  # 50 years

DEFAULT_SCENARIO_FILE = "loan_scenarios.json"
DEFAULT_SUMMARY_FILE = "loan_summaries.txt"
DEFAULT_SCHEDULE_FILE = "loan_schedule.csv"


def create_loan(amount: float, annual_rate: float, months: int) -> dict:
    """Build a loan dictionary with payment and full amortisation schedule."""
    from calculations import build_schedule

    schedule = build_schedule(amount, annual_rate, months)
    return {
        "amount": amount,
        "annual_rate": annual_rate,
        "months": months,
        "payment": schedule[0]["payment"] if schedule else 0.0,
        "schedule": schedule,
    }