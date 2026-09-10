USE f1_strategy_db;

INSERT INTO DRIVERS
(driver_id, first_name, last_name, nationality, date_of_birth)
VALUES
(1, 'Max', 'Verstappen', 'Dutch', '1997-09-30'),
(2, 'Lando', 'Norris', 'British', '1999-11-13'),
(3, 'Charles', 'Leclerc', 'Monégasque', '1997-10-16'),
(4, 'Lewis', 'Hamilton', 'British', '1985-01-07'),
(5, 'George', 'Russell', 'British', '1998-02-15');

INSERT INTO CONSTRUCTORS
(constructor_id, name, nationality, base_location)
VALUES
(1, 'Red Bull Racing', 'Austrian', 'Milton Keynes'),
(2, 'McLaren', 'British', 'Woking'),
(3, 'Ferrari', 'Italian', 'Maranello');

INSERT INTO CIRCUITS
(circuit_id, name, country, city, length_km, number_of_turns)
VALUES
(1, 'Circuit de Monaco', 'Monaco', 'Monte Carlo', 3.337, 19),
(2, 'Silverstone Circuit', 'United Kingdom', 'Silverstone', 5.891, 18),
(3, 'Autodromo Nazionale Monza', 'Italy', 'Monza', 5.793, 11);

INSERT INTO TYRE_COMPOUNDS
(compound_id, compound_name, color_code, expected_lifespan_laps)
VALUES
(1, 'Soft', '#FF0000', 20),
(2, 'Medium', '#FFFF00', 30),
(3, 'Hard', '#FFFFFF', 40),
(4, 'Intermediate', '#00FF00', 25),
(5, 'Wet', '#0000FF', 20);

INSERT INTO ANALYSTS
(analyst_id, name, email, role, access_level)
VALUES
(1, 'Admin User', 'admin@f1strategy.com', 'Admin', 3),
(2, 'Strategy Analyst', 'analyst@f1strategy.com', 'Analyst', 2),
(3, 'Dashboard Viewer', 'viewer@f1strategy.com', 'Viewer', 1);

INSERT INTO RACES
(race_id, circuit_id, season_year, race_name, race_date, total_laps, round_number)
VALUES
(1, 1, 2024, 'Monaco Grand Prix', '2024-05-26', 78, 8),
(2, 2, 2024, 'British Grand Prix', '2024-07-07', 52, 12),
(3, 3, 2024, 'Italian Grand Prix', '2024-09-01', 53, 16);

INSERT INTO DRIVER_CONTRACTS
(contract_id, driver_id, constructor_id, season_year, car_number, start_date, end_date)
VALUES
(1, 1, 1, 2024, 1, '2024-01-01', '2024-12-31'),
(2, 2, 2, 2024, 4, '2024-01-01', '2024-12-31'),
(3, 3, 3, 2024, 16, '2024-01-01', '2024-12-31'),
(4, 4, 3, 2024, 44, '2024-01-01', '2024-12-31'),
(5, 5, 1, 2024, 63, '2024-01-01', '2024-12-31');

INSERT INTO RACE_RESULTS
(result_id, race_id, driver_id, constructor_id,
 grid_position, finishing_position, points_scored,
 status, fastest_lap_time)
VALUES
(1, 1, 1, 1, 6, 6, 8.00, 'Finished', '00:01:15.234'),
(2, 1, 2, 2, 4, 4, 12.00, 'Finished', '00:01:14.876'),
(3, 1, 3, 3, 1, 1, 25.00, 'Finished', '00:01:14.567'),
(4, 1, 4, 3, 3, 3, 15.00, 'Finished', '00:01:14.789'),
(5, 2, 1, 1, 4, 1, 25.00, 'Finished', '00:01:28.456'),
(6, 2, 2, 2, 3, 2, 18.00, 'Finished', '00:01:28.123'),
(7, 2, 5, 1, 8, 5, 10.00, 'Finished', '00:01:29.012'),
(8, 3, 1, 1, 7, 1, 25.00, 'Finished', '00:01:23.456'),
(9, 3, 2, 2, 2, 2, 18.00, 'Finished', '00:01:23.789'),
(10, 3, 3, 3, 4, 4, 12.00, 'Finished', '00:01:24.012');

INSERT INTO LAP_TIMES
(lap_id, race_id, driver_id, compound_id, lap_number,
 lap_time, sector1_time, sector2_time, sector3_time)
VALUES
(1, 1, 3, 1, 1, '00:01:16.234', 18.123, 32.456, 25.655),
(2, 1, 3, 1, 2, '00:01:15.876', 17.987, 32.201, 25.688),
(3, 1, 3, 1, 3, '00:01:15.543', 17.876, 32.123, 25.544),
(4, 1, 3, 1, 4, '00:01:15.234', 17.765, 32.012, 25.457),
(5, 1, 3, 2, 5, '00:01:16.123', 18.001, 32.234, 25.888),
(6, 1, 2, 2, 1, '00:01:17.123', 18.456, 32.789, 25.878),
(7, 1, 2, 2, 2, '00:01:16.789', 18.234, 32.567, 25.988),
(8, 1, 2, 2, 3, '00:01:16.456', 18.123, 32.345, 25.988),
(9, 2, 1, 2, 1, '00:01:30.234', 28.123, 35.456, 26.655),
(10, 2, 1, 2, 2, '00:01:29.876', 27.987, 35.201, 26.688),
(11, 2, 1, 1, 3, '00:01:29.234', 27.765, 35.012, 26.457),
(12, 2, 1, 1, 4, '00:01:28.987', 27.654, 34.901, 26.432);

INSERT INTO PIT_STOPS
(pit_stop_id, race_id, driver_id,
 compound_removed_id, compound_fitted_id,
 lap_number, stop_duration, pit_loss_time)
VALUES
(1, 1, 3, 1, 2, 20, 2.341, 22.456),
(2, 1, 2, 2, 1, 35, 2.512, 23.102),
(3, 2, 1, 2, 1, 18, 2.287, 21.876),
(4, 2, 1, 1, 2, 36, 2.401, 22.234),
(5, 3, 1, 2, 1, 25, 2.198, 21.543);

INSERT INTO WEATHER_CONDITIONS
(weather_id, race_id, session_type,
 temperature_celsius, humidity_percent,
 wind_speed_kmh, track_condition, rainfall_mm)
VALUES
(1, 1, 'Race', 22.5, 68.0, 12.5, 'Dry', 0.0),
(2, 2, 'Race', 18.2, 72.0, 15.3, 'Dry', 0.0),
(3, 3, 'Race', 25.8, 55.0, 9.7, 'Dry', 0.0),
(4, 1, 'Qualifying', 21.8, 70.0, 10.2, 'Dry', 0.0),
(5, 2, 'Qualifying', 17.5, 75.0, 13.8, 'Damp', 1.2);

INSERT INTO STRATEGY_NOTES
(note_id, race_id, analyst_id, driver_id,
 note_text, note_type)
VALUES
(1, 1, 2, 3,
 'Strong performance on the medium compound during the second stint.',
 'Observation'),
(2, 2, 2, 1,
 'Early pit stop provided an effective undercut against the leading driver.',
 'Recommendation'),
(3, 3, 2, 2,
 'Consistent pace throughout the race with good tyre management.',
 'Post-Race Review');