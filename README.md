# Bike Data Pipeline

Local GBFS data pipeline: polls the Citi Bike / Lyft station feed every 60 seconds,
streams records through Kafka, and persists them to MySQL via a PySpark Structured
Streaming job — all running in Docker.

```
GBFS API → Python Producer → Kafka (KRaft) → PySpark → MySQL
```

---

## Prerequisites

- Docker Engine 20.10+
- Docker Compose plugin (`docker compose`)
- `config/secrets.yaml` (copy from `config/secrets.yaml.example` and fill in passwords)

---

## Quick Start

```bash
# First run — build images and start all services
docker compose up --build -d

# Subsequent runs — start without rebuilding
docker compose up -d
```

Services take ~30 s to become healthy (Kafka and MySQL run health checks before
the producer and Spark containers start).

---

## Stop / Restart

```bash
# Stop all containers (data is preserved in Docker volumes)
docker compose down

# Stop and wipe all data (Kafka logs, MySQL rows, Spark checkpoints)
docker compose down -v
```

---

## Logs

```bash
# Follow all services
docker compose logs -f

# Follow a specific service
docker compose logs -f producer
docker compose logs -f spark
docker compose logs -f kafka
docker compose logs -f mysql
```

---

## Verify the Pipeline

```bash
# 1. Check all containers are healthy/running
docker compose ps

# 2. Confirm producer is publishing
docker compose logs producer --tail=5

# 3. Query MySQL row count (grows every ~60 s)
docker compose exec mysql \
  mysql -u bikeuser -pbikepass bike_data \
  -e "SELECT COUNT(*) AS rows, MAX(ingested_at) AS latest FROM station_information;"

# 4. Browse the Kafka topic manually
docker compose exec kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic gbfs-stations \
  --from-beginning \
  --max-messages 1
```

---

## Configuration

| File | Purpose | Committed |
|---|---|---|
| `config/config.yaml` | All non-sensitive settings (URLs, intervals, ports) | Yes |
| `config/secrets.yaml` | Database passwords | **No** (gitignored) |
| `config/secrets.yaml.example` | Template for secrets | Yes |
| `.env` | Docker infrastructure variables (MySQL container setup) | **No** (gitignored) |

To change the poll interval or GBFS feed URL, edit `config/config.yaml` and restart:

```bash
docker compose restart producer
```

---

## Services

| Container | Image | Role |
|---|---|---|
| `kafka` | `apache/kafka:3.9.0` | Message broker (KRaft, no Zookeeper) |
| `mysql` | `mysql:8.0` | Persistent storage |
| `producer` | `python:3.11-slim` | Polls GBFS API, publishes to Kafka |
| `spark` | `python:3.11-slim` + JRE + PySpark | Consumes Kafka, writes to MySQL |
