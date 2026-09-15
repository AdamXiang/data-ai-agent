"""Seed and load a PostgreSQL database for the ride-sharing AI agent.

This standalone data-feed script performs the following steps:

1. Reads the database connection settings from environment variables.
2. Creates the schema (``users``, ``vehicles``, ``rides``, ``payments``,
   ``ratings``) together with foreign-key constraints and indexes.
3. Loads the CSV files from the ``data/`` directory into those tables
   using PostgreSQL's high-performance ``COPY`` command.
4. Prints the loaded record counts, commits the whole transaction, and
   closes the database connection.

Environment variables used (loaded from ``.env``)::

    HOST        -- PostgreSQL host name
    PORT        -- PostgreSQL port (defaults to ``5432``)
    DATABASE    -- Name of the target database
    USER        -- Database user
    PASSWORD    -- Password for the database user

Usage::

    python database_feed.py
"""

import os

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

# Load environment variables from the .env file into the current process
load_dotenv()

# Fall back to the default PostgreSQL port when it is not set in .env
# NOTE: this sets os.environ["PORT"], not "DB_PORT" -- the DB_CONFIG
# block below still reads os.environ["DB_PORT"] directly, so if DB_PORT
# is genuinely missing from .env this fallback won't actually prevent
# the KeyError on line "port": int(os.environ["DB_PORT"]) below.
# Flagging as-is rather than changing the behavior; worth fixing in a
# follow-up (either write to "DB_PORT" here, or use os.environ.get(...)
# with a default down in DB_CONFIG).
if "DB_PORT" not in os.environ:
    os.environ["DB_PORT"] = "5432"

# ============================================================
# CONFIGURATION
# ============================================================

# Database connection settings pulled from environment variables
DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ["DB_PORT"]),
    "database": os.environ["DB_DATABASE"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
}

# Directory (relative to this script) that holds the CSV seed files
# NOTE: unlike utils/etl_tools.py, this path is resolved relative to
# the *current working directory* the script is launched from, not to
# this file's location -- run `python database_feed.py` from the
# project root (where the `data/` folder lives) or this will fail.
CSV_DIR = "data"


# ============================================================
# DATABASE CONNECTION
# ============================================================

# Open a connection to PostgreSQL using the configuration above
conn = psycopg2.connect(**DB_CONFIG)

# Disable autocommit so all changes below are applied
# as a single, atomic transaction
conn.autocommit = False

# Create a cursor used for executing SQL statements
cursor = conn.cursor()

print("Connected to PostgreSQL")


# ============================================================
# CREATE TABLES
# ============================================================

