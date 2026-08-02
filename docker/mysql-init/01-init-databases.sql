-- 01-init-databases.sql
-- WHY THIS FILE EXISTS:
-- In a true microservice architecture, each service must possess its own isolated database.
-- Sharing databases across microservices creates tight coupling, prevents independent scaling, 
-- and allows unauthorized cross-domain SQL joins.
-- This script runs automatically when MySQL container boots up in Docker Compose.

CREATE DATABASE IF NOT EXISTS coordinator_db;
CREATE DATABASE IF NOT EXISTS order_db;
CREATE DATABASE IF NOT EXISTS inventory_db;
CREATE DATABASE IF NOT EXISTS payment_db;
CREATE DATABASE IF NOT EXISTS shipping_db;
CREATE DATABASE IF NOT EXISTS notification_db;

-- Grant privileges to the root user / app user for all databases
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'rootpassword';

GRANT ALL PRIVILEGES ON coordinator_db.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON order_db.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON inventory_db.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON payment_db.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON shipping_db.* TO 'root'@'%';
GRANT ALL PRIVILEGES ON notification_db.* TO 'root'@'%';

FLUSH PRIVILEGES;
