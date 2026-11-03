from pathlib import Path
import psycopg
import csv

DATA_DIR = Path(__file__).resolve().parent

def create_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.raw_payments (
            txn_id TEXT,
            status TEXT,
            payment_type TEXT,
            invoice_amount TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.raw_transactions (
            connector_id TEXT,
            device_id TEXT,
            end_reason TEXT,
            end_time TEXT,
            meter_start TEXT,
            meter_stop TEXT,
            org TEXT,
            payment_id TEXT,
            payment_status TEXT,
            soc TEXT,
            start_time TEXT,
            total_capacity TEXT,
            total_usage TEXT,
            txn_id TEXT,
            user_id TEXT,
            zone_id TEXT
        )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS public.charger_daily_sessions (
        charger_id TEXT NOT NULL,
        session_date DATE NOT NULL,
        session_count BIGINT NOT NULL CHECK (session_count > 0),
        PRIMARY KEY (charger_id, session_date)
        )
    """)

def load_csv(cur, filename, copy_query):
    file_path = DATA_DIR / filename

    with file_path.open("rb") as file:
        with cur.copy(copy_query) as copy:
            while True:
                chunk = file.read(1024 * 1024)

                if not chunk:
                    break

                copy.write(chunk)

    print(f"Loaded {filename}")

def check_missing_values(cur):
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE txn_id IS NULL OR TRIM(txn_id) = ''),
            COUNT(*) FILTER (WHERE device_id IS NULL OR TRIM(device_id) = ''),
            COUNT(*) FILTER (WHERE start_time IS NULL OR TRIM(start_time) = ''),
            COUNT(*) FILTER (WHERE end_time IS NULL OR TRIM(end_time) = '')
        FROM public.raw_transactions
    """)

    txn_ids, device_ids, start_times, end_times = cur.fetchone()

    print(f"Missing txn_id: {txn_ids}")
    print(f"Missing device_id: {device_ids}")
    print(f"Missing start_time: {start_times}")
    print(f"Missing end_time: {end_times} (warning only)")
    return txn_ids == 0 and device_ids == 0 and start_times == 0

