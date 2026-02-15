from pathlib import Path

import yaml
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, from_json
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

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

    for key, val in secrets.items():
        if key in cfg and isinstance(cfg[key], dict) and isinstance(val, dict):
            cfg[key].update(val)
        else:
            cfg[key] = val

    return cfg


# ── Schemas ────────────────────────────────────────────────────────────────────
# One StructType per feed name. Only fields that get dedicated SQL columns are
# listed here; the full payload is always captured in raw_json separately.

STATION_INFORMATION_SCHEMA = StructType([
    StructField("station_id", StringType(),  nullable=True),
    StructField("name",       StringType(),  nullable=True),
    StructField("lat",        DoubleType(),  nullable=True),
    StructField("lon",        DoubleType(),  nullable=True),
    StructField("capacity",   IntegerType(), nullable=True),
    StructField("region_id",  StringType(),  nullable=True),
])

STATION_STATUS_SCHEMA = StructType([
    StructField("station_id",          StringType(),  nullable=True),
    StructField("num_bikes_available", IntegerType(), nullable=True),
    StructField("num_bikes_disabled",  IntegerType(), nullable=True),
    StructField("num_docks_available", IntegerType(), nullable=True),
    StructField("num_docks_disabled",  IntegerType(), nullable=True),
    StructField("is_installed",        BooleanType(), nullable=True),
    StructField("is_renting",          BooleanType(), nullable=True),
    StructField("is_returning",        BooleanType(), nullable=True),
    StructField("last_reported",       LongType(),    nullable=True),
])

FEED_SCHEMAS = {
    "station_information": STATION_INFORMATION_SCHEMA,
    "station_status":      STATION_STATUS_SCHEMA,
}

# ── Bootstrap ──────────────────────────────────────────────────────────────────

cfg = load_config()

kafka_broker   = cfg["kafka"]["broker"]
mysql_host     = cfg["mysql"]["host"]
mysql_port     = cfg["mysql"]["port"]
mysql_database = cfg["mysql"]["database"]
mysql_user     = cfg["mysql"]["user"]
mysql_password = cfg["mysql"]["password"]
checkpoint_dir = cfg["spark"]["checkpoint_dir"]
trigger_secs   = cfg["spark"]["trigger_interval_seconds"]

JDBC_URL = (
    f"jdbc:mysql://{mysql_host}:{mysql_port}/{mysql_database}"
    "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"
)

JDBC_PROPS = {
    "user":     mysql_user,
    "password": mysql_password,
    "driver":   "com.mysql.cj.jdbc.Driver",
}

spark = (
    SparkSession.builder
    .appName("GBFSConsumer")
    .config("spark.ui.enabled", "false")
    .config("spark.driver.memory", cfg["spark"]["driver_memory"])
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")


# ── Query builder ──────────────────────────────────────────────────────────────

def build_query(feed: dict):
    """Build and start one Structured Streaming query for a single feed."""
    name   = feed["name"]
    topic  = feed["topic"]
    table  = feed["table"]
    schema = FEED_SCHEMAS[name]

    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_broker)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    parsed = (
        raw.select(
            col("value").cast("string").alias("raw_json"),
            from_json(col("value").cast("string"), schema).alias("s"),
        )
        .select(col("s.*"), col("raw_json"), current_timestamp().alias("ingested_at"))
    )

    def write_batch(batch_df, epoch_id):
        batch_df.write.jdbc(
            url=JDBC_URL,
            table=table,
            mode="append",
            properties=JDBC_PROPS,
        )

    return (
        parsed.writeStream
        .foreachBatch(write_batch)
        .option("checkpointLocation", f"{checkpoint_dir}/{name}")
        .trigger(processingTime=f"{trigger_secs} seconds")
        .start()
    )


# ── Start all queries ──────────────────────────────────────────────────────────

queries = [build_query(feed) for feed in cfg["feeds"]]

spark.streams.awaitAnyTermination()
