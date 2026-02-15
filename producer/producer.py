import json
import logging
import time
from pathlib import Path

import requests
import yaml
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

CONFIG_DIR = Path("/config")


def load_config() -> dict:
    with open(CONFIG_DIR / "config.yaml") as f:
        cfg = yaml.safe_load(f)

    secrets_path = CONFIG_DIR / "secrets.yaml"
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"{secrets_path} not found. "
            "Copy config/secrets.yaml.example → config/secrets.yaml and fill in values."
        )
    with open(secrets_path) as f:
        secrets = yaml.safe_load(f)

    # Merge secrets into cfg (secrets override matching top-level keys)
    for key, val in secrets.items():
        if key in cfg and isinstance(cfg[key], dict) and isinstance(val, dict):
            cfg[key].update(val)
        else:
            cfg[key] = val

    return cfg


def make_producer(broker: str) -> KafkaProducer:
    """Connect to Kafka, retrying until the broker is ready."""
    while True:
        try:
            producer = KafkaProducer(
                bootstrap_servers=broker,
                key_serializer=str.encode,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks="all",
                retries=3,
            )
            log.info("Connected to Kafka at %s", broker)
            return producer
        except NoBrokersAvailable:
            log.warning("Kafka broker not ready — retrying in 5 s...")
            time.sleep(5)


def fetch_stations(url: str) -> list:
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()["data"]["stations"]


def main() -> None:
    cfg = load_config()

    kafka_broker    = cfg["kafka"]["broker"]
    kafka_topic     = cfg["kafka"]["topic"]
    gbfs_url        = cfg["gbfs"]["url"]
    poll_interval   = cfg["gbfs"]["poll_interval_seconds"]

    producer = make_producer(kafka_broker)
    log.info("Polling %s every %d s", gbfs_url, poll_interval)

    while True:
        try:
            stations = fetch_stations(gbfs_url)
            for station in stations:
                producer.send(kafka_topic, key=station["station_id"], value=station)
            producer.flush()
            log.info("Published %d stations → topic '%s'", len(stations), kafka_topic)
        except requests.RequestException as exc:
            log.error("HTTP error fetching GBFS feed: %s", exc)
        except Exception as exc:
            log.error("Unexpected error in poll cycle: %s", exc)

        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
