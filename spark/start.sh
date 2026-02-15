#!/bin/bash
set -e
exec spark-submit \
    --master local[2] \
    --conf spark.driver.memory=1g \
    /app/consumer.py
