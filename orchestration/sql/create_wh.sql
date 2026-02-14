-- ============================================================
-- Climate Intelligence Platform - Star Schema Data Warehouse
-- ============================================================
-- This creates the dimensional model in PostgreSQL.
-- In production, this would be in BigQuery instead.
-- The SQL is almost identical for both.
-- ============================================================

-- Create a separate schema for the warehouse
CREATE SCHEMA IF NOT EXISTS climate_warehouse;

-- ============================================================
-- DIMENSION: dim_location
-- Contains geographic information about weather stations/cities
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.dim_location (
    location_key    SERIAL PRIMARY KEY,
    city            VARCHAR(100) NOT NULL,
    state           VARCHAR(50),
    country         VARCHAR(50) DEFAULT 'US',
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    region          VARCHAR(50),
    -- Slowly Changing Dimension Type 1 (overwrite)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city, state)
);

-- ============================================================
-- DIMENSION: dim_time
-- Pre-populated time dimension for fast date-based queries
-- Contains every hour for a full year
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.dim_time (
    time_key        SERIAL PRIMARY KEY,
    full_timestamp  TIMESTAMP NOT NULL,
    date            DATE NOT NULL,
    year            INT NOT NULL,
    quarter         INT NOT NULL,
    month           INT NOT NULL,
    month_name      VARCHAR(20) NOT NULL,
    week_of_year    INT NOT NULL,
    day_of_month    INT NOT NULL,
    day_of_week     INT NOT NULL,
    day_name        VARCHAR(20) NOT NULL,
    hour            INT NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    season          VARCHAR(10) NOT NULL,
    UNIQUE (full_timestamp)
);

-- ============================================================
-- DIMENSION: dim_weather_type
-- Categorizes weather conditions
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.dim_weather_type (
    weather_type_key  SERIAL PRIMARY KEY,
    condition         VARCHAR(50) NOT NULL,
    category          VARCHAR(50),
    severity          VARCHAR(20) DEFAULT 'Normal',
    description       TEXT,
    UNIQUE (condition)
);

-- ============================================================
-- FACT: fact_weather_readings
-- The main fact table with all measurements
-- Foreign keys link to dimension tables
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.fact_weather_readings (
    reading_key             SERIAL PRIMARY KEY,
    -- Foreign keys to dimensions
    location_key            INT REFERENCES climate_warehouse.dim_location(location_key),
    time_key                INT REFERENCES climate_warehouse.dim_time(time_key),
    weather_type_key        INT REFERENCES climate_warehouse.dim_weather_type(weather_type_key),
    -- Measurements (what we want to analyze)
    temperature_fahrenheit  DOUBLE PRECISION,
    temperature_celsius     DOUBLE PRECISION,
    humidity_percent        DOUBLE PRECISION,
    pressure_hpa            DOUBLE PRECISION,
    wind_speed_mph          DOUBLE PRECISION,
    wind_direction_degrees  INT,
    precipitation_mm        DOUBLE PRECISION,
    visibility_km           DOUBLE PRECISION,
    cloud_cover_percent     INT,
    uv_index                DOUBLE PRECISION,
    -- Engineered features (from Gold layer)
    heat_index              DOUBLE PRECISION,
    wind_chill              DOUBLE PRECISION,
    temp_anomaly            DOUBLE PRECISION,
    temp_anomaly_score      DOUBLE PRECISION,
    -- Extreme weather flags
    is_extreme_weather      INT DEFAULT 0,
    is_heatwave             INT DEFAULT 0,
    is_extreme_cold         INT DEFAULT 0,
    is_high_wind            INT DEFAULT 0,
    is_heavy_precipitation  INT DEFAULT 0,
    -- Metadata
    source                  VARCHAR(50),
    quality_flag            VARCHAR(50),
    loaded_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- INDEXES for faster queries
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fact_location ON climate_warehouse.fact_weather_readings(location_key);
CREATE INDEX IF NOT EXISTS idx_fact_time ON climate_warehouse.fact_weather_readings(time_key);
CREATE INDEX IF NOT EXISTS idx_fact_weather_type ON climate_warehouse.fact_weather_readings(weather_type_key);
CREATE INDEX IF NOT EXISTS idx_fact_extreme ON climate_warehouse.fact_weather_readings(is_extreme_weather);

-- ============================================================
-- POPULATE dim_weather_type with known conditions
-- ============================================================
INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
VALUES
    ('Clear', 'Fair', 'Normal', 'Clear skies'),
    ('Partly Cloudy', 'Fair', 'Normal', 'Partially cloudy skies'),
    ('Cloudy', 'Overcast', 'Normal', 'Fully overcast'),
    ('Rain', 'Precipitation', 'Moderate', 'Rainfall'),
    ('Heavy Rain', 'Precipitation', 'Severe', 'Heavy rainfall with flooding risk'),
    ('Thunderstorm', 'Storm', 'Severe', 'Thunder and lightning with rain'),
    ('Snow', 'Precipitation', 'Moderate', 'Snowfall'),
    ('Blizzard', 'Storm', 'Extreme', 'Heavy snow with strong winds'),
    ('Fog', 'Visibility', 'Moderate', 'Reduced visibility'),
    ('Windy', 'Wind', 'Moderate', 'Strong winds'),
    ('Tornado', 'Storm', 'Extreme', 'Tornado conditions'),
    ('Hurricane', 'Storm', 'Extreme', 'Hurricane conditions'),
    ('Haze', 'Visibility', 'Normal', 'Light haze'),
    ('Drizzle', 'Precipitation', 'Normal', 'Light rain'),
    ('Unknown', 'Unknown', 'Normal', 'Condition not determined')
ON CONFLICT (condition) DO NOTHING;

-- ============================================================
-- POPULATE dim_time (generate 1 year of hourly timestamps)
-- ============================================================
INSERT INTO climate_warehouse.dim_time (
    full_timestamp, date, year, quarter, month, month_name,
    week_of_year, day_of_month, day_of_week, day_name,
    hour, is_weekend, season
)
SELECT
    ts,
    ts::date,
    EXTRACT(YEAR FROM ts)::int,
    EXTRACT(QUARTER FROM ts)::int,
    EXTRACT(MONTH FROM ts)::int,
    TO_CHAR(ts, 'Month'),
    EXTRACT(WEEK FROM ts)::int,
    EXTRACT(DAY FROM ts)::int,
    EXTRACT(DOW FROM ts)::int,
    TO_CHAR(ts, 'Day'),
    EXTRACT(HOUR FROM ts)::int,
    EXTRACT(DOW FROM ts) IN (0, 6),
    CASE
        WHEN EXTRACT(MONTH FROM ts) IN (12, 1, 2) THEN 'Winter'
        WHEN EXTRACT(MONTH FROM ts) IN (3, 4, 5) THEN 'Spring'
        WHEN EXTRACT(MONTH FROM ts) IN (6, 7, 8) THEN 'Summer'
        ELSE 'Fall'
    END
FROM generate_series(
    '2025-01-01 00:00:00'::timestamp,
    '2026-12-31 23:00:00'::timestamp,
    '1 hour'::interval
) AS ts
ON CONFLICT (full_timestamp) DO NOTHING;