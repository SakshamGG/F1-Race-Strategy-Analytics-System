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
        REFERENCES CIRCUITS(circuit_id),

    UNIQUE (season_year, round_number)
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
        REFERENCES CONSTRUCTORS(constructor_id),

    UNIQUE (race_id, driver_id),
    INDEX idx_results_race (race_id, finishing_position)
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
        REFERENCES TYRE_COMPOUNDS(compound_id),

    UNIQUE KEY idx_laptimes_lookup (race_id, driver_id, lap_number)
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
        REFERENCES TYRE_COMPOUNDS(compound_id),

    INDEX idx_pitstops_lookup (race_id, driver_id)
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
        REFERENCES RACES(race_id),

    UNIQUE (race_id, session_type)
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

-- ==============================================================================
-- DATABASE VIEWS (Relational Joins & Analytics)
-- ==============================================================================

CREATE OR REPLACE VIEW v_race_results_detailed AS
SELECT 
    rr.result_id,
    rr.race_id,
    r.race_name,
    r.season_year,
    r.round_number,
    rr.driver_id,
    CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
    d.nationality AS driver_nationality,
    rr.constructor_id,
    c.name AS team_name,
    c.nationality AS team_nationality,
    rr.grid_position,
    rr.finishing_position,
    rr.points_scored,
    rr.status,
    rr.fastest_lap_time
FROM RACE_RESULTS rr
JOIN RACES r ON rr.race_id = r.race_id
JOIN DRIVERS d ON rr.driver_id = d.driver_id
JOIN CONSTRUCTORS c ON rr.constructor_id = c.constructor_id;

CREATE OR REPLACE VIEW v_lap_times_detailed AS
SELECT 
    lt.lap_id,
    lt.race_id,
    r.race_name,
    r.season_year,
    lt.driver_id,
    CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
    lt.compound_id,
    tc.compound_name,
    tc.color_code AS compound_color,
    lt.lap_number,
    lt.lap_time,
    lt.sector1_time,
    lt.sector2_time,
    lt.sector3_time
FROM LAP_TIMES lt
JOIN RACES r ON lt.race_id = r.race_id
JOIN DRIVERS d ON lt.driver_id = d.driver_id
JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id;

CREATE OR REPLACE VIEW v_pit_stops_detailed AS
SELECT 
    ps.pit_stop_id,
    ps.race_id,
    r.race_name,
    r.season_year,
    ps.driver_id,
    CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
    ps.compound_removed_id,
    tc_rem.compound_name AS compound_removed_name,
    tc_rem.color_code AS compound_removed_color,
    ps.compound_fitted_id,
    tc_fit.compound_name AS compound_fitted_name,
    tc_fit.color_code AS compound_fitted_color,
    ps.lap_number,
    ps.stop_duration,
    ps.pit_loss_time
FROM PIT_STOPS ps
JOIN RACES r ON ps.race_id = r.race_id
JOIN DRIVERS d ON ps.driver_id = d.driver_id
JOIN TYRE_COMPOUNDS tc_rem ON ps.compound_removed_id = tc_rem.compound_id
JOIN TYRE_COMPOUNDS tc_fit ON ps.compound_fitted_id = tc_fit.compound_id;

CREATE OR REPLACE VIEW v_driver_standings AS
SELECT 
    r.season_year,
    d.driver_id,
    CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
    c.name AS team_name,
    SUM(rr.points_scored) AS total_points,
    COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) AS wins,
    COUNT(CASE WHEN rr.finishing_position <= 3 THEN 1 END) AS podiums
FROM RACE_RESULTS rr
JOIN RACES r ON rr.race_id = r.race_id
JOIN DRIVERS d ON rr.driver_id = d.driver_id
JOIN CONSTRUCTORS c ON rr.constructor_id = c.constructor_id
GROUP BY r.season_year, d.driver_id, d.first_name, d.last_name, c.name
ORDER BY r.season_year DESC, total_points DESC;

CREATE OR REPLACE VIEW v_constructor_standings AS
SELECT 
    r.season_year,
    c.constructor_id,
    c.name AS team_name,
    SUM(rr.points_scored) AS total_points,
    COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) AS wins,
    COUNT(CASE WHEN rr.finishing_position <= 3 THEN 1 END) AS podiums
