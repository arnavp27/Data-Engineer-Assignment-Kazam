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

I added these checks to make sure the files loaded properly and to flag records that could affect the session count:

- **Import counts:** I compared CSV and database row counts to catch rows missed during loading. I also checked for empty files.
- **Required fields and timestamps:** I checked for transaction IDs, charger IDs and start times, and checked timestamp formats. These are needed to identify each record and assign it to a charger and day.
- **Possible duplicates:** I checked for repeated transaction IDs and identical details under different IDs. I found 33 sets of matching records, containing 75 rows. These could be duplicates or separate failed attempts, like someone trying to charge three times and failing each time, so I flagged them and kept the rows pending clarification.
- **End times:** I found 551 missing end times and 1,429 end times before their starts. I flagged these but counted the records by their start date, since the task doesn't specify only completed or successful sessions.
- **Payment references:** I checked for payments without a matching transaction to catch missing references between the two files. This doesn't require every transaction to have a payment.
- **Summary totals and reruns:** I checked that the summary's session counts add up to the transaction row count, and that running the pipeline twice didn't increase the counts.

With the supplied files, I loaded **200,000 transactions and 196,266 payment rows**. The summary has **32,916 charger/day rows**, adding up to **200,000 counted sessions**.

For empty inputs, missing required fields, repeated transaction IDs or invalid start formats, the current code keeps the raw import but leaves any previous summary unchanged. Import errors or count mismatches roll back the run.

I would confirm the status meanings and measurement units before adding checks based on them, as those definitions weren't supplied.

## With more time

Right now, I have used a full refresh of both raw tables. Each run replaces their contents with all the rows from the CSVs, then rebuilds the daily summary if validation passes. I chose this because the supplied CSVs are small enough to reload, and it keeps reruns simple while picking up changes to existing rows. For larger files updated regularly, I'd add incremental loading to process new and changed records without counting them twice. I'd need a reliable way to track updates, since these files don't have a last-updated field.

I'd also add reusable tests, validate CSV headers, and confirm the status definitions and measurement units.

## Task 2

[Google Sheet](https://docs.google.com/spreadsheets/d/18j9lEKvf9iJn6ZPxDh1GOfGdid6llalvQHzahzI0iBo/edit?gid=247387524#gid=247387524)