def check_duplicate_transactions(cur):
    cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT txn_id
            FROM public.raw_transactions
            WHERE txn_id IS NOT NULL AND TRIM(txn_id) <> ''
            GROUP BY txn_id
            HAVING COUNT(*) > 1
        ) AS repeated_ids
    """)

    duplicate_count = cur.fetchone()[0]

    if duplicate_count > 0:
        print(f"WARNING: {duplicate_count} transaction IDs appear more than once")
    else:
        print("PASS: No repeated transaction IDs")

    return duplicate_count == 0

def check_timestamp_format(cur):
    cur.execute("""
        SELECT
            COUNT(*) FILTER (
                WHERE NULLIF(TRIM(start_time), '') !~ '^[0-9]{1,10}$'
            ),
            COUNT(*) FILTER (
                WHERE NULLIF(TRIM(end_time), '') !~ '^[0-9]{1,10}$'
            )
        FROM public.raw_transactions
    """)

    invalid_start, invalid_end = cur.fetchone()

    print(f"Invalid start_time format: {invalid_start}")
    print(f"Invalid end_time format: {invalid_end}")
    return invalid_start == 0

def check_time_order(cur):
    cur.execute("""
        SELECT COUNT(*)
        FROM public.raw_transactions
        WHERE CASE
            WHEN TRIM(start_time) ~ '^[0-9]{1,10}$'
             AND TRIM(end_time) ~ '^[0-9]{1,10}$'
            THEN end_time::BIGINT < start_time::BIGINT
            ELSE FALSE
        END
    """)

    invalid_count = cur.fetchone()[0]

    print(f"Sessions ending before they start: {invalid_count}")

def check_payment_references(cur):
    cur.execute("""
        SELECT COUNT(*)
        FROM public.raw_payments AS p
        WHERE NOT EXISTS (
            SELECT 1
            FROM public.raw_transactions AS t
            WHERE t.txn_id = p.txn_id
        )
    """)

    unmatched_payments = cur.fetchone()[0]

    print(f"Payments without a matching transaction: {unmatched_payments}")


def build_daily_sessions(cur):
    cur.execute("TRUNCATE TABLE public.charger_daily_sessions")

    cur.execute("""
        INSERT INTO public.charger_daily_sessions (
            charger_id, session_date, session_count
        )
        SELECT
            device_id,
            (
                to_timestamp(start_time::DOUBLE PRECISION)
                AT TIME ZONE 'Asia/Kolkata'
            )::DATE,
            COUNT(*)
        FROM public.raw_transactions
        GROUP BY 1, 2
    """)

    print(f"Daily summary rows: {cur.rowcount}")

def check_session_total(cur, transaction_count):
    cur.execute("""
        SELECT COALESCE(SUM(session_count), 0)
        FROM public.charger_daily_sessions
    """)

    summary_total = cur.fetchone()[0]

    if summary_total != transaction_count:
        raise ValueError(
            f"Expected {transaction_count} sessions, "
            f"but the summary contains {summary_total}"
        )

    print(f"PASS: Daily summary contains {summary_total} sessions")


def main():
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname="kazam_assignment",
        user="kazam_user",
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            create_tables(cur)

            # Replace the previous import when we run this again.
            cur.execute("""
                TRUNCATE TABLE
                    public.raw_payments,
                    public.raw_transactions
            """)

            load_csv(cur, "Data for Task - Pymts.csv", """
                COPY public.raw_payments (
                    txn_id,
                    status,
                    payment_type,
                    invoice_amount
                )
                FROM STDIN WITH (FORMAT csv, HEADER true)
            """)

            load_csv(cur, "Data for Task - Txns.csv", """
                COPY public.raw_transactions (
                    connector_id,
                    device_id,
                    end_reason,
                    end_time,
                    meter_start,
                    meter_stop,
                    org,
                    payment_id,
                    payment_status,
                    soc,
                    start_time,
                    total_capacity,
                    total_usage,
                    txn_id,
                    user_id,
                    zone_id
                )
                FROM STDIN WITH (FORMAT csv, HEADER true)
            """)

            transaction_count, payment_count = validate_raw_data(cur)
            required_fields_ok = check_missing_values(cur)
            unique_ids_ok = check_duplicate_transactions(cur)
            start_times_ok = check_timestamp_format(cur)
            print(f"Required fields passed: {required_fields_ok}")
            check_time_order(cur)
            check_payment_references(cur)
            validation_passed = (
                required_fields_ok and unique_ids_ok and start_times_ok
            )

            print(f"Ready for aggregation: {validation_passed}")
            if validation_passed:
                build_daily_sessions(cur)
                check_session_total(cur, transaction_count)
            else:
                print("Aggregation skipped: validation failed.")
                print("Any existing daily summary was not refreshed.")

    print("Import completed.")
    print(f"Transactions: {transaction_count}")
    print(f"Payments: {payment_count}")

def validate_raw_data(cur):
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM public.raw_transactions),
            (SELECT COUNT(*) FROM public.raw_payments)
    """)
    transactions, payments = cur.fetchone()

    files = [
        ("Data for Task - Txns.csv", transactions),
        ("Data for Task - Pymts.csv", payments),
    ]

    for filename, db_count in files:
        with (DATA_DIR / filename).open(
            encoding="utf-8-sig", newline=""
        ) as file:
            reader = csv.reader(file)
            next(reader, None)
            csv_count = sum(1 for row in reader)

        if csv_count != db_count:
            raise ValueError(
                f"{filename}: CSV has {csv_count}, database has {db_count}"
            )

        print(f"PASS: {filename} — {db_count} rows")

    return transactions, payments


if __name__ == "__main__":
    main()