create_tables_sql = """

CREATE SCHEMA IF NOT EXISTS public;

-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE IF NOT EXISTS public.users (
    user_id INTEGER PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    city VARCHAR(100),
    province VARCHAR(50),
    user_type VARCHAR(20) NOT NULL,
    signup_date DATE,
    is_active BOOLEAN
);


-- =========================================================
-- VEHICLES
-- =========================================================

CREATE TABLE IF NOT EXISTS public.vehicles (
    vehicle_id INTEGER PRIMARY KEY,
    driver_id INTEGER NOT NULL,
    make VARCHAR(50),
    model VARCHAR(50),
    year INTEGER,
    license_plate VARCHAR(20) UNIQUE,
    color VARCHAR(30),
    is_active BOOLEAN,

    CONSTRAINT fk_vehicle_driver
        FOREIGN KEY (driver_id)
        REFERENCES public.users(user_id)
);


-- =========================================================
-- RIDES
-- =========================================================

CREATE TABLE IF NOT EXISTS public.rides (
    ride_id INTEGER PRIMARY KEY,

    rider_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,

    requested_at TIMESTAMP,
    pickup_time TIMESTAMP,
    dropoff_time TIMESTAMP,

    pickup_latitude DECIMAL(9,6),
    pickup_longitude DECIMAL(9,6),

    dropoff_latitude DECIMAL(9,6),
    dropoff_longitude DECIMAL(9,6),

    distance_km DECIMAL(10,2),
    fare DECIMAL(10,2),
    surge_multiplier DECIMAL(4,2),

    status VARCHAR(30),
    cancellation_reason VARCHAR(100),

    CONSTRAINT fk_ride_rider
        FOREIGN KEY (rider_id)
        REFERENCES public.users(user_id),

    CONSTRAINT fk_ride_driver
        FOREIGN KEY (driver_id)
        REFERENCES public.users(user_id)
);


-- =========================================================
-- PAYMENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS public.payments (
    payment_id INTEGER PRIMARY KEY,

    ride_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,

    amount DECIMAL(10,2),

    payment_method VARCHAR(50),
    payment_status VARCHAR(30),

    transaction_id VARCHAR(100) UNIQUE,
    payment_time TIMESTAMP,

    CONSTRAINT fk_payment_ride
        FOREIGN KEY (ride_id)
        REFERENCES public.rides(ride_id),

    CONSTRAINT fk_payment_user
        FOREIGN KEY (user_id)
        REFERENCES public.users(user_id)
);


-- =========================================================
-- RATINGS
-- =========================================================

CREATE TABLE IF NOT EXISTS public.ratings (
    rating_id INTEGER PRIMARY KEY,

    ride_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    driver_id INTEGER NOT NULL,

    rating INTEGER,
    comment TEXT,
    rated_at TIMESTAMP,

    CONSTRAINT fk_rating_ride
        FOREIGN KEY (ride_id)
        REFERENCES public.rides(ride_id),

    CONSTRAINT fk_rating_rider
        FOREIGN KEY (rider_id)
        REFERENCES public.users(user_id),

    CONSTRAINT fk_rating_driver
        FOREIGN KEY (driver_id)
        REFERENCES public.users(user_id),

    CONSTRAINT chk_rating
        CHECK (rating BETWEEN 1 AND 5)
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_vehicles_driver_id
ON public.vehicles(driver_id);

CREATE INDEX IF NOT EXISTS idx_rides_rider_id
ON public.rides(rider_id);

CREATE INDEX IF NOT EXISTS idx_rides_driver_id
ON public.rides(driver_id);

CREATE INDEX IF NOT EXISTS idx_rides_requested_at
ON public.rides(requested_at);

CREATE INDEX IF NOT EXISTS idx_rides_status
ON public.rides(status);

CREATE INDEX IF NOT EXISTS idx_payments_ride_id
ON public.payments(ride_id);

CREATE INDEX IF NOT EXISTS idx_payments_user_id
ON public.payments(user_id);

CREATE INDEX IF NOT EXISTS idx_ratings_ride_id
ON public.ratings(ride_id);

CREATE INDEX IF NOT EXISTS idx_ratings_driver_id
ON public.ratings(driver_id);

"""

# Run the DDL script that creates the schema, tables, constraints,
# and indexes (all statements use IF NOT EXISTS / CREATE IF NOT EXISTS)
cursor.execute(create_tables_sql)

print("Tables created successfully")


# ============================================================
# CLEAR EXISTING DATA
# ============================================================

# The TRUNCATE below wipes all rows from every table before the
# CSVs are reloaded, so each run starts from a clean slate.
# Remove or comment out this block to keep existing data across runs.
# CASCADE also truncates any tables referencing these via foreign keys.
# cursor.execute("""
#     TRUNCATE TABLE
#         public.ratings,
#         public.payments,
#         public.rides,
#         public.vehicles,
#         public.users
#     CASCADE;
# """)


# ============================================================
# LOAD CSV USING POSTGRES COPY
# ============================================================


