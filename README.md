# Kazam Data Engineer Assignment

I used Python and PostgreSQL to load both CSVs and build `charger_daily_sessions`: one row per charger per day.

## Run

Requires Python 3.10+ and Docker Compose. Keep these files beside `pipeline.py`:

- `Data for Task - Txns.csv`
- `Data for Task - Pymts.csv`

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d
docker compose exec postgres pg_isready -U kazam_user -d kazam_assignment
```

Once PostgreSQL reports `accepting connections`, run:

```bash
python pipeline.py
python pipeline.py
```

Run twice and confirm the printed counts stay the same. PostgreSQL 18 uses `127.0.0.1:5432` with no password for this local exercise. Prefix Docker commands with `sudo` if needed.

## Approach and assumptions

- One transaction row represents one session; transaction IDs must be unique. `device_id` identifies the charger.
- Timestamps are integer Unix seconds. Sessions count on their start date in `Asia/Kolkata` (GMT+05:30), including sessions crossing midnight.
- All transaction statuses are included. Payments are loaded but not joined into session counts.
- Raw columns stay as text. The loader expects the supplied CSV column order.
- Both supplied CSV extracts are expected to contain data.
- Each run replaces the raw imports. Successful validation rebuilds the summary, preventing copies from accumulating across runs.

## Checks and results

Checks cover CSV/database row counts, empty inputs, required fields, duplicate transaction IDs, matching session details under different IDs, timestamp format and order, payment references, and the summary's session total.

Empty extracts, missing required transaction fields, duplicate IDs or invalid start formats skip aggregation. The raw import is kept; any previous summary is not refreshed. Import failures or count mismatches roll back the run.

With the supplied files:

- 200,000 transactions and 196,266 payment rows loaded.
- 32,916 charger/day rows, totalling 200,000 sessions. Counts stayed unchanged across runs.
- 551 missing end times and 1,429 end times before their starts. These records remain in the count using their recorded start date.
- 33 groups (75 rows) match in every field except transaction ID. These are flagged as possible duplicate sessions and kept pending clarification. IDs are not altered.

Status definitions and measurement units were not supplied.

## With more time

I'd add reusable tests, validate CSV headers, and confirm the status definitions and measurement units.

## Task 2

[Google Sheet](https://docs.google.com/spreadsheets/d/18j9lEKvf9iJn6ZPxDh1GOfGdid6llalvQHzahzI0iBo/edit?gid=247387524#gid=247387524)
