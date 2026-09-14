# Postgres Initialization Files

This folder contains SQL initialization files that are automatically executed when Docker Compose starts up.

## File Descriptions

### `01-schema.sql`
Creates the structure (DDL) for all database tables:
- `users` - Users table (riders and drivers)
- `vehicles` - Vehicles table
- `rides` - Rides table
- `payments` - Payments table
- `ratings` - Ratings table

Also creates INDEXes to speed up common queries.

### `02-sample-data.sql`
Inserts test sample data including:
- 20 users (1 rider + 19 drivers)
- 5 vehicles
- 5 rides
- 5 payment records
- 5 ratings

## Usage

### 1. First Startup
```bash
docker compose up -d
```

Docker Compose will automatically execute all `.sql` files in the `init/` folder (sorted by filename).

### 2. Check Initialization Status
```bash
docker compose logs postgres
```

You'll see output like this when successful:
```
postgres: database system is ready to accept connections
```

### 3. Connect to Database
**Via adminer (Web UI):**
- Open http://localhost:8080
- Server: `postgres`
- User: `agent_user`
- Password: `agent_pass`
- Database: `agent_db`

**Via psql (CLI):**
```bash
psql -h localhost -U agent_user -d agent_db
```

### 4. Clear Data and Reinitialize
```bash
docker compose down -v  # -v deletes volume and clears all data
docker compose up -d    # Rebuilds and automatically re-executes init SQL
```

## Adding or Modifying Data

### Adding Additional Initialization SQL
To add more initialization files, simply create new files in the `init/` folder and name them with numbers (e.g., `03-extra.sql`). Postgres will automatically execute them in numerical order.

### Modifying Existing Data
- Edit `02-sample-data.sql` directly and then run `docker compose down -v && docker compose up -d` to apply changes
- Or use adminer/psql to modify data directly in the running database

## Data Structure

### users table
- `user_id` (PK)
- `first_name`, `last_name`
- `email`, `phone`
- `city`, `province`
- `user_type` ('rider' or 'driver')
- `signup_date`, `is_active`

### vehicles table
- `vehicle_id` (PK)
- `driver_id` (FK → users)
- `make`, `model`, `year`
- `license_plate`, `color`
- `is_active`

### rides table
- `ride_id` (PK)
- `rider_id`, `driver_id` (FK → users)
- `requested_at`, `pickup_time`, `dropoff_time` (timestamps)
- `pickup_latitude/longitude`, `dropoff_latitude/longitude`
- `distance_km`, `fare`, `surge_multiplier`
- `status` ('completed', 'cancelled')
- `cancellation_reason`

### payments table
- `payment_id` (PK)
- `ride_id` (FK → rides)
- `user_id` (FK → users)
- `amount`, `payment_method`
- `payment_status` ('completed', 'failed', 'pending')
- `transaction_id`
- `payment_time`

### ratings table
- `rating_id` (PK)
- `ride_id` (FK → rides)
- `driver_id`, `rider_id` (FK → users)
- `rating` (1-5)
- `comment`
- `rated_at`

## Notes

- All tables have a `created_at` field that automatically records creation time
- Foreign key constraints are set up; deleting a user will cascade-delete related rides/payments/ratings
- INDEXes have been created to speed up common queries (user_type, email, ride status, etc.)
- Password `agent_pass` is for development/testing only; change it in production environments
