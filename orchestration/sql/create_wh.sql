-- ============================================================
-- Climate Intelligence Platform - Star Schema Data Warehouse
-- FIXED: Aligned with 80-city global Kafka producer schema
-- ============================================================
-- Changes from original:
--   1. dim_location: added continent, changed UNIQUE to (city, country)
--      to handle 80 global cities (most have NULL state)
--   2. dim_weather_type: added weather_description column
--   3. fact table: no changes (visibility_km, uv_index stay as-is)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS climate_warehouse;

-- ============================================================
-- DIMENSION: dim_location
-- FIXED: Added continent, changed unique key to (city, country)
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.dim_location (
    location_key    SERIAL PRIMARY KEY,
    city            VARCHAR(100) NOT NULL,
    country         VARCHAR(50) DEFAULT 'US',
    continent       VARCHAR(50),
    state           VARCHAR(50),
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    region          VARCHAR(50),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- FIXED: Use (city, country) instead of (city, state)
    -- because 70+ global cities have NULL state
    UNIQUE (city, country)
);

-- ============================================================
-- DIMENSION: dim_time
-- Pre-populated hourly timestamps for 2 years
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
-- FIXED: Added weather_description from producer
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
-- All measurements + engineered features
-- ============================================================
CREATE TABLE IF NOT EXISTS climate_warehouse.fact_weather_readings (
    reading_key             SERIAL PRIMARY KEY,
    -- Foreign keys to dimensions
    location_key            INT REFERENCES climate_warehouse.dim_location(location_key),
    time_key                INT REFERENCES climate_warehouse.dim_time(time_key),
    weather_type_key        INT REFERENCES climate_warehouse.dim_weather_type(weather_type_key),
    -- Measurements
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
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_fact_location ON climate_warehouse.fact_weather_readings(location_key);
CREATE INDEX IF NOT EXISTS idx_fact_time ON climate_warehouse.fact_weather_readings(time_key);
CREATE INDEX IF NOT EXISTS idx_fact_weather_type ON climate_warehouse.fact_weather_readings(weather_type_key);
CREATE INDEX IF NOT EXISTS idx_fact_extreme ON climate_warehouse.fact_weather_readings(is_extreme_weather);

-- ============================================================
-- POPULATE dim_weather_type with known conditions
-- These match OpenWeatherMap API "main" field values
-- ============================================================
INSERT INTO climate_warehouse.dim_weather_type (condition, category, severity, description)
VALUES
    ('Clear', 'Fair', 'Normal', 'Clear skies'),
    ('Partly Cloudy', 'Fair', 'Normal', 'Partially cloudy skies'),
    ('Cloudy', 'Overcast', 'Normal', 'Fully overcast'),
    ('Clouds', 'Overcast', 'Normal', 'Cloudy skies'),
    ('Rain', 'Precipitation', 'Moderate', 'Rainfall'),
    ('Heavy Rain', 'Precipitation', 'Severe', 'Heavy rainfall with flooding risk'),
    ('Thunderstorm', 'Storm', 'Severe', 'Thunder and lightning with rain'),
    ('Snow', 'Precipitation', 'Moderate', 'Snowfall'),
    ('Blizzard', 'Storm', 'Extreme', 'Heavy snow with strong winds'),
    ('Fog', 'Visibility', 'Moderate', 'Reduced visibility due to fog'),
    ('Mist', 'Visibility', 'Normal', 'Light mist'),
    ('Haze', 'Visibility', 'Normal', 'Light haze'),
    ('Smoke', 'Visibility', 'Moderate', 'Smoke reducing visibility'),
    ('Dust', 'Visibility', 'Moderate', 'Dust in air'),
    ('Sand', 'Visibility', 'Moderate', 'Sand storm'),
    ('Drizzle', 'Precipitation', 'Normal', 'Light rain'),
    ('Windy', 'Wind', 'Moderate', 'Strong winds'),
    ('Squall', 'Wind', 'Severe', 'Sudden strong wind'),
    ('Tornado', 'Storm', 'Extreme', 'Tornado conditions'),
    ('Hurricane', 'Storm', 'Extreme', 'Hurricane conditions'),
    ('Unknown', 'Unknown', 'Normal', 'Condition not determined')
ON CONFLICT (condition) DO NOTHING;

-- ============================================================
-- POPULATE dim_time (2 years of hourly timestamps)
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