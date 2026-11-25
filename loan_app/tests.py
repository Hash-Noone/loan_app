"""Unit tests for loan amortisation, flat rate, affordability, and settlement."""

import csv
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from functools import partial
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from calculations import (
    IncompletePayoffError,
    build_payoff_schedule,
    build_schedule,
    calculate_early_settlement,
    calculate_exact_payment,
    calculate_flat_rate_loan,
    calculate_formula_totals,
    calculate_max_loan_for_payment,
    calculate_monthly_payment,
    calculate_months_needed,
    evaluate_extra_payment,
)
from cli import handle_affordability, handle_new_loan
from models import create_loan
from storage import save_schedule_csv, save_summary_text


class LoanCalculatorTests(unittest.TestCase):
    
    def test_example_loan_totals(self):
        payment, total, interest = calculate_formula_totals(1_000_000, 12, 24)
        self.assertAlmostEqual(payment, 47073.47, delta=0.01)
        self.assertAlmostEqual(total, 1129763.33, delta=0.01)
        self.assertAlmostEqual(interest, 129763.33, delta=0.01)

    def test_standard_mortgage_payments(self):
        self.assertAlmostEqual(calculate_monthly_payment(100_000, 6, 360), 599.55, delta=0.01)
        self.assertAlmostEqual(calculate_monthly_payment(200_000, 4.5, 360), 1013.37, delta=0.01)
        self.assertAlmostEqual(calculate_monthly_payment(100_000, 5, 180), 790.79, delta=0.01)

    def test_zero_interest_rate(self):
        self.assertAlmostEqual(calculate_monthly_payment(12_000, 0, 12), 1000.00, delta=0.01)

    def test_schedule_ends_at_zero_and_sums_principal(self):
        cases = [
            (1_000_000, 12, 24),
            (123_456.78, 7.3, 37),
            (5_000, 0, 7),
            (999_999.99, 25, 360),
            (100, 1, 1),
        ]
        for amount, rate, months in cases:
            with self.subTest(amount=amount, rate=rate, months=months):
                schedule = build_schedule(amount, rate, months)
                self.assertEqual(schedule[-1]["balance"], 0)

        schedule = build_schedule(250_000, 3.5, 360)
        self.assertAlmostEqual(sum(r["principal"] for r in schedule), 250_000, delta=0.01)
        self.assertEqual(len(schedule), 360)

    def test_flat_rate_loan(self):
        flat = calculate_flat_rate_loan(100_000, 10, 24)
        self.assertAlmostEqual(flat["interest"], 20_000, delta=0.01)
        self.assertAlmostEqual(flat["payment"], 5_000, delta=0.01)
        reducing_interest = calculate_formula_totals(100_000, 10, 24)[2]
        self.assertGreater(flat["interest"], reducing_interest)

    def test_affordability_inverses_and_unrepayable(self):
        exact_pmt = calculate_exact_payment(300_000, 8, 240)
        self.assertEqual(calculate_max_loan_for_payment(exact_pmt, 8, 240), 300_000.02)
        self.assertEqual(calculate_months_needed(300_000, 8, exact_pmt), 240)
        self.assertIsNone(calculate_months_needed(100_000, 12, 500))

    def test_payoff_term_respects_cent_rounded_budget(self):
        schedule = build_payoff_schedule(100_000, 6, 500.01)
        self.assertEqual(calculate_months_needed(100_000, 6, 500.01), 2185)
        self.assertEqual(len(schedule), 2185)
        self.assertLessEqual(max(row["payment"] for row in schedule), 500.01)
        self.assertEqual(schedule[-1]["payment"], 335.02)
        self.assertEqual(schedule[-1]["balance"], 0)
        self.assertIsNone(calculate_months_needed(3.70, 12, 0.04))

    def test_maximum_loan_clears_on_budget_and_next_cent_does_not(self):
        amount = calculate_max_loan_for_payment(599.55, 6, 360)
        self.assertEqual(amount, 99_999.87)
        schedule = build_schedule(amount, 6, 360, payment_override=599.55)
        self.assertEqual(len(schedule), 360)
        self.assertLessEqual(max(row["payment"] for row in schedule), 599.55)
        self.assertEqual(schedule[-1]["balance"], 0)
        larger = build_schedule(99_999.88, 6, 360, payment_override=599.55)
        self.assertEqual(larger[-1]["balance"], 0.05)

    def test_long_and_incomplete_affordability_terms(self):
        self.assertEqual(calculate_months_needed(10_000, 0, 1), 10_000)
        with self.assertRaises(IncompletePayoffError) as caught:
            calculate_months_needed(10_001, 0, 1)
        self.assertEqual((caught.exception.months, caught.exception.balance), (10_000, 1))

        output = StringIO()
        with (
            patch("builtins.input", side_effect=["2", "10001", "0", "1"]),
            redirect_stdout(output),
        ):
            handle_affordability()
        self.assertIn("not repaid after 10,000 months", output.getvalue())
        self.assertIn("Remaining balance: 1.00", output.getvalue())
        self.assertNotIn("Time needed", output.getvalue())

    def test_extra_payments_reduce_term_and_interest(self):
        
        loan = create_loan(500_000, 10, 120)
        impact = evaluate_extra_payment(loan, 5_000)
        self.assertGreater(impact["months_saved"], 0)
        self.assertGreater(impact["interest_saved"], 0)
        self.assertEqual(impact["schedule"][-1]["balance"], 0)

    def test_extra_payment_without_progress_is_not_reported_as_paid(self):
        output = StringIO()
        inputs = ["2", "0", "m", "600", "n", "y", "0.001", "n", "n", ""]
        with (
            patch("builtins.input", side_effect=inputs),
            patch("cli.save_summary_text"),
            redirect_stdout(output),
        ):
            handle_new_loan()
        self.assertIn("Remaining balance: 2.00", output.getvalue())
        self.assertNotIn("Loan repaid in", output.getvalue())
        self.assertNotIn("Interest saved", output.getvalue())

    def test_balloon_payment_quote_agrees_with_text_summary_and_csv(self):
        output = StringIO()
        inputs = ["100000", "100", "m", "600", "y", "n", "n", "n", ""]
        with TemporaryDirectory() as folder:
            csv_path = Path(folder) / "schedule.csv"
            summary_path = Path(folder) / "summary.txt"
            with (
                patch("builtins.input", side_effect=inputs),
                patch("cli.save_schedule_csv", partial(save_schedule_csv, filename=csv_path)),
                patch("cli.save_summary_text", partial(save_summary_text, filename=summary_path)),
                redirect_stdout(output),
            ):
                handle_new_loan()
            with csv_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            summary = summary_path.read_text()

        self.assertEqual(len(rows), 600)
        self.assertEqual(rows[0]["Payment"], "8333.33")
        self.assertEqual(rows[0]["Principal"], "0.00")
        self.assertEqual(rows[-1]["Payment"], "108333.33")
        self.assertEqual(rows[-1]["Balance"], "0.00")
        self.assertEqual(sum(Decimal(row["Payment"]) for row in rows), Decimal("5099998.00"))
        self.assertEqual(sum(Decimal(row["Interest"]) for row in rows), Decimal("4999998.00"))
        for quote in (output.getvalue(), summary):
            self.assertIn("8,333.33", quote)
            self.assertIn("108,333.33", quote)
            self.assertIn("5,099,998.00", quote)
            self.assertIn("4,999,998.00", quote)

    def test_early_settlement(self):
        loan = create_loan(500_000, 10, 120)
        self.assertAlmostEqual(
            calculate_early_settlement(loan, 0)["settlement"], 500_000, delta=0.01
        )
        self.assertEqual(calculate_early_settlement(loan, 120)["settlement"], 0)
        self.assertAlmostEqual(
            calculate_early_settlement(loan, 60)["settlement"],
            loan["schedule"][59]["balance"],
            delta=0.01,
        )


if __name__ == "__main__": unittest.main()