def load_csv(table_name, csv_file, columns):
    """Load a CSV file into the given table using PostgreSQL's COPY.

    The CSV file's first line is treated as a header, so the order of
    ``columns`` must match the header order of the file.

    Args:
        table_name (str): Name of the target table in the ``public`` schema.
        csv_file (str): Name of the CSV file located in ``CSV_DIR``
            (e.g. ``"users.csv"``).
        columns (list of str): Ordered column names into which the CSV
            rows should be inserted.

    Raises:
        FileNotFoundError: If ``csv_file`` does not exist in ``CSV_DIR``.

    Note:
        The COPY options ``HEADER TRUE`` and ``NULL ''`` mean the first
        line of the file is treated as a header and empty fields are
        stored as NULL.
    """

    # Build the full path to the target CSV file
    file_path = os.path.join(CSV_DIR, csv_file)

    # Fail fast with a clear message if the seed file is missing
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Build the COPY ... FROM STDIN statement. sql.Identifier safely
    # quotes the schema/table/column names in the generated SQL.
    copy_sql = sql.SQL("""
        COPY {} ({})
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            DELIMITER ',',
            NULL ''
        )
    """).format(
        sql.Identifier("public", table_name),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
    )

    # Stream the CSV contents directly into PostgreSQL through the cursor
    with open(file_path, "r", encoding="utf-8") as file:
        cursor.copy_expert(copy_sql, file)

    print(f"Loaded {csv_file}")


# ============================================================
# LOAD USERS
# ============================================================

# Load all user records (profile, contact, signup and status data)
load_csv(
    "users",
    "users.csv",
    [
        "user_id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "city",
        "province",
        "user_type",
        "signup_date",
        "is_active",
    ],
)


# ============================================================
# LOAD VEHICLES
# ============================================================

# Load all vehicle records, linked to their owning drivers
load_csv(
    "vehicles",
    "vehicles.csv",
    [
        "vehicle_id",
        "driver_id",
        "make",
        "model",
        "year",
        "license_plate",
        "color",
        "is_active",
    ],
)


# ============================================================
# LOAD RIDES
# ============================================================

# Load all ride records (trip timing, routing and fare information)
load_csv(
    "rides",
    "rides.csv",
    [
        "ride_id",
        "rider_id",
        "driver_id",
        "requested_at",
        "pickup_time",
        "dropoff_time",
        "pickup_latitude",
        "pickup_longitude",
        "dropoff_latitude",
        "dropoff_longitude",
        "distance_km",
        "fare",
        "surge_multiplier",
        "status",
        "cancellation_reason",
    ],
)


# ============================================================
# LOAD PAYMENTS
# ============================================================

# Load all payment records associated with completed rides
load_csv(
    "payments",
    "payments.csv",
    [
        "payment_id",
        "ride_id",
        "user_id",
        "amount",
        "payment_method",
        "payment_status",
        "transaction_id",
        "payment_time",
    ],
)


# ============================================================
# LOAD RATINGS
# ============================================================

# Load all rating records left by riders and drivers after rides
load_csv(
    "ratings",
    "ratings.csv",
    [
        "rating_id",
        "ride_id",
        "rider_id",
        "driver_id",
        "rating",
        "comment",
        "rated_at",
    ],
)


# ============================================================
# VERIFY RECORD COUNTS
# ============================================================

# List of tables to sanity-check after the CSV loads finish
tables = [
    "users",
    "vehicles",
    "rides",
    "payments",
    "ratings",
]

print("\nRecord counts:")
print("-" * 40)

# Print the row count of every table to verify the data was loaded
for table in tables:
    cursor.execute(
        sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier("public"), sql.Identifier(table)
        )
    )

    # Fetch the aggregate count and print it right-aligned for readability
    count = cursor.fetchone()[0]

    print(f"{table:<15} {count:>10,}")


# ============================================================
# COMMIT
# ============================================================

# Commit the entire transaction — all COPY loads are saved atomically
conn.commit()

print("\nData loaded successfully!")
print("Transaction committed.")


# ============================================================
# CLOSE CONNECTION
# ============================================================

# Release the cursor and close the connection to the database
cursor.close()
conn.close()

print("PostgreSQL connection closed.")
