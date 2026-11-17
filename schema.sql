-- Packet Pong database schema (NAS MariaDB, database Sandbox5)
-- Run with: mariadb -h 192.168.5.254 -P 3306 -u Sandbox5 -p Sandbox5 < schema.sql

CREATE TABLE IF NOT EXISTS matches (
    match_id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    started_at    DATETIME     NOT NULL,
    ended_at      DATETIME     NULL,
    player_a      VARCHAR(32)  NOT NULL,
    player_b      VARCHAR(32)  NOT NULL,
    score_a       TINYINT UNSIGNED NOT NULL DEFAULT 0,
    score_b       TINYINT UNSIGNED NOT NULL DEFAULT 0,
    winner        ENUM('A','B') NULL,
    longest_rally SMALLINT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS points (
    point_id      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    match_id      INT UNSIGNED NOT NULL,
    scored_at     DATETIME     NOT NULL,
    scorer        ENUM('A','B') NOT NULL,
    rally_length  SMALLINT UNSIGNED NOT NULL,
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
) ENGINE=InnoDB;
