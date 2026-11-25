"""Command-line interface: input validation, formatting, charts, and menus."""

import sys

from calculations import (
    IncompletePayoffError,
    build_payoff_schedule,
    calculate_early_settlement,
    calculate_flat_rate_loan,
    calculate_max_loan_for_payment,
    calculate_schedule_quote,
    calculate_schedule_totals,
    evaluate_extra_payment,
    find_equivalent_reducing_rate,
)
from models import DEFAULT_SUMMARY_FILE, MAX_MONTHS, MAX_RATE, create_loan
from storage import (
    format_currency,
    format_term,
    load_scenarios,
    save_scenario,
    save_schedule_csv,
    save_summary_text,
)

MAIN_MENU = """
            ==================== LOAN CALCULATOR ====================
            1. Calculate a loan (payment, schedule, extras)
            2. Compare 2-3 loan options
            3. Flat-rate vs reducing-balance interest
            4. Affordability (largest loan / term needed)
            5. Early-settlement calculator
            6. Saved scenarios (save / list / compare)
            0. Exit
            
            """


def prompt_text(message: str) -> str:
    """Read stripped input from stdin, exiting cleanly on EOF."""
    try:
        return input(message).strip()
    except EOFError:
        print("\nInput closed. Goodbye!")
        sys.exit(0)


def prompt_number(
    message: str,
    low: float,
    high: float | None = None,
    allow_low: bool = False,
) -> float:
    """Prompt repeatedly until a valid float within bounds is entered."""
    while True:
        raw = prompt_text(message).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a valid number.")
            continue

        is_too_low = value < low if allow_low else value <= low
        if is_too_low:
            bound_label = "at least" if allow_low else "greater than"
            print(f"  Value must be {bound_label} {low:,}.")
        elif high is not None and value > high:
            print(f"  Value must be {high:,} or less.")
        else:
            return value


def prompt_yes_no(message: str) -> bool:

    """Prompt for a yes/no response."""

    return prompt_text(f"{message} (y/n): ").lower().startswith("y")


def prompt_amount() -> float:
    return prompt_number("Loan amount: ", 0)


def prompt_rate() -> float:
    return prompt_number(
        f"Annual interest rate (%) [0-{MAX_RATE:.0f}]: ",
        0,
        MAX_RATE,
        allow_low=True,
    )


def prompt_term_months() -> int:
    
    """Prompt for term in years or months and return whole months."""
    
    while True:
        unit = prompt_text("Enter term in (Y)ears or (M)onths? [Y/M]: ").lower()
        if unit in ("y", "m"):
            break
        print("  Please type Y or M.")

    while True:
        if unit == "y":
            years = prompt_number("Term (years): ", 0)
            months = round(years * 12)
        else:
            raw_months = prompt_number("Term (months): ", 0)
            months = round(raw_months)

        if months < 1:
            print("  The term must be at least 1 month.")
        elif months > MAX_MONTHS:
            print(
                f"  The term can be at most {MAX_MONTHS} months "
                f"({MAX_MONTHS // 12} years)."
            )
        else:
            return months


def prompt_loan_inputs() -> tuple[float, float, int]:
    return prompt_amount(), prompt_rate(), prompt_term_months()


def print_loan_summary(loan: dict) -> None:
    payment, final_payment, total_repaid, total_interest = calculate_schedule_quote(
        loan["schedule"]
    )
    print()
    print(f"Monthly payment: {format_currency(payment)}")
    if final_payment != payment:
        print(f"Final payment:   {format_currency(final_payment)}")
    print(f"Total repaid:    {format_currency(total_repaid)}")
    print(f"Total interest:  {format_currency(total_interest)}")


def print_schedule_table(schedule: list[dict], limit: int | None = None) -> None:
    rows = schedule if limit is None else schedule[:limit]
    print()
    print(
        f"{'Month':>5} {'Payment':>14} {'Interest':>14} "
        f"{'Principal':>14} {'Balance':>16}"
    )
    print("-" * 67)
    for row in rows:
        print(
            f"{row['month']:>5} {format_currency(row['payment']):>14} "
            f"{format_currency(row['interest']):>14} "
            f"{format_currency(row['principal']):>14} "
            f"{format_currency(row['balance']):>16}"
        )
    if limit is not None and len(schedule) > limit:
        print(f"... ({len(schedule) - limit} more months not shown)")


def print_balance_chart(loan: dict, width: int = 40, points: int = 12) -> None:
    """Render an ASCII bar chart showing remaining principal over time."""
    schedule = loan["schedule"]
    total_months = len(schedule)
    if total_months == 0 or loan["amount"] <= 0:
        return

    steps = min(points, total_months)
    sampled_months = sorted(
        {round(i * total_months / steps) for i in range(1, steps + 1)}
    )
    unit_value = format_currency(loan["amount"] / width)

    print(f"\n  Balance over time (each # = {unit_value})")
    print(f"  {'Month':>5} | balance")
    print(f"  {0:>5} | {'#' * width} {format_currency(loan['amount'])}")
    for month_num in sampled_months:
        balance = schedule[month_num - 1]["balance"]
        bar_len = round(balance / loan["amount"] * width)
        print(f"  {month_num:>5} | {'#' * bar_len} {format_currency(balance)}")