FROM RACE_RESULTS rr
JOIN RACES r ON rr.race_id = r.race_id
JOIN CONSTRUCTORS c ON rr.constructor_id = c.constructor_id
GROUP BY r.season_year, c.constructor_id, c.name
ORDER BY r.season_year DESC, total_points DESC;

-- ==============================================================================
-- ADVANCED DBMS FEATURES: AUDIT LOGGING, TRIGGERS & STORED PROCEDURES
-- ==============================================================================

CREATE TABLE IF NOT EXISTS STRATEGY_NOTES_AUDIT (
    audit_id INT PRIMARY KEY AUTO_INCREMENT,
    note_id INT NOT NULL,
    race_id INT NOT NULL,
    analyst_id INT NOT NULL,
    driver_id INT NOT NULL,
    action_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    old_note_text TEXT,
    new_note_text TEXT,
    old_note_type VARCHAR(50),
    new_note_type VARCHAR(50),
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_note (note_id, changed_at)
);

CREATE TABLE IF NOT EXISTS DRIVER_STANDINGS (
    standing_id INT PRIMARY KEY AUTO_INCREMENT,
    season_year YEAR NOT NULL,
    driver_id INT NOT NULL,
    position INT NOT NULL,
    points DECIMAL(6,2) NOT NULL,
    wins INT NOT NULL DEFAULT 0,
    podiums INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (season_year, driver_id),
    FOREIGN KEY (driver_id) REFERENCES DRIVERS(driver_id)
);

CREATE TABLE IF NOT EXISTS CONSTRUCTOR_STANDINGS (
    standing_id INT PRIMARY KEY AUTO_INCREMENT,
    season_year YEAR NOT NULL,
    constructor_id INT NOT NULL,
    position INT NOT NULL,
    points DECIMAL(6,2) NOT NULL,
    wins INT NOT NULL DEFAULT 0,
    podiums INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (season_year, constructor_id),
    FOREIGN KEY (constructor_id) REFERENCES CONSTRUCTORS(constructor_id)
);

DELIMITER //

-- TRIGGERS: RACE TOTAL LAPS BOUNDS CHECK
DROP TRIGGER IF EXISTS trg_check_lap_number_before_insert //
CREATE TRIGGER trg_check_lap_number_before_insert
BEFORE INSERT ON LAP_TIMES
FOR EACH ROW
BEGIN
    DECLARE v_total_laps INT;
    SELECT total_laps INTO v_total_laps FROM RACES WHERE race_id = NEW.race_id;
    IF v_total_laps IS NOT NULL AND (NEW.lap_number > v_total_laps OR NEW.lap_number < 1) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validation Error: Lap number exceeds race total laps or is less than 1';
    END IF;
END //

DROP TRIGGER IF EXISTS trg_check_lap_number_before_update //
CREATE TRIGGER trg_check_lap_number_before_update
BEFORE UPDATE ON LAP_TIMES
FOR EACH ROW
BEGIN
    DECLARE v_total_laps INT;
    SELECT total_laps INTO v_total_laps FROM RACES WHERE race_id = NEW.race_id;
    IF v_total_laps IS NOT NULL AND (NEW.lap_number > v_total_laps OR NEW.lap_number < 1) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validation Error: Lap number exceeds race total laps or is less than 1';
    END IF;
END //

DROP TRIGGER IF EXISTS trg_check_pit_stop_lap_before_insert //
CREATE TRIGGER trg_check_pit_stop_lap_before_insert
BEFORE INSERT ON PIT_STOPS
FOR EACH ROW
BEGIN
    DECLARE v_total_laps INT;
    SELECT total_laps INTO v_total_laps FROM RACES WHERE race_id = NEW.race_id;
    IF v_total_laps IS NOT NULL AND (NEW.lap_number > v_total_laps OR NEW.lap_number < 1) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validation Error: Pit stop lap number exceeds race total laps or is less than 1';
    END IF;
END //

