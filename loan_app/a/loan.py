"""
Project 14 - Loan Calculator (standard library only)

Shared data structure (a "loan" dictionary) passed between all parts:
    {
        "amount":      float,   # loan principal
        "annual_rate": float,   # annual interest rate in %
        "months":      int,     # term in months
        "payment":     float,   # fixed monthly payment (rounded to cents)
        "schedule":    list,    # list of row dicts (see build_schedule)
    }
A schedule row is:
    {"month": int, "payment": float, "interest": float,
     "principal": float, "balance": float}

Sections (matching the suggested role split):
    A. CALCULATIONS      - formulas, schedules, extra payments, flat rate,
                           affordability, early settlement
    B. DISPLAY AND INPUT - validated input, tables, chart, menus
    C. DATA AND FILES    - CSV, text summaries, JSON scenarios, self-tests
"""

import csv
import json
import math
import os
import sys
from datetime import datetime

SCENARIO_FILE = "loan_scenarios.json"
SUMMARY_FILE = "loan_summaries.txt"
MAX_RATE = 100.0       # sensible upper limit for annual rate (%)
MAX_MONTHS = 600       # 50 years


# =====================================================================
# A. CALCULATIONS
# =====================================================================
def payment_exact(amount, annual_rate, months):
    """Fixed monthly payment (unrounded): P*r / (1 - (1+r)^-n)."""
    r = annual_rate / 100 / 12
    if r == 0:
        return amount / months
    return amount * r / (1 - (1 + r) ** -months)


def monthly_payment(amount, annual_rate, months):
    return round(payment_exact(amount, annual_rate, months), 2)


def totals_from_formula(amount, annual_rate, months):
    """Headline numbers: (monthly payment, total repaid, total interest)."""
    exact = payment_exact(amount, annual_rate, months)
    total = round(exact * months, 2)
    return round(exact, 2), total, round(total - amount, 2)


def build_schedule(amount, annual_rate, months, extra=0.0, payment=None):
    """
    Full amortisation schedule, rounded to kobo every month.
    The last payment is adjusted so the final balance is exactly 0.00.
    extra   : extra amount paid towards principal every month.
    payment : override the regular payment (used by affordability mode).
    """
    r = annual_rate / 100 / 12
    if payment is None:
        payment = monthly_payment(amount, annual_rate, months)
    balance = round(amount, 2)
    rows = []
    month = 0
    while balance > 0:
        month += 1
        interest = round(balance * r, 2)
        principal = round(payment - interest + extra, 2)
        # clear the loan on the last scheduled month or when the
        # payment is enough to cover what is left
        if principal >= balance or (extra == 0 and month >= months):
            principal = balance
        paid = round(interest + principal, 2)
        balance = round(balance - principal, 2)
        rows.append({"month": month, "payment": paid, "interest": interest,
                     "principal": principal, "balance": balance})
        if month > 5000:            # safety net against endless loops
            break
    return rows


def make_loan(amount, annual_rate, months):
    return {
        "amount": amount,
        "annual_rate": annual_rate,
        "months": months,
        "payment": monthly_payment(amount, annual_rate, months),
        "schedule": build_schedule(amount, annual_rate, months),
    }


def schedule_totals(schedule):
    """(total repaid, total interest) from an actual schedule."""
    return (round(sum(r["payment"] for r in schedule), 2),
            round(sum(r["interest"] for r in schedule), 2))


def extra_payment_effect(loan, extra):
    """Months and interest saved by paying `extra` more each month."""
    base = loan["schedule"]
    fast = build_schedule(loan["amount"], loan["annual_rate"],
                          loan["months"], extra=extra)
    _, base_interest = schedule_totals(base)
    _, fast_interest = schedule_totals(fast)
    return {
        "new_months": len(fast),
        "months_saved": len(base) - len(fast),
        "interest_saved": round(base_interest - fast_interest, 2),
        "new_interest": fast_interest,
        "schedule": fast,
    }


def flat_rate_loan(amount, annual_rate, months):
    """Flat-rate loan: interest is always charged on the ORIGINAL amount."""
    interest = round(amount * annual_rate / 100 * months / 12, 2)
    total = round(amount + interest, 2)
    return {"interest": interest, "total": total,
            "payment": round(total / months, 2)}


