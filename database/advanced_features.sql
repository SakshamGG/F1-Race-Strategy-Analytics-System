-- ==============================================================================
-- ADVANCED DBMS FEATURES: TRIGGERS, AUDIT LOGGING & STORED PROCEDURES
-- ==============================================================================
-- This script contains advanced database logic for the F1 Strategy System:
-- 1. Validation Triggers: Ensures lap and pit stop numbers do not exceed race total_laps.
-- 2. Business Rule Trigger: Enforces FIA F1 two-compound dry tyre rule.
-- 3. Audit Logging: Full audit trail table & triggers for STRATEGY_NOTES changes.
-- 4. Stored Procedures:
--    - sp_recalculate_standings(season_year)
--    - sp_simulate_strategy(race_id, driver_id)
--    - sp_validate_race_tyre_rules(race_id)
-- ==============================================================================

USE f1_strategy_db;

-- ------------------------------------------------------------------------------
-- 1. AUDIT LOGGING TABLE
-- ------------------------------------------------------------------------------

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

-- ------------------------------------------------------------------------------
-- 2. MATERIALIZED / CACHED STANDINGS TABLES
-- ------------------------------------------------------------------------------

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

-- ==============================================================================
-- 3. TRIGGERS: RACE TOTAL LAPS BOUNDS CHECK
-- ==============================================================================

-- Lap Times total_laps check (INSERT)
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

-- Lap Times total_laps check (UPDATE)
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

-- Pit Stops total_laps check (INSERT)
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

-- Pit Stops total_laps check (UPDATE)
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

-- ==============================================================================
-- 4. TRIGGERS: FIA F1 TWO-COMPOUND DRY TYRE RULE
-- ==============================================================================

-- F1 Two-Compound Dry Tyre Rule (UPDATE)
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

-- F1 Two-Compound Dry Tyre Rule (INSERT)
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

-- ==============================================================================
-- 5. TRIGGERS: STRATEGY NOTES AUDIT LOGGING
-- ==============================================================================

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

-- ==============================================================================
-- 6. STORED PROCEDURES
-- ==============================================================================

-- Stored Procedure: Recalculate and Materialize Season Standings
DROP PROCEDURE IF EXISTS sp_recalculate_standings //
CREATE PROCEDURE sp_recalculate_standings(IN p_season_year INT)
BEGIN
    -- 1. Refresh Driver Standings
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

    -- 2. Refresh Constructor Standings
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

    -- 3. Return updated driver standings
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

-- Stored Procedure: Simulate Race Strategy Options
DROP PROCEDURE IF EXISTS sp_simulate_strategy //
CREATE PROCEDURE sp_simulate_strategy(IN p_race_id INT, IN p_driver_id INT)
BEGIN
    DECLARE v_race_name VARCHAR(100);
    DECLARE v_total_laps INT;
    DECLARE v_driver_name VARCHAR(100);
    DECLARE v_avg_pace DECIMAL(6,3);
    DECLARE v_laps_completed INT DEFAULT 0;
    DECLARE v_pit_loss DECIMAL(5,2) DEFAULT 22.0;

    -- Fetch race info
    SELECT race_name, total_laps INTO v_race_name, v_total_laps
    FROM RACES WHERE race_id = p_race_id;

    -- Fetch driver info
    SELECT CONCAT(first_name, ' ', last_name) INTO v_driver_name
    FROM DRIVERS WHERE driver_id = p_driver_id;

    -- Fetch average lap pace and completed laps
    SELECT 
        COUNT(*),
        AVG(TIME_TO_SEC(lap_time))
    INTO v_laps_completed, v_avg_pace
    FROM LAP_TIMES
    WHERE race_id = p_race_id AND driver_id = p_driver_id;

    IF v_avg_pace IS NULL OR v_avg_pace = 0 THEN
        SET v_avg_pace = 80.000;
    END IF;

    -- Model 1-stop vs 2-stop scenarios
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

-- Stored Procedure: Validate F1 Tyre Rule across entire race grid
DROP PROCEDURE IF EXISTS sp_validate_race_tyre_rules //
CREATE PROCEDURE sp_validate_race_tyre_rules(IN p_race_id INT)
BEGIN
    DECLARE v_track_condition VARCHAR(20);
    DECLARE v_is_dry BOOLEAN DEFAULT TRUE;

    -- Determine race condition
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
