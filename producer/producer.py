import json
import logging
import threading
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


def poll_feed(producer: KafkaProducer, feed: dict) -> None:
    """Poll one GBFS feed forever. Runs in its own daemon thread."""
    name     = feed["name"]
    url      = feed["url"]
    topic    = feed["topic"]
    interval = feed["poll_interval_seconds"]

    log.info("[%s] Starting — every %d s → topic '%s'", name, interval, topic)
    while True:
        try:
            stations = fetch_stations(url)
            for station in stations:
                producer.send(topic, key=station["station_id"], value=station)
            producer.flush()
            log.info("[%s] Published %d records → topic '%s'", name, len(stations), topic)
        except requests.RequestException as exc:
            log.error("[%s] HTTP error fetching feed: %s", name, exc)
        except Exception as exc:
            log.error("[%s] Unexpected error in poll cycle: %s", name, exc)

        time.sleep(interval)


def main() -> None:
    cfg          = load_config()
    kafka_broker = cfg["kafka"]["broker"]
    producer     = make_producer(kafka_broker)

    threads = [
        threading.Thread(
            target=poll_feed,
            args=(producer, feed),
            name=f"poller-{feed['name']}",
            daemon=True,
        )
        for feed in cfg["feeds"]
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
