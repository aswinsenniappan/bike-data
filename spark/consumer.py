from pathlib import Path

import yaml
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, current_timestamp, from_json
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
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


cfg = load_config()

kafka_broker    = cfg["kafka"]["broker"]
kafka_topic     = cfg["kafka"]["topic"]
mysql_host      = cfg["mysql"]["host"]
mysql_port      = cfg["mysql"]["port"]
mysql_database  = cfg["mysql"]["database"]
mysql_user      = cfg["mysql"]["user"]
mysql_password  = cfg["mysql"]["password"]
checkpoint_dir  = cfg["spark"]["checkpoint_dir"]
trigger_secs    = cfg["spark"]["trigger_interval_seconds"]

JDBC_URL = (
    f"jdbc:mysql://{mysql_host}:{mysql_port}/{mysql_database}"
    "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"
)

JDBC_PROPS = {
    "user":     mysql_user,
    "password": mysql_password,
    "driver":   "com.mysql.cj.jdbc.Driver",
}

# Named columns written to dedicated SQL columns;
# the full original payload is also preserved in raw_json.
STATION_SCHEMA = StructType([
    StructField("station_id", StringType(),  nullable=True),
    StructField("name",       StringType(),  nullable=True),
    StructField("lat",        DoubleType(),  nullable=True),
    StructField("lon",        DoubleType(),  nullable=True),
    StructField("capacity",   IntegerType(), nullable=True),
    StructField("region_id",  StringType(),  nullable=True),
])


def write_batch(batch_df, epoch_id):
    batch_df.write.jdbc(
        url=JDBC_URL,
        table="station_information",
        mode="append",
        properties=JDBC_PROPS,
    )


spark = (
    SparkSession.builder
    .appName("GBFSStationConsumer")
    .config("spark.ui.enabled", "false")
    .config("spark.driver.memory", cfg["spark"]["driver_memory"])
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_broker)
    .option("subscribe", kafka_topic)
    .option("startingOffsets", "latest")
    .option("failOnDataLoss", "false")
    .load()
)

parsed = (
    raw.select(
        col("value").cast("string").alias("raw_json"),
        from_json(col("value").cast("string"), STATION_SCHEMA).alias("s"),
    )
    .select(
        col("s.station_id"),
        col("s.name"),
        col("s.lat"),
        col("s.lon"),
        col("s.capacity"),
        col("s.region_id"),
        col("raw_json"),
        current_timestamp().alias("ingested_at"),
    )
)

query = (
    parsed.writeStream
    .foreachBatch(write_batch)
    .option("checkpointLocation", checkpoint_dir)
    .trigger(processingTime=f"{trigger_secs} seconds")
    .start()
)

query.awaitTermination()
