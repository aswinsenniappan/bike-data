FROM bitnami/spark:3.5

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Download Kafka connector JARs and MySQL JDBC driver directly into Spark's
# jars directory so no --packages flag or runtime network access is needed.
RUN set -e && \
    BASE=https://repo1.maven.org/maven2 && \
    JARS=/opt/bitnami/spark/jars && \
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY consumer.py start.sh ./
RUN chmod +x start.sh

# config/ is mounted at /config at runtime via docker-compose volume
USER 1001

ENTRYPOINT ["/app/start.sh"]
