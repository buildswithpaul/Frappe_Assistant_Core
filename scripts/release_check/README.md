# Release check: business questions with known answers

## What this is for

A release gate. Before every FAC release, a fixed set of business questions
is put to the assistant on two test sites, and each answer is scored against
the number the site's own data gives. The owner requires it because unit tests
mock the boundaries the assistant crosses; only real questions against real
reports and documents show whether "report-first" answering works.

The runner and scoring are **Task 7** and come next. This directory holds the
inputs: the site setup scripts, `questions.json` and `expected.py`.

## The two sites

| Site | Purpose | Contents |
| --- | --- | --- |
| `realistic` | Human-shaped business data | ERPNext demo company, recently dated invoices, a UI-style Query Report "Sales Performance by Region", a custom DocType "Booking" (Customer, Date, Amount; 60 submitted rows), supplier "RC Vendor Alpha" with 3 paid purchase invoices, stock item "RC Widget" |
| `large` | Volume | at least 200,000 GL Entry rows and 20,000 submitted Sales Invoices, so Accounts Receivable / General Ledger / Stock Balance exceed the prepared-report threshold |

## Building the sites

Both need Frappe and ERPNext (v15 or v16). Build them under any bench; the
setup scripts connect with `frappe.init`, so run them with the bench's Python
from its `sites` directory.

```bash
cd <bench>

# realistic site
bench new-site realistic.test --admin-password admin --install-app erpnext
cd sites
../env/bin/python <fac-repo>/scripts/release_check/setup_realistic_site.py --site realistic.test
cd ..
bench --site realistic.test install-app frappe_assistant_core

# large site
bench new-site large.test --admin-password admin --install-app erpnext
bench --site large.test install-app frappe_assistant_core
cd sites
../env/bin/python <fac-repo>/scripts/release_check/setup_large_site.py --site large.test
```

Complete the ERPNext setup wizard on each site first (company, chart of
accounts, fiscal year); the scripts need a default company. Run the scripts
by the command lines above (not through `bench execute` or `bench console`,
since they are not an importable app module).

Options on both scripts:

* `--dry-run` prints the plan and touches nothing (no site needed).
* `--scale 0.01` runs the large site at 1% (about 200 invoices, 2,000 GL rows)
  for a smoke test.
* `--sites-path` (default `./sites`, or `$FRAPPE_SITES_PATH`).

Both are idempotent and resumable: every step counts what exists (documents
are tagged in `remarks`) and creates only the shortfall. Re-running the
realistic script on release day refreshes the "last month" and "this month"
data, which the questions depend on. The large script commits every 200
documents, so an interrupted run resumes where it stopped.

### Expected build time

* realistic: 5-10 minutes (the ERPNext demo data dominates).
* large at scale 1.0: roughly 3-6 hours, **an estimate, not a measurement**
  (about 0.3-0.5 s per submitted invoice, 1 s per payment, 2-3 s per wide
  Journal Entry). Run `--scale 0.01` first, time it and multiply by 100.

Real submitted documents are generated, so GL Entry and Stock Ledger Entry are
written by ERPNext on submit exactly as in production. The ledger is topped up
to 200,000 rows with wide Journal Entries (one debit per customer). The script
also sets `prepared_report` on Accounts Receivable, General Ledger and Stock
Balance; Frappe flips that on by itself after a 15 second run, so this just
makes the outcome independent of machine speed.

## The question set

`questions.json` is a list of:

```json
{"id": "...", "site": "realistic|large", "question": "...",
 "expect": {"kind": "total|top_n|mentions", "source": "<function in expected.py>"},
 "cite": ["acceptable report or doctype names"]}
```

`expected.py` functions take no arguments, run inside a connected site, and
compute the answer from the data with `frappe.get_list` at call time, never a
hand-typed number. Return shapes:

* `total`: a float.
* `top_n`: `[(name, value), ...]`, best first, ties broken by name.
* `mentions`: strings the answer must contain; an element that is a list is a
  set of alternatives, any one of which satisfies it.

`cite` lists the reports or doctypes whose use counts as answering the way we
want (report-first); the runner scores whether the tool calls used one of them.

Validate without a site (pure Python):

```bash
python scripts/release_check/validate.py
python -m unittest discover -s scripts/release_check -p "test_*.py"
```

Importing `expected` needs `scripts/release_check` on `sys.path` and a bench
Python with Frappe installed.