DROP TRIGGER IF EXISTS trg_check_pit_stop_lap_before_update //
CREATE TRIGGER trg_check_pit_stop_lap_before_update
BEFORE UPDATE ON PIT_STOPS
FOR EACH ROW
BEGIN
    DECLARE v_total_laps INT;
    SELECT total_laps INTO v_total_laps FROM RACES WHERE race_id = NEW.race_id;
    IF v_total_laps IS NOT NULL AND (NEW.lap_number > v_total_laps OR NEW.lap_number < 1) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Validation Error: Pit stop lap number exceeds race total laps or is less than 1';
    END IF;
END //

-- TRIGGERS: FIA F1 TWO-COMPOUND DRY TYRE RULE
DROP TRIGGER IF EXISTS trg_validate_f1_tyre_rule_update //
CREATE TRIGGER trg_validate_f1_tyre_rule_update
BEFORE UPDATE ON RACE_RESULTS
FOR EACH ROW
BEGIN
    DECLARE v_track_condition VARCHAR(20);
    DECLARE v_dry_compound_count INT DEFAULT 0;
    DECLARE v_wet_tyre_count INT DEFAULT 0;
    DECLARE v_laps_run INT DEFAULT 0;

    IF NEW.status = 'Finished' THEN
        SELECT track_condition INTO v_track_condition
        FROM WEATHER_CONDITIONS
        WHERE race_id = NEW.race_id AND session_type = 'Race'
        LIMIT 1;

        IF v_track_condition IS NULL OR v_track_condition = 'Dry' THEN
            SELECT COUNT(*) INTO v_wet_tyre_count
            FROM LAP_TIMES lt
            JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
            WHERE lt.race_id = NEW.race_id AND lt.driver_id = NEW.driver_id
              AND tc.compound_name IN ('Intermediate', 'Wet');

            IF v_wet_tyre_count = 0 THEN
                SELECT COUNT(*) INTO v_laps_run
                FROM LAP_TIMES
                WHERE race_id = NEW.race_id AND driver_id = NEW.driver_id;

                SELECT COUNT(DISTINCT compound_id) INTO v_dry_compound_count
                FROM (
                    SELECT lt.compound_id
                    FROM LAP_TIMES lt
                    JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
                    WHERE lt.race_id = NEW.race_id AND lt.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                    UNION
                    SELECT ps.compound_removed_id AS compound_id
                    FROM PIT_STOPS ps
                    JOIN TYRE_COMPOUNDS tc ON ps.compound_removed_id = tc.compound_id
                    WHERE ps.race_id = NEW.race_id AND ps.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                    UNION
                    SELECT ps.compound_fitted_id AS compound_id
                    FROM PIT_STOPS ps
                    JOIN TYRE_COMPOUNDS tc ON ps.compound_fitted_id = tc.compound_id
                    WHERE ps.race_id = NEW.race_id AND ps.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                ) dry_compounds;

                IF (v_laps_run >= 2 OR (SELECT COUNT(*) FROM PIT_STOPS WHERE race_id = NEW.race_id AND driver_id = NEW.driver_id) > 0)
                   AND v_dry_compound_count < 2 THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'F1 Rule Violation: Driver must use at least two distinct dry tyre compounds in a dry race';
                END IF;
            END IF;
        END IF;
    END IF;
END //