def equivalent_reducing_rate(amount, payment, months):
    """Annual % on a reducing balance that gives the same monthly payment."""
    lo, hi = 0.0, 1000.0
    for _ in range(200):            # bisection search
        mid = (lo + hi) / 2
        if payment_exact(amount, mid, months) < payment:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def max_loan_for_payment(payment, annual_rate, months):
    """Largest loan whose monthly payment is <= `payment`."""
    r = annual_rate / 100 / 12
    if r == 0:
        return payment * months
    return payment * (1 - (1 + r) ** -months) / r


def months_needed(amount, annual_rate, payment):
    """Months to repay `amount` paying `payment` a month (None if never)."""
    r = annual_rate / 100 / 12
    if r == 0:
        return math.ceil(amount / payment)
    if payment <= amount * r:
        return None                 # payment does not even cover interest
    n = -math.log(1 - amount * r / payment) / math.log(1 + r)
    return math.ceil(n - 1e-9)


def early_settlement(loan, month):
    """Amount needed to clear the loan right after payment number `month`."""
    sched = loan["schedule"]
    month = max(0, min(month, len(sched)))
    balance = loan["amount"] if month == 0 else sched[month - 1]["balance"]
    paid = sum(r["payment"] for r in sched[:month])
    interest_paid = sum(r["interest"] for r in sched[:month])
    _, total_interest = schedule_totals(sched)
    return {
        "month": month,
        "settlement": round(balance, 2),
        "paid_so_far": round(paid, 2),
        "interest_paid": round(interest_paid, 2),
        "interest_saved": round(total_interest - interest_paid, 2),
    }


# =====================================================================
# B. DISPLAY AND INPUT
# =====================================================================
def money(x):
    return f"{x:,.2f}"


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        print("\nInput closed. Goodbye!")
        sys.exit(0)


def ask_number(prompt, low, high=None, allow_low=False):
    """Re-prompt until a number in range is entered."""
    while True:
        text = ask(prompt).replace(",", "")
        try:
            value = float(text)
        except ValueError:
            print("  Please enter a number.")
            continue
        too_low = value < low if allow_low else value <= low
        if too_low:
            print(f"  Value must be {'at least' if allow_low else 'greater than'} {low:,}.")
        elif high is not None and value > high:
            print(f"  Value must be {high:,} or less.")
        else:
            return value


def ask_yes_no(prompt):
    return ask(prompt + " (y/n): ").lower().startswith("y")


def ask_amount():
    return ask_number("Loan amount: ", 0)


def ask_rate():
    return ask_number(f"Annual interest rate (%) [0-{MAX_RATE:.0f}]: ",
                      0, MAX_RATE, allow_low=True)


def ask_term():
    """Term in years or months, returned as whole months."""
    while True:
        unit = ask("Enter term in (Y)ears or (M)onths? [Y/M]: ").lower()
        if unit in ("y", "m"):
            break
        print("  Please type Y or M.")
    while True:
        if unit == "y":
            value = ask_number("Term (years): ", 0)
            months = round(value * 12)
        else:
            value = ask_number("Term (months): ", 0)
            months = round(value)
        if months < 1:
            print("  The term must be at least 1 month.")
        elif months > MAX_MONTHS:
            print(f"  The term can be at most {MAX_MONTHS} months "
                  f"({MAX_MONTHS // 12} years).")
        else:
            return months


def ask_loan_inputs():
    return ask_amount(), ask_rate(), ask_term()


def term_text(months):
    y, m = divmod(months, 12)
    parts = []
    if y:
        parts.append(f"{y} year{'s' if y != 1 else ''}")
    if m:
        parts.append(f"{m} month{'s' if m != 1 else ''}")
    return " ".join(parts)


def print_summary(loan):
    pay, total, interest = totals_from_formula(
        loan["amount"], loan["annual_rate"], loan["months"])
    print()
    print(f"Monthly payment: {money(pay)}")
    print(f"Total repaid:    {money(total)}")
    print(f"Total interest:  {money(interest)}")


def print_schedule(schedule, limit=None):
    rows = schedule if limit is None else schedule[:limit]
    print()
    print(f"{'Month':>5} {'Payment':>14} {'Interest':>14} "
          f"{'Principal':>14} {'Balance':>16}")
    print("-" * 67)
    for r in rows:
        print(f"{r['month']:>5} {money(r['payment']):>14} "
              f"{money(r['interest']):>14} {money(r['principal']):>14} "
              f"{money(r['balance']):>16}")
    if limit is not None and len(schedule) > limit:
        print(f"... ({len(schedule) - limit} more months not shown)")


