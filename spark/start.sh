#!/bin/bash
set -e
exec /opt/bitnami/spark/bin/spark-submit \
    --master local[2] \
    --conf spark.driver.memory=1g \
    /app/consumer.py
