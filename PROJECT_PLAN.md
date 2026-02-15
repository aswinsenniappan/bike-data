# Bike Data Pipeline — Project Plan

## Overview

A local data pipeline that polls GBFS (General Bikeshare Feed Specification) APIs,
streams data through Apache Kafka, and persists it to MySQL via a PySpark consumer.
Everything runs in Docker on a single machine.

**Starting endpoint:** `https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_information.json`
**Target endpoint:** `https://gbfs.citibikenyc.com/gbfs/gbfs.json` (phase 2)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Network                       │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌────────────────────┐ │
│  │  Python  │    │  Kafka   │    │   PySpark          │ │
│  │ Producer │───▶│ (KRaft)  │───▶│   Consumer         │ │
│  │          │    │          │    │                    │ │
│  │ polls    │    │ topic:   │    │ structured         │ │
│  │ GBFS API │    │ gbfs-    │    │ streaming          │ │
│  │ every 60s│    │ stations │    │                    │ │
│  └──────────┘    └──────────┘    └────────┬───────────┘ │
│                                           │             │
│                                  ┌────────▼───────────┐ │
│                                  │      MySQL         │ │
│                                  │  station_info      │ │
│                                  │  table             │ │
│                                  └────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Resource Budget

| Component      | Docker Image         | RAM Limit | Disk (approx) |
|----------------|----------------------|-----------|---------------|
| Kafka (KRaft)  | bitnami/kafka        | 512MB     | ~500MB image  |
| MySQL 8        | mysql:8.0            | 512MB     | ~600MB image  |
| Producer       | python:3.11-slim     | 128MB     | ~200MB image  |
| Spark          | bitnami/spark:3.5    | 2GB       | ~1.5GB image  |
| **Total**      |                      | **~3.2GB**| **~3GB**      |

Kafka 24h log retention with 60s poll interval and small JSON payloads: ~50MB/day.
MySQL data: negligible growth for station_information (static-ish data).
Well within 16GB RAM and 50GB SSD constraints.

---

## Project Directory Structure

```
bike_data/
├── docker-compose.yml
├── .env                          # Environment variables (ports, credentials)
├── PROJECT_PLAN.md               # This file
│
├── producer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── producer.py               # Polls GBFS API, publishes to Kafka
│
├── spark/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── consumer.py               # PySpark structured streaming job
│
└── mysql/
    └── init.sql                  # Schema creation script
```

---

## Milestones

### Phase 1 — Infrastructure (Docker Compose)

- [ ] Write `docker-compose.yml` with:
  - Kafka in KRaft mode (no Zookeeper, saves RAM)
  - MySQL 8 with a named volume
  - Producer service
  - Spark service
  - A shared Docker bridge network
- [ ] Write `.env` for all configurable values (ports, credentials, topic name)
- [ ] Verify all containers start cleanly with `docker compose up`

### Phase 2 — MySQL Schema

- [ ] Write `mysql/init.sql` to create the `bike_data` database and
  `station_information` table:
  - `id` BIGINT AUTO_INCREMENT PK
  - `station_id` VARCHAR — unique station identifier from feed
  - `name` VARCHAR
  - `lat` DOUBLE
  - `lon` DOUBLE
  - `capacity` INT
  - `region_id` VARCHAR (nullable)
  - `raw_json` JSON — full station record for forward compatibility
  - `ingested_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### Phase 3 — Python Kafka Producer

- [ ] Write `producer/producer.py`:
  - Uses `requests` to fetch GBFS station_information JSON every 60s
  - Iterates each station record in `data.stations[]`
  - Publishes each station as a separate Kafka message (key = `station_id`)
  - Serialises payload as JSON string
- [ ] Write `producer/Dockerfile` based on `python:3.11-slim`
- [ ] Dependencies: `requests`, `kafka-python`
- [ ] Add basic error handling: log fetch failures, retry next cycle

### Phase 4 — PySpark Consumer

- [ ] Write `spark/consumer.py`:
  - Uses PySpark Structured Streaming with Kafka source
  - Reads from topic `gbfs-stations`
  - Defines schema matching the GBFS station_information record
  - Parses Kafka value (JSON string) into structured columns
  - Writes micro-batches to MySQL via JDBC (`foreachBatch` sink)
- [ ] Write `spark/Dockerfile` based on `bitnami/spark:3.5`
- [ ] Dependencies: `pyspark`, MySQL JDBC connector JAR
- [ ] Checkpoint location: `/tmp/spark-checkpoint` (inside container)

### Phase 5 — End-to-End Test

- [ ] `docker compose up --build`
- [ ] Verify producer logs show successful publishes
- [ ] Verify Spark logs show micro-batch processing
- [ ] Query MySQL: `SELECT COUNT(*), MAX(ingested_at) FROM station_information;`
- [ ] Wait 2+ minutes, confirm new rows are being inserted

### Phase 6 — Expand to Citi Bike Full Feed (Future)

- [ ] Add additional GBFS endpoints from `https://gbfs.citibikenyc.com/gbfs/gbfs.json`:
  - `station_status` — real-time availability
  - `free_bike_status` — dockless bikes (if available)
- [ ] Add corresponding MySQL tables
- [ ] Add Spark jobs or extend existing one for new topics
- [ ] Consider partitioning MySQL tables by date for larger datasets

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Kafka mode | KRaft (no Zookeeper) | Saves ~256MB RAM, simpler setup |
| Message granularity | One Kafka message per station | Better parallelism, cleaner offsets |
| Spark mode | Local (`local[2]`) | Single machine, no cluster overhead |
| Spark sink | `foreachBatch` → JDBC | Simplest reliable write to MySQL |
| Kafka retention | 24 hours | Bounded disk use; MySQL is source of truth |
| MySQL | Keep all rows | Full history for future analysis |

---

## Environment Variables (`.env`)

```
KAFKA_BROKER=kafka:9092
KAFKA_TOPIC=gbfs-stations
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=bike_data
MYSQL_USER=bikeuser
MYSQL_PASSWORD=bikepass
MYSQL_ROOT_PASSWORD=rootpass
GBFS_URL=https://gbfs.lyft.com/gbfs/1.1/bkn/en/station_information.json
POLL_INTERVAL_SECONDS=60
```

---

## Useful Commands

```bash
# Start all services
docker compose up --build -d

# Tail producer logs
docker compose logs -f producer

# Tail spark logs
docker compose logs -f spark

# Connect to MySQL
docker compose exec mysql mysql -u bikeuser -pbikepass bike_data

# List Kafka topics
docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

# Consume Kafka topic manually
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic gbfs-stations \
  --from-beginning

# Stop everything
docker compose down

# Stop and remove volumes (wipes MySQL data)
docker compose down -v
```

---

## Notes for Claude Code

- Always check `docker compose ps` before assuming services are running.
- The MySQL JDBC JAR must be available inside the Spark container; pin the version
  in the Dockerfile (e.g., `mysql-connector-j-8.3.0.jar`).
- Spark structured streaming requires a checkpoint directory; ensure it persists
  across container restarts by mounting a volume or using a local path.
- The GBFS `station_information` feed is relatively static (stations don't change
  often). `station_status` (phase 6) is the high-churn feed.
- Use `bitnami/kafka` with env var `KAFKA_CFG_PROCESS_ROLES=broker,controller`
  for KRaft mode — no Zookeeper image needed.
- Kafka advertised listener inside Docker must use the service name `kafka`, not
  `localhost`, for inter-container communication.
