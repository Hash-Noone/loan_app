"""File persistence for CSV schedules, text summaries, and JSON scenarios."""

import csv
import json
import os
from datetime import datetime

from calculations import calculate_schedule_quote
from models import (
    DEFAULT_SCENARIO_FILE,
    DEFAULT_SCHEDULE_FILE,
    DEFAULT_SUMMARY_FILE,
)


def format_currency(amount: float) -> str:
    """Format a numeric amount with thousands separators and two decimals."""
    return f"{amount:,.2f}"


def format_term(months: int) -> str:
    """Convert a month count into a readable years/months string."""
    years, rem_months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if rem_months:
        parts.append(f"{rem_months} month{'s' if rem_months != 1 else ''}")
    return " ".join(parts)


def save_schedule_csv(
    loan: dict, filename: str = DEFAULT_SCHEDULE_FILE
) -> str:
    """Write a loan's amortisation schedule to CSV and return its absolute path."""
    schedule = loan["schedule"]
    if not schedule or schedule[-1]["balance"] != 0:
        raise ValueError("Cannot export schedule: final balance is not zero.")

    with open(filename, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Month", "Payment", "Interest", "Principal", "Balance"])
        for row in schedule:
            writer.writerow(
                [
                    row["month"],
                    f"{row['payment']:.2f}",
                    f"{row['interest']:.2f}",
                    f"{row['principal']:.2f}",
                    f"{row['balance']:.2f}",
                ]
            )
    return os.path.abspath(filename)


def save_summary_text(
    loan: dict, filename: str = DEFAULT_SUMMARY_FILE
) -> str:
    """Append a formatted loan summary block and return the file path."""
    schedule = loan["schedule"]
    payment, final_payment, total_repaid, total_interest = calculate_schedule_quote(
        schedule
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(filename, "a", encoding="utf-8") as handle:
        handle.write(f"=== Loan calculation - {timestamp} ===\n")
        handle.write(f"Loan amount:          {format_currency(loan['amount'])}\n")
        handle.write(f"Annual interest rate: {loan['annual_rate']}%\n")
        handle.write(
            f"Term:                 {loan['months']} months "
            f"({format_term(loan['months'])})\n"
        )
        handle.write(f"Monthly payment:      {format_currency(payment)}\n")
        if final_payment != payment:
            handle.write(f"Final payment:        {format_currency(final_payment)}\n")
        if (
            schedule
            and schedule[-1]["balance"] == 0
            and schedule[-1]["month"] < loan["months"]
        ):
            handle.write(f"Payoff month:         {schedule[-1]['month']}\n")
        handle.write(f"Total repaid:         {format_currency(total_repaid)}\n")
        handle.write(f"Total interest:       {format_currency(total_interest)}\n\n")

    return os.path.abspath(filename)


def load_scenarios(filename: str = DEFAULT_SCENARIO_FILE) -> dict:

    """Load saved loan scenarios from JSON, returning `{}` if missing/corrupt."""

    try:
        with open(filename, encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_scenario(
            name: str,
            amount: float,
            annual_rate: float,
            months: int,
            filename: str = DEFAULT_SCENARIO_FILE,
        ) -> None:
    """Persist a named loan scenario to the JSON store."""
    scenarios = load_scenarios(filename)
    scenarios[name] = {
        "amount": amount,
        "annual_rate": annual_rate,
        "months": months,
    }
    with open(filename, "w", encoding="utf-8") as handle:
        json.dump(scenarios, handle, indent=2)