DROP TRIGGER IF EXISTS trg_validate_f1_tyre_rule_insert //
CREATE TRIGGER trg_validate_f1_tyre_rule_insert
BEFORE INSERT ON RACE_RESULTS
FOR EACH ROW
BEGIN
    DECLARE v_track_condition VARCHAR(20);
    DECLARE v_dry_compound_count INT DEFAULT 0;
    DECLARE v_wet_tyre_count INT DEFAULT 0;
    DECLARE v_laps_run INT DEFAULT 0;

    IF NEW.status = 'Finished' THEN
        SELECT track_condition INTO v_track_condition
        FROM WEATHER_CONDITIONS
        WHERE race_id = NEW.race_id AND session_type = 'Race'
        LIMIT 1;

        IF v_track_condition IS NULL OR v_track_condition = 'Dry' THEN
            SELECT COUNT(*) INTO v_wet_tyre_count
            FROM LAP_TIMES lt
            JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
            WHERE lt.race_id = NEW.race_id AND lt.driver_id = NEW.driver_id
              AND tc.compound_name IN ('Intermediate', 'Wet');

            IF v_wet_tyre_count = 0 THEN
                SELECT COUNT(*) INTO v_laps_run
                FROM LAP_TIMES
                WHERE race_id = NEW.race_id AND driver_id = NEW.driver_id;

                SELECT COUNT(DISTINCT compound_id) INTO v_dry_compound_count
                FROM (
                    SELECT lt.compound_id
                    FROM LAP_TIMES lt
                    JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
                    WHERE lt.race_id = NEW.race_id AND lt.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                    UNION
                    SELECT ps.compound_removed_id AS compound_id
                    FROM PIT_STOPS ps
                    JOIN TYRE_COMPOUNDS tc ON ps.compound_removed_id = tc.compound_id
                    WHERE ps.race_id = NEW.race_id AND ps.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                    UNION
                    SELECT ps.compound_fitted_id AS compound_id
                    FROM PIT_STOPS ps
                    JOIN TYRE_COMPOUNDS tc ON ps.compound_fitted_id = tc.compound_id
                    WHERE ps.race_id = NEW.race_id AND ps.driver_id = NEW.driver_id
                      AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
                ) dry_compounds;

                IF (v_laps_run >= 2 OR (SELECT COUNT(*) FROM PIT_STOPS WHERE race_id = NEW.race_id AND driver_id = NEW.driver_id) > 0)
                   AND v_dry_compound_count < 2 THEN
                    SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'F1 Rule Violation: Driver must use at least two distinct dry tyre compounds in a dry race';
                END IF;
            END IF;
        END IF;
    END IF;
END //

-- TRIGGERS: STRATEGY NOTES AUDIT LOGGING
DROP TRIGGER IF EXISTS trg_strategy_notes_audit_insert //
CREATE TRIGGER trg_strategy_notes_audit_insert
AFTER INSERT ON STRATEGY_NOTES
FOR EACH ROW
BEGIN
    INSERT INTO STRATEGY_NOTES_AUDIT (
        note_id, race_id, analyst_id, driver_id,
        action_type, old_note_text, new_note_text,
        old_note_type, new_note_type, changed_by, changed_at
    ) VALUES (
        NEW.note_id, NEW.race_id, NEW.analyst_id, NEW.driver_id,
        'INSERT', NULL, NEW.note_text,
        NULL, NEW.note_type, CURRENT_USER(), CURRENT_TIMESTAMP
    );
END //

DROP TRIGGER IF EXISTS trg_strategy_notes_audit_update //
CREATE TRIGGER trg_strategy_notes_audit_update
AFTER UPDATE ON STRATEGY_NOTES
FOR EACH ROW
BEGIN
    INSERT INTO STRATEGY_NOTES_AUDIT (
        note_id, race_id, analyst_id, driver_id,
        action_type, old_note_text, new_note_text,
        old_note_type, new_note_type, changed_by, changed_at
    ) VALUES (
        NEW.note_id, NEW.race_id, NEW.analyst_id, NEW.driver_id,
        'UPDATE', OLD.note_text, NEW.note_text,
        OLD.note_type, NEW.note_type, CURRENT_USER(), CURRENT_TIMESTAMP
    );
END //

DROP TRIGGER IF EXISTS trg_strategy_notes_audit_delete //
CREATE TRIGGER trg_strategy_notes_audit_delete
AFTER DELETE ON STRATEGY_NOTES
FOR EACH ROW
BEGIN
    INSERT INTO STRATEGY_NOTES_AUDIT (
        note_id, race_id, analyst_id, driver_id,
        action_type, old_note_text, new_note_text,
        old_note_type, new_note_type, changed_by, changed_at
    ) VALUES (
        OLD.note_id, OLD.race_id, OLD.analyst_id, OLD.driver_id,
        'DELETE', OLD.note_text, NULL,
        OLD.note_type, NULL, CURRENT_USER(), CURRENT_TIMESTAMP
    );
END //

