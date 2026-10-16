# Release check: business questions with known answers

## What this is for

A release gate. Before every FAC release, a fixed set of business questions
is put to the assistant on two test sites, and each answer is scored against
the number the site's own data gives. The owner requires it because unit tests
mock the boundaries the assistant crosses; only real questions against real
reports and documents show whether "report-first" answering works.

This directory holds the inputs (site setup scripts, `questions.json`, `expected.py`), the
runner (`run.py`) and the comparison (`compare.py`); scoring lives in `scoring.py`.

## The two sites

| Site | Purpose | Contents |
| --- | --- | --- |
| `realistic` | Human-shaped business data | ERPNext demo company, recently dated invoices, a UI-style Query Report "Sales Performance by Region", a custom DocType "Booking" (Customer, Date, Amount; 60 submitted rows), supplier "RC Vendor Alpha" with 3 paid purchase invoices, stock item "RC Widget" |
| `large` | Volume | at least 200,000 GL Entry rows and 20,000 submitted Sales Invoices, so Accounts Receivable / General Ledger / Stock Balance exceed the prepared-report threshold |

## Building the sites

Both need Frappe and ERPNext (v15 or v16). Run the setup scripts with the
bench's Python from `<bench>/sites` (they connect with `frappe.init`; from
`<bench>` also works, `--sites-path` overrides).

**Step 1, per site: create it and complete the setup wizard.** The scripts need
a default company and fiscal year, and fail without them. Headless (derived from
`frappe.utils.install.complete_setup_wizard` and the keys ERPNext's setup stages
read; replace 2026 with the current year; untested here, adjust if your version asks
for more):

```bash
cd <bench>
bench new-site realistic.test --admin-password admin --install-app erpnext
bench --site realistic.test install-app frappe_assistant_core
bench --site realistic.test execute frappe.desk.page.setup_wizard.setup_wizard.setup_complete --kwargs \
  "{'args': {'language': 'English', 'country': 'United States', 'timezone': 'America/New_York', \
  'currency': 'USD', 'full_name': 'Release Check', 'email': 'rc@example.com', 'password': 'admin', \
  'company_name': 'RC Test Co', 'company_abbr': 'RTC', 'chart_of_accounts': 'Standard', \
  'fy_start_date': '2026-01-01', 'fy_end_date': '2026-12-31', 'bank_account': 'Bank Account'}}"
```

(Or open the site in a browser and finish the wizard by hand.) Repeat with
`large.test` for the second site.

**Mark each site as a release-check site.** The setup scripts add an ERPNext demo company and,
on the large site, 200,000 ledger rows, so they refuse any site that does not opt in:

```bash
bench --site realistic.test set-config release_check_site 1
bench --site large.test set-config release_check_site 1
```

`--dry-run` skips this check because it touches nothing.

**Step 2: run the setup script.**

```bash
cd <bench>/sites
../env/bin/python <fac-repo>/scripts/release_check/setup_realistic_site.py --site realistic.test
../env/bin/python <fac-repo>/scripts/release_check/setup_large_site.py --site large.test
```

Not through `bench execute` or `bench console`: the scripts are not an
importable app module.

Options on both scripts:

* `--dry-run` prints the plan and touches nothing (no site needed).
* `--scale 0.01` runs the large site at 1% (about 200 invoices, 2,000 GL rows)
  for a smoke test.
* `--sites-path` (default `$FRAPPE_SITES_PATH`, else the current directory if it holds the site, else `./sites`).

Both are idempotent and resumable: every step counts what exists (documents
are tagged in `remarks`; Payment Entries also set `custom_remarks`, or ERPNext overwrites the tag) and creates only the shortfall. Re-running the
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

Scoring definitions: sales questions are **net sales before tax**
(`base_net_total`; the wording says so, because a company default tax template makes grand total
differ). Receivable questions are the **customer party-ledger balance as on today**
(GL debit minus credit on Receivable accounts, Customer party, posting date up to today),
which is what Accounts Receivable totals. The age of the debt is not scored: the
question asks only for the total (`receivables_ageing` keeps its id).

