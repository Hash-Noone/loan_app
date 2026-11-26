# Loan Calculator CLI

A modular, zero-dependency Python command-line application for calculating loan amortisation schedules, comparing financing options, evaluating extra payments, estimating affordability, and managing saved scenarios.

Built strictly with the **Python Standard Library** (`csv`, `json`, `math`, `os`, `sys`, `datetime`, `unittest`) and structured around **Separation of Concerns (SoC)**.

---

## Features

- **Reducing-Balance Loan Calculator:** Computes fixed monthly payments, total repayment, total interest, and a month-by-month amortisation schedule guaranteed to close at a `0.00` balance.

- **Extra Payment Simulator:** Calculates how many months and how much interest you save by adding a fixed extra principal payment each month.

- **Multi-Option Comparison:** Compares 2 to 3 loan offers side-by-side and highlights the lowest-interest option.
- **Flat-Rate vs. Reducing-Balance Analysis:**
Flat rate interest calculates interest on the full original loan amount for the entire duration, while reducing balance interest calculates interest only on the remaining unpaid principal after each payment. Because of this difference, a reducing balance loan is much cheaper than a flat rate loan at the same advertised percentage.Demonstrates the true cost difference between flat-rate and reducing-balance loans and computes the equivalent reducing-balance APR via bisection search.


- **Affordability & Payoff Term Solver:**
  - Finds the maximum principal you can borrow given a monthly budget, rate, and term.
  - Calculates the exact months needed to pay off a target loan at a fixed monthly payment (and warns when a payment fails to cover monthly interest).
- **Early Settlement Calculator:** Determines the exact payoff figure, total paid to date, and interest saved if you settle the loan after any given month.
- **ASCII Balance Visualization:** Renders a terminal bar chart illustrating remaining principal over time.
- **Data Persistence:**
  - Automatically appends loan summaries to `loan_summaries.txt`.
  - Exports full amortisation schedules to `loan_schedule.csv`.
  - Saves, lists, and compares named scenarios in `loan_scenarios.json`.


---

## Project Structure

```text

loan_app/
├── models.py        # Domain constants and loan dictionary factory
├── calculations.py  # Pure financial math (amortisation, flat rate, affordability, settlement)
├── storage.py       # CSV, text summary, and JSON scenario file persistence
├── cli.py           # Terminal input validation, formatting, ASCII charts, and menu flows
├── tests.py         # Unit test suite built with unittest
└── main.py          # Application entry point

```


# Loan Calculator

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | Defines validation bounds (`MAX_RATE`, `MAX_MONTHS`), default output filenames, and `create_loan()`. |
| `calculations.py` | Contains pure functions with no I/O or terminal side effects. Functions are reusable in scripts, APIs, or tests. |
| `storage.py` | Handles reading and writing CSV schedules, text audit logs, and JSON scenario dictionaries. |
| `cli.py` | Manages interactive prompts, input validation, table rendering, ASCII charts, and menu routing. |
| `tests.py` | Verifies formulas, zero-rate edge cases, schedule rounding, affordability inverses, and settlement mathematics. |
| `main.py` | Launches the interactive menu or executes the test suite when passed `--test`. |

## Getting Started

### Prerequisites

- Python 3.10+ (uses modern union type hints such as `float | None`).
- No third-party packages required.

### Running the Application
Navigate into the directory containing `main.py` and run:

```bash
python3 main.py
```

### Running Self-Tests

Run the built-in unit test suite via `main.py` or directly with `unittest`:

```bash
python3 main.py --test

# Or
python3 -m unittest tests.py -v
```

## Usage Overview

When launched, the calculator presents an interactive menu:

```text
==================== LOAN CALCULATOR ====================

1. Calculate a loan (payment, schedule, extras)
2. Compare 2-3 loan options
3. Flat-rate vs reducing-balance interest
4. Affordability (largest loan / term needed)
5. Early-settlement calculator
6. Saved scenarios (save / list / compare)
0. Exit
```

## Generated Output Files

Running calculations and saving scenarios will generate the following files in your working directory:

| File | Description |
|---|---|
| `loan_summaries.txt` | Timestamped log of calculated loans and headline totals. |
| `loan_schedule.csv` | Full month-by-month breakdown (Month, Payment, Interest, Principal, Balance) when exported. |
| `loan_scenarios.json` | Named loan configurations saved for future side-by-side comparisons. |

## Financial Formulas Used

### 1. Reducing-Balance Monthly Payment

$$
M = \frac{P \cdot r}{1 - (1 + r)^{-n}}
$$

This formula is called the loan amortization formula (or equated monthly installment (EMI) formula). It calculates the fixed, regular payment required to completely pay off a loan—covering both principal and interest—over a set period.

- `P` = Principal loan amount.
- `r` = Monthly interest rate.
- `n` = Loan term in months.
- `M` = Monthly repayment.

The monthly interest rate is calculated as:

$$
r = \frac{\text{Annual Rate}}{100 \times 12}
$$

For a zero-interest loan:

$$
M = \frac{P}{n}
$$

### 2. Maximum Affordable Principal

Calculates the maximum loan amount affordable based on a fixed monthly payment:

$$
P_{\max} = \frac{M \cdot (1 - (1 + r)^{-n})}{r}
$$

### 3. Months Required to Repay

Calculates the number of months required to repay a loan based on a fixed monthly payment:

$$
n = \left\lceil
-\frac{\ln(1 - \frac{P \cdot r}{M})}
{\ln(1 + r)}
\right\rceil
$$

This formula applies when:

$$
M > P \cdot r
$$

Where:

- `P` = Principal loan amount.
- `r` = Monthly interest rate.
- `M` = Monthly repayment amount.
- `ceil` = Rounding up to the next whole month.
