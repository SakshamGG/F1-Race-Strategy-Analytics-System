CREATE DATABASE IF NOT EXISTS f1_strategy_db;

USE f1_strategy_db;

CREATE TABLE DRIVERS (
    driver_id INT PRIMARY KEY AUTO_INCREMENT,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    nationality VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL
);

CREATE TABLE CONSTRUCTORS (
    constructor_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    nationality VARCHAR(50) NOT NULL,
    base_location VARCHAR(100) NOT NULL
);

CREATE TABLE CIRCUITS (
    circuit_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50) NOT NULL,
    city VARCHAR(50) NOT NULL,
    length_km DECIMAL(5,3) NOT NULL,
    number_of_turns INT NOT NULL
);

CREATE TABLE TYRE_COMPOUNDS (
    compound_id INT PRIMARY KEY AUTO_INCREMENT,
    compound_name VARCHAR(20) NOT NULL UNIQUE,
    color_code VARCHAR(7) NOT NULL,
    expected_lifespan_laps INT
);

CREATE TABLE ANALYSTS (
    analyst_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('Admin', 'Analyst', 'Viewer') NOT NULL,
    access_level INT NOT NULL DEFAULT 1
);

CREATE TABLE RACES (
    race_id INT PRIMARY KEY AUTO_INCREMENT,
    circuit_id INT NOT NULL,
    season_year YEAR NOT NULL,
    race_name VARCHAR(100) NOT NULL,
    race_date DATE NOT NULL,
    total_laps INT NOT NULL,
    round_number INT NOT NULL,

    FOREIGN KEY (circuit_id)
        REFERENCES CIRCUITS(circuit_id)
);

CREATE TABLE DRIVER_CONTRACTS (
    contract_id INT PRIMARY KEY AUTO_INCREMENT,
    driver_id INT NOT NULL,
    constructor_id INT NOT NULL,
    season_year YEAR NOT NULL,
    car_number INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,

    FOREIGN KEY (driver_id)
        REFERENCES DRIVERS(driver_id),

    FOREIGN KEY (constructor_id)
        REFERENCES CONSTRUCTORS(constructor_id),

    UNIQUE (driver_id, constructor_id, season_year)
);

CREATE TABLE RACE_RESULTS (
    result_id INT PRIMARY KEY AUTO_INCREMENT,
    race_id INT NOT NULL,
    driver_id INT NOT NULL,
    constructor_id INT NOT NULL,
    grid_position INT,
    finishing_position INT,
    points_scored DECIMAL(5,2) DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    fastest_lap_time TIME(3),

    FOREIGN KEY (race_id)
        REFERENCES RACES(race_id),

    FOREIGN KEY (driver_id)
        REFERENCES DRIVERS(driver_id),

    FOREIGN KEY (constructor_id)
        REFERENCES CONSTRUCTORS(constructor_id)
);

CREATE TABLE LAP_TIMES (
    lap_id INT PRIMARY KEY AUTO_INCREMENT,
    race_id INT NOT NULL,
    driver_id INT NOT NULL,
    compound_id INT NOT NULL,
    lap_number INT NOT NULL,
    lap_time TIME(3) NOT NULL,
    sector1_time DECIMAL(6,3),
    sector2_time DECIMAL(6,3),
    sector3_time DECIMAL(6,3),

    FOREIGN KEY (race_id)
        REFERENCES RACES(race_id),

    FOREIGN KEY (driver_id)
        REFERENCES DRIVERS(driver_id),

    FOREIGN KEY (compound_id)
        REFERENCES TYRE_COMPOUNDS(compound_id)
);

CREATE TABLE PIT_STOPS (
    pit_stop_id INT PRIMARY KEY AUTO_INCREMENT,
    race_id INT NOT NULL,
    driver_id INT NOT NULL,
    compound_removed_id INT NOT NULL,
    compound_fitted_id INT NOT NULL,
    lap_number INT NOT NULL,
    stop_duration DECIMAL(5,3) NOT NULL,
    pit_loss_time DECIMAL(5,3),

    FOREIGN KEY (race_id)
        REFERENCES RACES(race_id),

    FOREIGN KEY (driver_id)
        REFERENCES DRIVERS(driver_id),

    FOREIGN KEY (compound_removed_id)
        REFERENCES TYRE_COMPOUNDS(compound_id),

    FOREIGN KEY (compound_fitted_id)
        REFERENCES TYRE_COMPOUNDS(compound_id)
);

CREATE TABLE WEATHER_CONDITIONS (
    weather_id INT PRIMARY KEY AUTO_INCREMENT,
    race_id INT NOT NULL,
    session_type ENUM(
        'FP1',
        'FP2',
        'FP3',
        'Qualifying',
        'Sprint',
        'Race'
    ) NOT NULL,
    temperature_celsius DECIMAL(4,1),
    humidity_percent DECIMAL(4,1),
    wind_speed_kmh DECIMAL(5,1),
    track_condition ENUM('Dry', 'Damp', 'Wet') NOT NULL,
    rainfall_mm DECIMAL(5,1) DEFAULT 0,

    FOREIGN KEY (race_id)
        REFERENCES RACES(race_id)
);

CREATE TABLE STRATEGY_NOTES (
    note_id INT PRIMARY KEY AUTO_INCREMENT,
    race_id INT NOT NULL,
    analyst_id INT NOT NULL,
    driver_id INT NOT NULL,
    note_text TEXT NOT NULL,
    note_type ENUM(
        'Observation',
        'Recommendation',
        'Post-Race Review'
    ) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (race_id)
        REFERENCES RACES(race_id),

    FOREIGN KEY (analyst_id)
        REFERENCES ANALYSTS(analyst_id),

    FOREIGN KEY (driver_id)
        REFERENCES DRIVERS(driver_id)
);