-- STORED PROCEDURES
DROP PROCEDURE IF EXISTS sp_recalculate_standings //
CREATE PROCEDURE sp_recalculate_standings(IN p_season_year INT)
BEGIN
    DELETE FROM DRIVER_STANDINGS WHERE season_year = p_season_year;

    INSERT INTO DRIVER_STANDINGS (season_year, driver_id, position, points, wins, podiums)
    SELECT 
        p_season_year,
        d.driver_id,
        ROW_NUMBER() OVER (ORDER BY COALESCE(SUM(rr.points_scored), 0) DESC, COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) DESC) AS position,
        COALESCE(SUM(rr.points_scored), 0) AS points,
        COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) AS wins,
        COUNT(CASE WHEN rr.finishing_position <= 3 THEN 1 END) AS podiums
    FROM DRIVERS d
    JOIN RACE_RESULTS rr ON d.driver_id = rr.driver_id
    JOIN RACES r ON rr.race_id = r.race_id
    WHERE r.season_year = p_season_year
    GROUP BY d.driver_id;

    DELETE FROM CONSTRUCTOR_STANDINGS WHERE season_year = p_season_year;

    INSERT INTO CONSTRUCTOR_STANDINGS (season_year, constructor_id, position, points, wins, podiums)
    SELECT 
        p_season_year,
        c.constructor_id,
        ROW_NUMBER() OVER (ORDER BY COALESCE(SUM(rr.points_scored), 0) DESC, COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) DESC) AS position,
        COALESCE(SUM(rr.points_scored), 0) AS points,
        COUNT(CASE WHEN rr.finishing_position = 1 THEN 1 END) AS wins,
        COUNT(CASE WHEN rr.finishing_position <= 3 THEN 1 END) AS podiums
    FROM CONSTRUCTORS c
    JOIN RACE_RESULTS rr ON c.constructor_id = rr.constructor_id
    JOIN RACES r ON rr.race_id = r.race_id
    WHERE r.season_year = p_season_year
    GROUP BY c.constructor_id;

    SELECT 
        ds.position,
        ds.driver_id,
        CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
        d.nationality,
        ds.points,
        ds.wins,
        ds.podiums,
        ds.last_updated
    FROM DRIVER_STANDINGS ds
    JOIN DRIVERS d ON ds.driver_id = d.driver_id
    WHERE ds.season_year = p_season_year
    ORDER BY ds.position ASC;
END //

DROP PROCEDURE IF EXISTS sp_simulate_strategy //
CREATE PROCEDURE sp_simulate_strategy(IN p_race_id INT, IN p_driver_id INT)
BEGIN
    DECLARE v_race_name VARCHAR(100);
    DECLARE v_total_laps INT;
    DECLARE v_driver_name VARCHAR(100);
    DECLARE v_avg_pace DECIMAL(6,3);
    DECLARE v_laps_completed INT DEFAULT 0;
    DECLARE v_pit_loss DECIMAL(5,2) DEFAULT 22.0;

    SELECT race_name, total_laps INTO v_race_name, v_total_laps
    FROM RACES WHERE race_id = p_race_id;

    SELECT CONCAT(first_name, ' ', last_name) INTO v_driver_name
    FROM DRIVERS WHERE driver_id = p_driver_id;

    SELECT 
        COUNT(*),
        AVG(TIME_TO_SEC(lap_time))
    INTO v_laps_completed, v_avg_pace
    FROM LAP_TIMES
    WHERE race_id = p_race_id AND driver_id = p_driver_id;

    IF v_avg_pace IS NULL OR v_avg_pace = 0 THEN
        SET v_avg_pace = 80.000;
    END IF;

    SELECT 
        p_race_id AS race_id,
        v_race_name AS race_name,
        p_driver_id AS driver_id,
        v_driver_name AS driver_name,
        v_total_laps AS total_laps,
        v_laps_completed AS laps_completed,
        strategy_option,
        tyre_sequence,
        stops_count,
        pit_window_laps,
        ROUND((v_total_laps * (v_avg_pace + pace_delta_sec)) + (stops_count * v_pit_loss), 3) AS projected_race_time_seconds,
        is_recommended,
        strategic_rationale
    FROM (
        SELECT 
            '1-Stop Strategy' AS strategy_option,
            'Medium -> Hard' AS tyre_sequence,
            1 AS stops_count,
            CONCAT('Lap ', ROUND(v_total_laps * 0.38), ' - ', ROUND(v_total_laps * 0.44)) AS pit_window_laps,
            0.15 AS pace_delta_sec,
            TRUE AS is_recommended,
            'Minimizes pit lane loss; high track position retention if tyre degradation is manageable.' AS strategic_rationale
        UNION ALL
        SELECT 
            '2-Stop Strategy' AS strategy_option,
            'Soft -> Medium -> Hard' AS tyre_sequence,
            2 AS stops_count,
            CONCAT('Lap ', ROUND(v_total_laps * 0.22), ' and Lap ', ROUND(v_total_laps * 0.58)) AS pit_window_laps,
            -0.45 AS pace_delta_sec,
            FALSE AS is_recommended,
            'Aggressive pace advantage on fresh compounds; requires 2 pit windows and clean traffic air.' AS strategic_rationale
    ) strategies
    ORDER BY projected_race_time_seconds ASC;
