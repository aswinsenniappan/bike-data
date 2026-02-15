-- Runs automatically on first MySQL startup via docker-entrypoint-initdb.d

CREATE DATABASE IF NOT EXISTS bike_data;
USE bike_data;

CREATE TABLE IF NOT EXISTS station_information (
    id            BIGINT        NOT NULL AUTO_INCREMENT,
    station_id    VARCHAR(64)   NOT NULL,
    name          VARCHAR(256)  NOT NULL,
    lat           DOUBLE        NOT NULL,
    lon           DOUBLE        NOT NULL,
    capacity      INT           DEFAULT NULL,
    region_id     VARCHAR(64)   DEFAULT NULL,
    raw_json      JSON          NOT NULL,
    ingested_at   TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_station_id  (station_id),
    INDEX idx_ingested_at (ingested_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS station_status (
    id                   BIGINT      NOT NULL AUTO_INCREMENT,
    station_id           VARCHAR(64) NOT NULL,
    num_bikes_available  INT         DEFAULT NULL,
    num_bikes_disabled   INT         DEFAULT NULL,
    num_docks_available  INT         DEFAULT NULL,
    num_docks_disabled   INT         DEFAULT NULL,
    is_installed         TINYINT(1)  DEFAULT NULL,
    is_renting           TINYINT(1)  DEFAULT NULL,
    is_returning         TINYINT(1)  DEFAULT NULL,
    last_reported        BIGINT      DEFAULT NULL,
    raw_json             JSON        NOT NULL,
    ingested_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_station_id    (station_id),
    INDEX idx_ingested_at   (ingested_at),
    INDEX idx_last_reported (last_reported)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
