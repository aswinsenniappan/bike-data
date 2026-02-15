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
