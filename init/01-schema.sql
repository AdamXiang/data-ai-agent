-- 建立 users 表
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(50),
    province VARCHAR(50),
    user_type VARCHAR(20) NOT NULL, -- 'rider' or 'driver'
    signup_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立 vehicles 表
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id SERIAL PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    make VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    license_plate VARCHAR(20) UNIQUE NOT NULL,
    color VARCHAR(30),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立 rides 表
CREATE TABLE IF NOT EXISTS rides (
    ride_id SERIAL PRIMARY KEY,
    rider_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    driver_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    requested_at TIMESTAMP NOT NULL,
    pickup_time TIMESTAMP,
    dropoff_time TIMESTAMP,
    pickup_latitude NUMERIC(10, 6),
    pickup_longitude NUMERIC(10, 6),
    dropoff_latitude NUMERIC(10, 6),
    dropoff_longitude NUMERIC(10, 6),
    distance_km NUMERIC(10, 2),
    fare NUMERIC(10, 2),
    surge_multiplier NUMERIC(4, 2) DEFAULT 1.00,
    status VARCHAR(20) NOT NULL, -- 'completed', 'cancelled', 'in_progress'
    cancellation_reason VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立 payments 表
CREATE TABLE IF NOT EXISTS payments (
    payment_id SERIAL PRIMARY KEY,
    ride_id INTEGER NOT NULL REFERENCES rides(ride_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    amount NUMERIC(10, 2) NOT NULL,
    payment_method VARCHAR(30) NOT NULL, -- 'credit_card', 'debit_card', 'paypal', 'apple_pay'
    payment_status VARCHAR(20) NOT NULL, -- 'completed', 'failed', 'pending'
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    payment_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立 ratings 表
CREATE TABLE IF NOT EXISTS ratings (
    rating_id SERIAL PRIMARY KEY,
    ride_id INTEGER NOT NULL REFERENCES rides(ride_id) ON DELETE CASCADE,
    driver_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    rider_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    rated_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 建立 index 加速查詢
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_vehicles_driver_id ON vehicles(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_rider_id ON rides(rider_id);
CREATE INDEX IF NOT EXISTS idx_rides_driver_id ON rides(driver_id);
CREATE INDEX IF NOT EXISTS idx_rides_requested_at ON rides(requested_at);
CREATE INDEX IF NOT EXISTS idx_rides_status ON rides(status);
CREATE INDEX IF NOT EXISTS idx_payments_ride_id ON payments(ride_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_ride_id ON ratings(ride_id);
CREATE INDEX IF NOT EXISTS idx_ratings_driver_id ON ratings(driver_id);
CREATE INDEX IF NOT EXISTS idx_ratings_rider_id ON ratings(rider_id);