def balance_chart(loan, width=40, points=12):
    """Text chart of the balance falling over time."""
    sched = loan["schedule"]
    n = len(sched)
    steps = min(points, n)
    picks = sorted({round(i * n / steps) for i in range(1, steps + 1)})
    print(f"\n  Balance over time (each # = {money(loan['amount'] / width)})")
    print(f"  {'Month':>5} | " + "balance")
    print(f"  {0:>5} | {'#' * width} {money(loan['amount'])}")
    for m in picks:
        bal = sched[m - 1]["balance"]
        bar = "#" * round(bal / loan["amount"] * width)
        print(f"  {m:>5} | {bar} {money(bal)}")


def print_comparison(options):
    """options: list of (name, loan). Side-by-side table."""
    rows = []
    for name, loan in options:
        pay, total, interest = totals_from_formula(
            loan["amount"], loan["annual_rate"], loan["months"])
        rows.append((name, loan, pay, total, interest))
    cheapest = min(r[4] for r in rows)
    print()
    print(f"{'Option':<16}{'Amount':>14}{'Rate %':>8}{'Term':>12}"
          f"{'Monthly':>14}{'Total repaid':>17}{'Interest':>15}")
    print("-" * 96)
    for name, loan, pay, total, interest in rows:
        flag = "  <- lowest interest" if interest == cheapest and len(rows) > 1 else ""
        print(f"{name[:15]:<16}{money(loan['amount']):>14}"
              f"{loan['annual_rate']:>8.2f}{term_text(loan['months']):>12}"
              f"{money(pay):>14}{money(total):>17}{money(interest):>15}{flag}")


# ---------- menu actions ----------
def action_new_loan():
    amount, rate, months = ask_loan_inputs()
    loan = make_loan(amount, rate, months)
    print_summary(loan)
    print("\nRepayment schedule (first 12 months):")
    print_schedule(loan["schedule"], 12)

    path = save_summary_text(loan)
    print(f"\n(Summary saved to {path})")

    if ask_yes_no("\nSave the FULL schedule to a CSV file?"):
        print("Saved:", save_schedule_csv(loan))

    if ask_yes_no("Try an extra monthly payment?"):
        extra = ask_number("Extra amount per month: ", 0)
        res = extra_payment_effect(loan, extra)
        print(f"\nWith {money(extra)} extra each month:")
        print(f"  Loan repaid in {res['new_months']} months "
              f"({res['months_saved']} months sooner)")
        print(f"  Interest saved: {money(res['interest_saved'])}")

    if ask_yes_no("Check an early settlement amount?"):
        early_settlement_flow(loan)

    if ask_yes_no("Show a balance chart?"):
        balance_chart(loan)

    name = ask("Save as a named scenario? (type a name, or press Enter to skip): ")
    if name:
        save_scenario(name, amount, rate, months)
        print(f"Scenario '{name}' saved.")


def early_settlement_flow(loan):
    n = len(loan["schedule"])
    m = int(ask_number(f"Settle after which month? (0-{n}): ", 0, n, allow_low=True))
    r = early_settlement(loan, m)
    print(f"\nTo clear the loan after payment {r['month']}:")
    print(f"  Settlement amount:   {money(r['settlement'])}")
    print(f"  Paid so far:         {money(r['paid_so_far'])}")
    print(f"  Interest paid so far:{money(r['interest_paid']):>14}")
    print(f"  Interest saved:      {money(r['interest_saved'])}")


def action_early_settlement():
    amount, rate, months = ask_loan_inputs()
    early_settlement_flow(make_loan(amount, rate, months))


def action_compare():
    count = int(ask_number("How many options to compare (2 or 3)? ", 2, 3, allow_low=True))
    amount = ask_amount()
    options = []
    for i in range(1, count + 1):
        print(f"\n--- Option {i} ---")
        rate = ask_rate()
        months = ask_term()
        options.append((f"Option {i}", make_loan(amount, rate, months)))
    print_comparison(options)
    for _, loan in options:
        save_summary_text(loan)
    print("\n(Summaries saved to", SUMMARY_FILE + ")")


def action_flat_vs_reducing():
    amount, rate, months = ask_loan_inputs()
    red_pay, red_total, red_int = totals_from_formula(amount, rate, months)
    flat = flat_rate_loan(amount, rate, months)
    eq = equivalent_reducing_rate(amount, flat["payment"], months)
    print(f"\n{'':<22}{'Reducing balance':>18}{'Flat rate':>18}")
    print(f"{'Monthly payment':<22}{money(red_pay):>18}{money(flat['payment']):>18}")
    print(f"{'Total repaid':<22}{money(red_total):>18}{money(flat['total']):>18}")
    print(f"{'Total interest':<22}{money(red_int):>18}{money(flat['interest']):>18}")
    diff = round(flat["interest"] - red_int, 2)
    print(f"\nThe flat-rate loan costs {money(diff)} more in interest.")
    print("Why: with a reducing balance, interest is charged only on what you")
    print("still owe, and that shrinks every month. With a flat rate, interest")
    print("is charged on the ORIGINAL amount for the whole term, even though")
    print("you are repaying the loan month by month.")
    print(f"A flat rate of {rate:.2f}% is like a reducing-balance rate of "
          f"about {eq:.2f}%.")