END //

DROP PROCEDURE IF EXISTS sp_validate_race_tyre_rules //
CREATE PROCEDURE sp_validate_race_tyre_rules(IN p_race_id INT)
BEGIN
    DECLARE v_track_condition VARCHAR(20);
    DECLARE v_is_dry BOOLEAN DEFAULT TRUE;

    SELECT track_condition INTO v_track_condition
    FROM WEATHER_CONDITIONS
    WHERE race_id = p_race_id AND session_type = 'Race'
    LIMIT 1;

    IF v_track_condition IN ('Wet', 'Damp') THEN
        SET v_is_dry = FALSE;
    END IF;

    SELECT 
        rr.race_id,
        r.race_name,
        COALESCE(v_track_condition, 'Dry') AS track_condition,
        d.driver_id,
        CONCAT(d.first_name, ' ', d.last_name) AS driver_name,
        c.name AS team_name,
        rr.finishing_position,
        rr.status,
        COALESCE(dry_info.dry_compound_count, 0) AS dry_compounds_used,
        COALESCE(dry_info.compounds_list, 'None') AS compounds_used,
        CASE 
            WHEN NOT v_is_dry THEN 'Exempt (Wet/Damp Session)'
            WHEN rr.status != 'Finished' THEN 'Exempt (Did Not Finish)'
            WHEN COALESCE(dry_info.dry_compound_count, 0) >= 2 THEN 'Compliant'
            ELSE 'VIOLATION (Two dry compounds required)'
        END AS rule_compliance_status,
        CASE 
            WHEN v_is_dry AND rr.status = 'Finished' AND COALESCE(dry_info.dry_compound_count, 0) < 2 THEN 'Disqualification (DSQ)'
            ELSE 'None'
        END AS recommended_action
    FROM RACE_RESULTS rr
    JOIN RACES r ON rr.race_id = r.race_id
    JOIN DRIVERS d ON rr.driver_id = d.driver_id
    JOIN CONSTRUCTORS c ON rr.constructor_id = c.constructor_id
    LEFT JOIN (
        SELECT 
            driver_id,
            COUNT(DISTINCT compound_id) AS dry_compound_count,
            GROUP_CONCAT(DISTINCT compound_name ORDER BY compound_name SEPARATOR ', ') AS compounds_list
        FROM (
            SELECT lt.driver_id, lt.compound_id, tc.compound_name
            FROM LAP_TIMES lt
            JOIN TYRE_COMPOUNDS tc ON lt.compound_id = tc.compound_id
            WHERE lt.race_id = p_race_id AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
            UNION
            SELECT ps.driver_id, ps.compound_removed_id, tc.compound_name
            FROM PIT_STOPS ps
            JOIN TYRE_COMPOUNDS tc ON ps.compound_removed_id = tc.compound_id
            WHERE ps.race_id = p_race_id AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
            UNION
            SELECT ps.driver_id, ps.compound_fitted_id, tc.compound_name
            FROM PIT_STOPS ps
            JOIN TYRE_COMPOUNDS tc ON ps.compound_fitted_id = tc.compound_id
            WHERE ps.race_id = p_race_id AND tc.compound_name IN ('Soft', 'Medium', 'Hard')
        ) driver_compounds
        GROUP BY driver_id
    ) dry_info ON rr.driver_id = dry_info.driver_id
    WHERE rr.race_id = p_race_id
    ORDER BY rr.finishing_position ASC;
END //

DELIMITER ;
