-- 插入 users 表 sample data
INSERT INTO users (user_id, first_name, last_name, email, phone, city, province, user_type, signup_date, is_active) VALUES
(1, 'Danielle', 'Johnson', 'user1@example.com', '+13567729816', 'Halifax', 'NS', 'rider', '2025-05-25', TRUE),
(2, 'Joshua', 'Walker', 'user2@example.com', '+19222900764', 'Vancouver', 'BC', 'rider', '2025-05-04', TRUE),
(3, 'Jill', 'Rhodes', 'user3@example.com', '+12900432998', 'Winnipeg', 'MB', 'rider', '2026-05-24', TRUE),
(4, 'Patricia', 'Miller', 'user4@example.com', '+19812397600', 'Montreal', 'QC', 'rider', '2026-05-21', TRUE),
(5, 'Robert', 'Johnson', 'user5@example.com', '+16892737056', 'Winnipeg', 'MB', 'rider', '2024-04-15', TRUE),
(6945, 'Michael', 'Smith', 'driver6945@example.com', '+14165551234', 'Toronto', 'ON', 'driver', '2023-01-10', TRUE),
(5541, 'Sarah', 'Brown', 'driver5541@example.com', '+14165551235', 'Toronto', 'ON', 'driver', '2023-02-15', TRUE),
(8738, 'James', 'Davis', 'driver8738@example.com', '+14165551236', 'Toronto', 'ON', 'driver', '2023-03-20', TRUE),
(5455, 'Jennifer', 'Wilson', 'driver5455@example.com', '+14165551237', 'Toronto', 'ON', 'driver', '2023-04-25', TRUE),
(1129, 'David', 'Moore', 'driver1129@example.com', '+14165551238', 'Toronto', 'ON', 'driver', '2023-05-30', TRUE),
(7667, 'Lisa', 'Taylor', 'driver7667@example.com', '+14165551239', 'Toronto', 'ON', 'driver', '2023-06-10', TRUE),
(3147, 'Christopher', 'Anderson', 'driver3147@example.com', '+14165551240', 'Toronto', 'ON', 'driver', '2023-07-15', TRUE),
(2267, 'Mary', 'Thomas', 'driver2267@example.com', '+14165551241', 'Toronto', 'ON', 'driver', '2023-08-20', TRUE),
(4679, 'Daniel', 'Jackson', 'driver4679@example.com', '+14165551242', 'Toronto', 'ON', 'driver', '2023-09-25', TRUE),
(8698, 'Nancy', 'White', 'driver8698@example.com', '+14165551243', 'Toronto', 'ON', 'driver', '2023-10-30', TRUE),
(7514, 'Mark', 'Harris', 'driver7514@example.com', '+14165551244', 'Toronto', 'ON', 'driver', '2024-01-05', TRUE),
(4936, 'Karen', 'Martin', 'driver4936@example.com', '+14165551245', 'Toronto', 'ON', 'driver', '2024-02-10', TRUE),
(5849, 'Steven', 'Thompson', 'driver5849@example.com', '+14165551246', 'Toronto', 'ON', 'driver', '2024-03-15', TRUE),
(1030, 'Betty', 'Garcia', 'driver1030@example.com', '+14165551247', 'Toronto', 'ON', 'driver', '2024-04-20', TRUE),
(8856, 'Paul', 'Martinez', 'driver8856@example.com', '+14165551248', 'Toronto', 'ON', 'driver', '2024-05-25', TRUE);

-- 重設 user_id sequence
SELECT setval('users_user_id_seq', (SELECT MAX(user_id) FROM users) + 1);