def action_affordability():
    print("\n1) Largest loan I can afford (given payment, rate and term)")
    print("2) Term needed to repay a loan (given payment and rate)")
    choice = ask("Choose 1 or 2: ")
    if choice == "1":
        pay = ask_number("Maximum monthly payment: ", 0)
        rate = ask_rate()
        months = ask_term()
        biggest = max_loan_for_payment(pay, rate, months)
        print(f"\nLargest loan: {money(biggest)} over {term_text(months)} "
              f"at {rate:.2f}%")
    elif choice == "2":
        amount = ask_amount()
        rate = ask_rate()
        pay = ask_number("Monthly payment you will pay: ", 0)
        n = months_needed(amount, rate, pay)
        if n is None:
            minimum = amount * rate / 100 / 12
            print(f"\nThat payment does not even cover the monthly interest "
                  f"({money(minimum)}).\nThe loan would never be repaid. "
                  f"Pay more than {money(minimum)}.")
        else:
            sched = build_schedule(amount, rate, n, payment=pay)
            total, interest = schedule_totals(sched)
            print(f"\nTime needed: {len(sched)} months ({term_text(len(sched))})")
            print(f"Total repaid:   {money(total)}")
            print(f"Total interest: {money(interest)}")
    else:
        print("Invalid choice.")


def action_scenarios():
    print("\n1) Save a new scenario")
    print("2) List saved scenarios")
    print("3) Compare saved scenarios (table + balance charts)")
    choice = ask("Choose 1-3: ")
    if choice == "1":
        name = ask("Scenario name: ")
        if not name:
            print("A name is required.")
            return
        amount, rate, months = ask_loan_inputs()
        save_scenario(name, amount, rate, months)
        print(f"Scenario '{name}' saved to {SCENARIO_FILE}.")
    elif choice in ("2", "3"):
        data = load_scenarios()
        if not data:
            print("No saved scenarios yet.")
            return
        print("\nSaved scenarios:")
        for name, s in data.items():
            print(f"  {name}: {money(s['amount'])} at {s['annual_rate']}% "
                  f"for {term_text(s['months'])}")
        if choice == "3":
            raw = ask("\nNames to compare, separated by commas (Enter = all): ")
            names = [n.strip() for n in raw.split(",") if n.strip()] or list(data)
            options = []
            for n in names:
                if n not in data:
                    print(f"  '{n}' not found, skipped.")
                    continue
                s = data[n]
                options.append((n, make_loan(s["amount"], s["annual_rate"], s["months"])))
            if len(options) < 2:
                print("Need at least two valid scenarios to compare.")
                return
            print_comparison(options)
            for n, loan in options:
                print(f"\n[{n}]")
                balance_chart(loan)
    else:
        print("Invalid choice.")


# =====================================================================
# C. DATA AND FILES
# =====================================================================
def save_schedule_csv(loan, filename=None):
    sched = loan["schedule"]
    # final balance must be exactly 0 after rounding
    assert sched[-1]["balance"] == 0, "final balance is not zero"
    if filename is None:
        filename = "loan_schedule.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Month", "Payment", "Interest", "Principal", "Balance"])
        for r in sched:
            w.writerow([r["month"], f"{r['payment']:.2f}", f"{r['interest']:.2f}",
                        f"{r['principal']:.2f}", f"{r['balance']:.2f}"])
    return os.path.abspath(filename)


def save_summary_text(loan, filename=SUMMARY_FILE):
    pay, total, interest = totals_from_formula(
        loan["amount"], loan["annual_rate"], loan["months"])
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"=== Loan calculation - {stamp} ===\n")
        f.write(f"Loan amount:          {money(loan['amount'])}\n")
        f.write(f"Annual interest rate: {loan['annual_rate']}%\n")
        f.write(f"Term:                 {loan['months']} months "
                f"({term_text(loan['months'])})\n")
        f.write(f"Monthly payment:      {money(pay)}\n")
        f.write(f"Total repaid:         {money(total)}\n")
        f.write(f"Total interest:       {money(interest)}\n\n")
    return os.path.abspath(filename)


