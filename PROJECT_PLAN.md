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
├── .env                          # Docker infra credentials (gitignored)
├── .env.example                  # Template for .env
├── PROJECT_PLAN.md               # This file
│
├── config/
│   ├── config.yaml               # Non-sensitive settings (committed)
│   ├── secrets.yaml              # Passwords (gitignored)
│   └── secrets.yaml.example      # Template for secrets.yaml
│
├── producer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── producer.py               # Polls GBFS API, publishes to Kafka
│
├── spark/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── start.sh                  # spark-submit entrypoint
│   └── consumer.py               # PySpark structured streaming job
│
└── mysql/
    └── init.sql                  # Schema creation script
```

---

## Milestones

### Phase 1 — Infrastructure (Docker Compose) ✅

- [x] Write `docker-compose.yml` with Kafka (KRaft), MySQL 8, producer, spark, shared network
- [x] Write `config/config.yaml` (settings) and `config/secrets.yaml` (credentials, gitignored)
- [x] Placeholder Dockerfiles for producer and spark

### Phase 2 — MySQL Schema ✅

- [x] Write `mysql/init.sql` — `station_information` table with all required columns

### Phase 3 — Python Kafka Producer ✅

- [x] `producer/producer.py` — loads config from `/config`, polls GBFS every 60 s,
  publishes each station as a Kafka message keyed by `station_id`
- [x] `producer/Dockerfile` — `python:3.11-slim`, pip installs `requests`, `kafka-python`, `pyyaml`
- [x] Startup retry loop for Kafka not-yet-ready condition

### Phase 4 — PySpark Consumer ✅

- [x] `spark/consumer.py` — loads config from `/config`, Structured Streaming from Kafka,
  `foreachBatch` → JDBC → MySQL
- [x] `spark/Dockerfile` — `bitnami/spark:3.5`, pre-downloads all required JARs at build time
- [x] `spark/start.sh` — entrypoint that calls `spark-submit --master local[2]`

### Phase 5 — End-to-End Test ✅

- [x] `docker compose up --build`
- [x] Producer logs: "Published 2354 stations → topic 'gbfs-stations'" every 60 s
- [x] Spark logs: streaming query started, micro-batches processing
- [x] MySQL: 4,708 rows after 2 poll cycles, `MAX(ingested_at)` advancing
- [x] Pipeline confirmed working end-to-end

**Image notes (resolved during Phase 5):**
- `bitnami/kafka` and `bitnami/spark` unavailable on Docker Hub/GHCR → switched to
  `apache/kafka:3.9.0` (official) and `python:3.11-slim` + `pyspark==3.5.0` via pip
- Kafka healthcheck must use full path `/opt/kafka/bin/kafka-topics.sh` (not in `/bin/sh` PATH)

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
| Kafka image | `apache/kafka:3.9.0` | Official image; bitnami unavailable on Docker Hub |
| Kafka mode | KRaft (no Zookeeper) | Saves ~256MB RAM, simpler setup |
| Spark image | `python:3.11-slim` + JRE + `pyspark==3.5.0` pip | Simpler than apache/spark; no entrypoint conflicts |
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