`cite` lists the reports or doctypes whose use counts as answering the way we
want (report-first); the runner scores whether the tool calls used one of them.

Validate without a site (pure Python):

```bash
python scripts/release_check/validate.py
python -m unittest discover -s scripts/release_check -p "test_*.py"
```

Importing `expected` needs `scripts/release_check` on `sys.path` and a bench
Python with Frappe installed.

## Running the check

One run asks every question of one site's profile through FAC Chat with one fixed model and
writes a results file. Use the same model every time, or the comparison measures the model.

```bash
cd <bench>/sites
export RELEASE_CHECK_API_KEY=<key> RELEASE_CHECK_API_SECRET=<secret>   # a chat-enabled user's API keys
../env/bin/python <fac-repo>/scripts/release_check/run.py --site realistic.test --profile realistic \
    --url http://localhost:8000 --ar-site <cloud-site> --model <model_id> --out <fac-repo>/scripts/release_check/results/<version>.json
../env/bin/python <fac-repo>/scripts/release_check/run.py --site large.test --profile large \
    --url http://localhost:8001 --model <model_id> --out <fac-repo>/scripts/release_check/results/<version>-large.json
```

`--dry-run` prints the questions, model and output path without connecting.

Why HTTP for the questions: `send_message` hands the turn to a background relay that streams the
reply over Socket.IO and saves it afterwards. Posting to the running web workers exercises exactly
the path the SPA uses; the script then polls `get_session_history` for the assistant reply (up to
`--timeout`, 300 s). Turns are sent with `client_type=spa`, what the SPA sends, so they get the tool profile a customer's chat gets (a custom client type would get AR's fail-safe profile instead). The script
connects to `--site` in-process only to compute the expected answers (`expected.py`). `AR Turn Usage`
lives on the FAC Cloud (assistant_runtime) site, not on these test sites: pass `--ar-site <that site>`
(same bench) and the script sums the turn's rows by session id; the runner creates every session fresh, so that identifies the turn.
Without `--ar-site`, `tool_calls`, `credits` and `input_tokens` are `null`.

Each result: `id`, `session_id`, `answer`, `correct`, `cited`, `tool_calls`, `credits`, `input_tokens`
(the last three are `null` without `--ar-site`), `wall_seconds`, `blocked_over_60s` (over 60 s),
`errored`, `aborted`, `timed_out` and `error` (a failed request or scoring error is recorded, the run
continues, and the file is rewritten after every question). An errored, aborted, timed-out or empty
turn is never scored correct. The reply wait ends early when the turn errored or was aborted.

Scoring (`scoring.py`): `total` is correct when any number in the answer is within 0.5% of the
expected total (supports `1,234,567`, Indian grouping `₹1,23,456.78`, `1.2M`, `1.2 million`,
`12 lakh`, `1.5 crore`, `350K`, `2 billion`); `top_n` when every expected name appears;
`mentions` when every term (or one of its alternatives) appears. Matching is case-insensitive.
Names and numbers match as whole tokens ("ABC" is not in "ABCD"), and numeric `mentions`
alternatives are compared as numbers, exactly ("1,000.00" is not in "11,000.00"). `cited` is true
when any `cite` name appears as a whole phrase in the answer or in a tool call's name or input;
tool results never count.

## Comparing releases

```bash
python scripts/release_check/compare.py results/<old>.json results/<new>.json
```

Prints a per-question table and exits 1 when any question went correct to incorrect (a question
missing from the new file counts as a regression).

## Creating the first baseline

No baseline is committed. The owner creates it once on a release candidate: build both sites,
run the two commands above with the chosen model, review the answers by hand (a wrong `correct`
verdict from a scoring edge is a fix to `scoring.py`, not to the file), then commit the files under
`scripts/release_check/results/`. Later releases are compared against the latest committed one.