-- 插入 vehicles 表 sample data
INSERT INTO vehicles (vehicle_id, driver_id, make, model, year, license_plate, color, is_active) VALUES
(1, 6945, 'Honda', 'CR-V', 2024, 'OP331', 'Grey', TRUE),
(2, 5541, 'Hyundai', 'Sonata', 2026, 'WK520', 'Black', TRUE),
(3, 8738, 'Ford', 'Fusion', 2022, 'LI224', 'Black', TRUE),
(4, 5455, 'Toyota', 'RAV4', 2015, 'FN542', 'Black', TRUE),
(5, 1129, 'Hyundai', 'Sonata', 2016, 'CS875', 'Grey', TRUE);

-- 重設 vehicle_id sequence
SELECT setval('vehicles_vehicle_id_seq', (SELECT MAX(vehicle_id) FROM vehicles) + 1);

-- 插入 rides 表 sample data
INSERT INTO rides (ride_id, rider_id, driver_id, requested_at, pickup_time, dropoff_time, pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude, distance_km, fare, surge_multiplier, status, cancellation_reason) VALUES
(1, 1, 7514, '2026-02-27 20:13:30', NULL, NULL, 44.229291, -63.543162, 44.496423, -67.980735, 0.00, 0.00, 1.00, 'cancelled', 'driver_cancelled'),
(2, 2, 4936, '2025-12-26 08:26:37', '2025-12-26 08:34:37', '2025-12-26 08:59:37', 43.881270, -70.083206, 43.410488, -70.560855, 13.16, 52.17, 1.50, 'completed', NULL),
(3, 3, 5849, '2025-07-03 07:58:26', '2025-07-03 08:02:26', '2025-07-03 09:02:26', 43.856247, -75.945737, 44.133943, -70.313959, 26.59, 70.53, 1.00, 'completed', NULL),
(4, 4, 1030, '2025-03-01 04:50:04', '2025-03-01 05:03:04', '2025-03-01 05:40:04', 44.360329, -64.339011, 44.395041, -77.436515, 11.35, 42.98, 1.20, 'completed', NULL),
(5, 5, 8856, '2026-07-09 07:45:41', '2026-07-09 07:51:41', '2026-07-09 08:36:41', 43.696089, -66.938775, 44.669130, -74.876163, 23.35, 59.61, 1.00, 'completed', NULL);

-- 重設 ride_id sequence
SELECT setval('rides_ride_id_seq', (SELECT MAX(ride_id) FROM rides) + 1);

-- 插入 payments 表 sample data
INSERT INTO payments (payment_id, ride_id, user_id, amount, payment_method, payment_status, transaction_id, payment_time) VALUES
(1, 1, 6945, 16.07, 'credit_card', 'completed', 'TXN-00000001', '2026-04-07 15:15:52'),
(2, 2, 5541, 47.01, 'debit_card', 'completed', 'TXN-00000002', '2025-10-07 14:56:33'),
(3, 3, 8738, 74.77, 'paypal', 'completed', 'TXN-00000003', '2026-01-14 16:19:32'),
(4, 4, 5455, 66.79, 'apple_pay', 'completed', 'TXN-00000004', '2026-03-20 08:37:33'),
(5, 5, 1129, 30.85, 'paypal', 'completed', 'TXN-00000005', '2026-04-29 18:56:19');

-- 重設 payment_id sequence
SELECT setval('payments_payment_id_seq', (SELECT MAX(payment_id) FROM payments) + 1);

-- 插入 ratings 表 sample data
INSERT INTO ratings (rating_id, ride_id, driver_id, rider_id, rating, comment, rated_at) VALUES
(1, 1, 7667, 1, 5, 'Could have been better', '2025-09-09 13:41:28'),
(2, 2, 3147, 2, 4, 'Could have been better', '2026-06-02 23:39:31'),
(3, 3, 2267, 3, 5, 'Great ride', '2026-07-23 06:31:59'),
(4, 4, 4679, 4, 3, 'Average experience', '2026-04-23 04:57:28'),
(5, 5, 8698, 5, 5, 'Average experience', '2025-10-09 06:15:35');

-- 重設 rating_id sequence
SELECT setval('ratings_rating_id_seq', (SELECT MAX(rating_id) FROM ratings) + 1);