def print_comparison_table(options: list[tuple[str, dict]]) -> None:
    """Display side-by-side totals for multiple `(label, loan)` pairs."""
    computed = []
    for name, loan in options:
        payment, final_payment, total_repaid, total_interest = calculate_schedule_quote(
            loan["schedule"]
        )
        computed.append((name, loan, payment, final_payment, total_repaid, total_interest))

    lowest_interest = min(item[-1] for item in computed)
    print()
    print(
        f"{'Option':<16}{'Amount':>14}{'Rate %':>8}{'Term':>12}"
        f"{'Monthly':>14}{'Final payment':>16}{'Total repaid':>17}{'Interest':>15}"
    )
    print("-" * 112)
    for name, loan, payment, final_payment, total_repaid, total_interest in computed:
        schedule = loan["schedule"]
        payoff_note = ""
        if (
            schedule
            and schedule[-1]["balance"] == 0
            and schedule[-1]["month"] < loan["months"]
        ):
            payoff_note = f"  (paid off in month {schedule[-1]['month']})"
        marker = (
            "  <- lowest interest"
            if total_interest == lowest_interest and len(computed) > 1
            else ""
        )
        print(
            f"{name[:15]:<16}{format_currency(loan['amount']):>14}"
            f"{loan['annual_rate']:>8.2f}{format_term(loan['months']):>12}"
            f"{format_currency(payment):>14}{format_currency(final_payment):>16}"
            f"{format_currency(total_repaid):>17}"
            f"{format_currency(total_interest):>15}{marker}{payoff_note}"
        )


def handle_early_settlement(loan: dict) -> None:
    total_months = len(loan["schedule"])
    target_month = int(
        prompt_number(
            f"Settle after which month? (0-{total_months}): ",
            0,
            total_months,
            allow_low=True,
        )
    )
    settlement = calculate_early_settlement(loan, target_month)
    print(f"\nTo clear the loan after payment {settlement['month']}:")
    print(f"  Settlement amount:    {format_currency(settlement['settlement'])}")
    print(f"  Paid so far:          {format_currency(settlement['paid_so_far'])}")
    print(f"  Interest paid so far: {format_currency(settlement['interest_paid'])}")
    print(f"  Interest saved:       {format_currency(settlement['interest_saved'])}")


def print_incomplete_payoff(error: IncompletePayoffError) -> None:
    if error.months == 0:
        print("The payment does not reduce the balance after rounding.")
    else:
        print(f"The loan is not repaid after {error.months:,} months.")
    print(f"Remaining balance: {format_currency(error.balance)}")


def handle_new_loan() -> None:
    amount, rate, months = prompt_loan_inputs()
    loan = create_loan(amount, rate, months)
    print_loan_summary(loan)
    print("\nRepayment schedule (first 12 months):")
    print_schedule_table(loan["schedule"], limit=12)

    saved_path = save_summary_text(loan)
    print(f"\n(Summary saved to {saved_path})")

    if prompt_yes_no("\nSave the FULL schedule to a CSV file?"):
        print("Saved:", save_schedule_csv(loan))

    if prompt_yes_no("Try an extra monthly payment?"):
        extra = prompt_number("Extra amount per month: ", 0)
        print(f"\nWith {format_currency(extra)} extra each month:")
        try:
            impact = evaluate_extra_payment(loan, extra)
        except IncompletePayoffError as error:
            print_incomplete_payoff(error)
        else:
            print(
                f"  Loan repaid in {impact['new_months']} months "
                f"({impact['months_saved']} months sooner)"
            )
            print(f"  Interest saved: {format_currency(impact['interest_saved'])}")

    if prompt_yes_no("Check an early settlement amount?"):
        handle_early_settlement(loan)

    if prompt_yes_no("Show a balance chart?"):
        print_balance_chart(loan)

    scenario_name = prompt_text(
        "Save as a named scenario? (type a name, or press Enter to skip): "
    )
    if scenario_name:
        save_scenario(scenario_name, amount, rate, months)
        print(f"Scenario '{scenario_name}' saved.")


def handle_early_settlement_menu() -> None:
    amount, rate, months = prompt_loan_inputs()
    handle_early_settlement(create_loan(amount, rate, months))


def handle_compare_options() -> None:
    count = int(
        prompt_number(
            "How many options to compare (2 or 3)? ", 2, 3, allow_low=True
        )
    )
    amount = prompt_amount()
    options: list[tuple[str, dict]] = []

    for index in range(1, count + 1):
        print(f"\n--- Option {index} ---")
        rate = prompt_rate()
        months = prompt_term_months()
        options.append((f"Option {index}", create_loan(amount, rate, months)))

    print_comparison_table(options)
    for _, loan in options:
        save_summary_text(loan)
    print(f"\n(Summaries saved to {DEFAULT_SUMMARY_FILE})")


