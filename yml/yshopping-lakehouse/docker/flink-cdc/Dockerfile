FROM flink:2.2.1-scala_2.12-java17

USER root

ARG FLINK_CDC_VERSION=3.6.0
ARG FLINK_CDC_CONNECTOR_VERSION=3.6.0-2.2
ARG FLINK_SHADED_GUAVA_VERSION=31.1-jre-17.0
ARG MYSQL_CONNECTOR_VERSION=8.4.0

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gettext-base; \
    rm -rf /var/lib/apt/lists/*; \
    wget -q "https://dlcdn.apache.org/flink/flink-cdc-${FLINK_CDC_VERSION}/flink-cdc-${FLINK_CDC_VERSION}-2.2-bin.tar.gz" -O /tmp/flink-cdc.tgz; \
    tar -xzf /tmp/flink-cdc.tgz -C /opt; \
    mv "/opt/flink-cdc-${FLINK_CDC_CONNECTOR_VERSION}" /opt/flink-cdc; \
    wget -q "https://repo1.maven.org/maven2/org/apache/flink/flink-cdc-pipeline-connector-mysql/${FLINK_CDC_CONNECTOR_VERSION}/flink-cdc-pipeline-connector-mysql-${FLINK_CDC_CONNECTOR_VERSION}.jar" -P /opt/flink-cdc/lib; \
    wget -q "https://repo1.maven.org/maven2/org/apache/flink/flink-cdc-pipeline-connector-starrocks/${FLINK_CDC_CONNECTOR_VERSION}/flink-cdc-pipeline-connector-starrocks-${FLINK_CDC_CONNECTOR_VERSION}.jar" -P /opt/flink-cdc/lib; \
    wget -q "https://repo1.maven.org/maven2/org/apache/flink/flink-shaded-guava/${FLINK_SHADED_GUAVA_VERSION}/flink-shaded-guava-${FLINK_SHADED_GUAVA_VERSION}.jar" -P "${FLINK_HOME}/lib"; \
    wget -q "https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/${MYSQL_CONNECTOR_VERSION}/mysql-connector-j-${MYSQL_CONNECTOR_VERSION}.jar" -P "${FLINK_HOME}/lib"; \
    cp "/opt/flink-cdc/lib/flink-cdc-dist-${FLINK_CDC_CONNECTOR_VERSION}.jar" "${FLINK_HOME}/lib/"; \
    rm /tmp/flink-cdc.tgz; \
    chown -R flink:flink /opt/flink-cdc "${FLINK_HOME}"

ENV FLINK_CDC_HOME=/opt/flink-cdc

USER flink