def load_scenarios(filename=SCENARIO_FILE):
    try:
        with open(filename, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_scenario(name, amount, annual_rate, months, filename=SCENARIO_FILE):
    data = load_scenarios(filename)
    data[name] = {"amount": amount, "annual_rate": annual_rate, "months": months}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------- self-tests ----------
def close(a, b, tol=0.01):
    return abs(a - b) <= tol


def run_tests():
    tests = 0

    def check(condition, label):
        nonlocal tests
        assert condition, "FAILED: " + label
        tests += 1

    # 1. the example from the project brief
    pay, total, interest = totals_from_formula(1_000_000, 12, 2 * 12)
    check(close(pay, 47073.47), "example monthly payment")
    check(close(total, 1129763.33), "example total repaid")
    check(close(interest, 129763.33), "example total interest")

    # 2-4. other known payments (standard mortgage tables)
    check(close(monthly_payment(100000, 6, 360), 599.55), "100k @6% 30y")
    check(close(monthly_payment(200000, 4.5, 360), 1013.37), "200k @4.5% 30y")
    check(close(monthly_payment(100000, 5, 180), 790.79), "100k @5% 15y")

    # 5. zero-rate loan does not divide by zero
    check(close(monthly_payment(12000, 0, 12), 1000.00), "0% rate")

    # 6. final balance exactly 0 for many different loans
    for amt, rate, mon in [(1_000_000, 12, 24), (123_456.78, 7.3, 37),
                           (5000, 0, 7), (999_999.99, 25, 360), (100, 1, 1)]:
        s = build_schedule(amt, rate, mon)
        check(s[-1]["balance"] == 0, f"final balance 0 for {amt},{rate},{mon}")
    # 7. principal repaid adds up to the loan amount
    s = build_schedule(250000, 3.5, 360)
    check(close(sum(r["principal"] for r in s), 250000, 0.001), "principal sums to amount")
    check(len(s) == 360, "schedule length")

    # 8. flat rate: 100,000 at 10% for 2 years = 20,000 interest
    f = flat_rate_loan(100000, 10, 24)
    check(close(f["interest"], 20000), "flat interest")
    check(close(f["payment"], 5000), "flat payment")
    check(f["interest"] > totals_from_formula(100000, 10, 24)[2], "flat costs more")

    # 9. affordability is the inverse of the payment formula
    p = payment_exact(300000, 8, 240)
    check(close(max_loan_for_payment(p, 8, 240), 300000, 0.01), "max loan inverse")
    check(months_needed(300000, 8, p) == 240, "months needed inverse")
    check(months_needed(100000, 12, 500) is None, "payment below interest")

    # 10. extra payments save months and interest
    loan = make_loan(500000, 10, 120)
    res = extra_payment_effect(loan, 5000)
    check(res["months_saved"] > 0 and res["interest_saved"] > 0, "extra payments help")
    check(res["schedule"][-1]["balance"] == 0, "extra schedule ends at 0")

    # 11. early settlement
    check(close(early_settlement(loan, 0)["settlement"], 500000), "settle at month 0")
    check(early_settlement(loan, 120)["settlement"] == 0, "settle at end")
    check(close(early_settlement(loan, 60)["settlement"],
                loan["schedule"][59]["balance"]), "settle midway")

    print(f"All {tests} self-tests passed.")


# =====================================================================
# MAIN MENU
# =====================================================================
MENU = """
==================== LOAN CALCULATOR ====================
 1. Calculate a loan (payment, schedule, extras)
 2. Compare 2-3 loan options
 3. Flat-rate vs reducing-balance interest
 4. Affordability (largest loan / term needed)
 5. Early-settlement calculator
 6. Saved scenarios (save / list / compare)
 7. Run self-tests
 0. Exit
"""

ACTIONS = {
    "1": action_new_loan,
    "2": action_compare,
    "3": action_flat_vs_reducing,
    "4": action_affordability,
    "5": action_early_settlement,
    "6": action_scenarios,
    "7": run_tests,
}


def main():
    if "--test" in sys.argv:
        run_tests()
        return
    while True:
        print(MENU)
        choice = ask("Choose an option: ")
        if choice == "0":
            print("Goodbye!")
            return
        action = ACTIONS.get(choice)
        if action is None:
            print("Please choose a number from the menu.")
            continue
        while True:
            action()
            if choice == "7" or not ask_yes_no("\nCalculate another?"):
                break


if __name__ == "__main__":
    main()
