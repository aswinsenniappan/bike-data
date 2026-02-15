FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        default-jre-headless \
        curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Resolve pyspark's bundled jars directory and drop in the extra JARs needed
# for Kafka Structured Streaming and MySQL JDBC.
RUN JARS=$(python3 -c "import pyspark, os; print(os.path.join(os.path.dirname(pyspark.__file__), 'jars'))") && \
    BASE=https://repo1.maven.org/maven2 && \
    curl -fsSL "$BASE/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.0/spark-sql-kafka-0-10_2.12-3.5.0.jar" \
         -o "$JARS/spark-sql-kafka-0-10_2.12-3.5.0.jar" && \
    curl -fsSL "$BASE/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.0/spark-token-provider-kafka-0-10_2.12-3.5.0.jar" \
         -o "$JARS/spark-token-provider-kafka-0-10_2.12-3.5.0.jar" && \
    curl -fsSL "$BASE/org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar" \
         -o "$JARS/kafka-clients-3.4.1.jar" && \
    curl -fsSL "$BASE/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar" \
         -o "$JARS/commons-pool2-2.11.1.jar" && \
    curl -fsSL "$BASE/com/mysql/mysql-connector-j/8.3.0/mysql-connector-j-8.3.0.jar" \
         -o "$JARS/mysql-connector-j-8.3.0.jar"

WORKDIR /app

COPY consumer.py start.sh ./
RUN chmod +x start.sh

# config/ is mounted at /config at runtime via docker-compose volume
ENTRYPOINT ["/app/start.sh"]