def handle_flat_vs_reducing() -> None:
    amount, rate, months = prompt_loan_inputs()
    loan = create_loan(amount, rate, months)
    red_payment, red_final, red_total, red_interest = calculate_schedule_quote(
        loan["schedule"]
    )
    flat = calculate_flat_rate_loan(amount, rate, months)
    equiv_rate = find_equivalent_reducing_rate(amount, flat["payment"], months)

    print(
        f"\n{'':<22}{'Reducing balance':>18}{'Flat rate':>18}"
    )
    print(
        f"{'Monthly payment':<22}{format_currency(red_payment):>18}"
        f"{format_currency(flat['payment']):>18}"
    )
    if red_final != red_payment:
        print(f"{'Final payment':<22}{format_currency(red_final):>18}{'—':>18}")
    print(
        f"{'Total repaid':<22}{format_currency(red_total):>18}"
        f"{format_currency(flat['total']):>18}"
    )
    print(
        f"{'Total interest':<22}{format_currency(red_interest):>18}"
        f"{format_currency(flat['interest']):>18}"
    )

    extra_cost = round(flat["interest"] - red_interest, 2)
    print(f"\nThe flat-rate loan costs {format_currency(extra_cost)} more in interest.")
    print(
        "Why: with a reducing balance, interest is charged only on what you "
        "still owe, which shrinks every month. With a flat rate, interest is "
        "charged on the ORIGINAL amount for the entire term."
    )
    print(
        f"A flat rate of {rate:.2f}% is roughly equivalent to a reducing-balance "
        f"rate of {equiv_rate:.2f}%."
    )


def handle_affordability() -> None:
    print("\n1) Largest loan I can afford (given payment, rate and term)")
    print("2) Term needed to repay a loan (given payment and rate)")
    choice = prompt_text("Choose 1 or 2: ")

    if choice == "1":
        payment = prompt_number("Maximum monthly payment: ", 0)
        rate = prompt_rate()
        months = prompt_term_months()
        max_principal = calculate_max_loan_for_payment(payment, rate, months)
        print(
            f"\nLargest loan: {format_currency(max_principal)} over "
            f"{format_term(months)} at {rate:.2f}%"
        )
    elif choice == "2":
        amount = prompt_amount()
        rate = prompt_rate()
        payment = prompt_number("Monthly payment you will pay: ", 0)
        try:
            schedule = build_payoff_schedule(amount, rate, payment)
        except IncompletePayoffError as error:
            print()
            print_incomplete_payoff(error)
        else:
            total_repaid, total_interest = calculate_schedule_totals(schedule)
            print(
                f"\nTime needed: {len(schedule)} months "
                f"({format_term(len(schedule))})"
            )
            print(f"Total repaid:   {format_currency(total_repaid)}")
            print(f"Total interest: {format_currency(total_interest)}")
    else:
        print("Invalid choice.")


def handle_scenarios() -> None:
    print("\n1) Save a new scenario")
    print("2) List saved scenarios")
    print("3) Compare saved scenarios (table + balance charts)")
    choice = prompt_text("Choose 1-3: ")

    if choice == "1":
        name = prompt_text("Scenario name: ")
        if not name:
            print("A name is required.")
            return
        amount, rate, months = prompt_loan_inputs()
        save_scenario(name, amount, rate, months)
        print(f"Scenario '{name}' saved.")
    elif choice in ("2", "3"):
        scenarios = load_scenarios()
        if not scenarios:
            print("No saved scenarios yet.")
            return

        print("\nSaved scenarios:")
        for name, item in scenarios.items():
            print(
                f"  {name}: {format_currency(item['amount'])} at "
                f"{item['annual_rate']}% for {format_term(item['months'])}"
            )

        if choice == "3":
            raw_names = prompt_text(
                "\nNames to compare, separated by commas (Enter = all): "
            )
            selected = [n.strip() for n in raw_names.split(",") if n.strip()] or list(
                scenarios
            )
            options: list[tuple[str, dict]] = []
            for name in selected:
                if name not in scenarios:
                    print(f"  '{name}' not found, skipped.")
                    continue
                item = scenarios[name]
                options.append(
                    (
                        name,
                        create_loan(
                            item["amount"], item["annual_rate"], item["months"]
                        ),
                    )
                )

            if len(options) < 2:
                print("Need at least two valid scenarios to compare.")
                return

            print_comparison_table(options)
            for name, loan in options:
                print(f"\n[{name}]")
                print_balance_chart(loan)
    else:
        print("Invalid choice.")


MENU_ACTIONS = {
    "1": handle_new_loan,
    "2": handle_compare_options,
    "3": handle_flat_vs_reducing,
    "4": handle_affordability,
    "5": handle_early_settlement_menu,
    "6": handle_scenarios,
}


def run_cli() -> None:
    """Run the interactive loan calculator loop."""
    while True:
        print(MAIN_MENU)
        choice = prompt_text("Choose an option: ")
        if choice == "0":
            print("Goodbye!")
            return

        action = MENU_ACTIONS.get(choice)
        if action is None:
            print("Please choose a number from the menu.")
            continue

        while True:
            action()
            if not prompt_yes_no("\nCalculate another?"):
                break