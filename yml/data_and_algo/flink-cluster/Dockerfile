FROM flink:1.17.2-java11

# 1. 定义版本变量
ARG FLINK_VERSION=1.17.2
ARG ICEBERG_VERSION=1.4.3
ARG FLINK_CDC_VERSION=2.4.2
ARG AMORO_VERSION=0.7.0-incubating

# 2. 创建插件目录
RUN mkdir -p /opt/flink/plugins/s3-fs-presto

# 3. 下载 S3 文件系统插件
RUN wget -P /opt/flink/plugins/s3-fs-presto/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-s3-fs-presto/${FLINK_VERSION}/flink-s3-fs-presto-${FLINK_VERSION}.jar

# 4. 下载连接器 JARs (精简版：仅保留 Uber JAR 和必需驱动)

# 4.1 Amoro Flink Runtime (核心胖包，已包含 Shaded Iceberg/Guava/Jackson/Thrift 等)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/amoro/amoro-mixed-format-flink-runtime-1.17/${AMORO_VERSION}/amoro-mixed-format-flink-runtime-1.17-${AMORO_VERSION}.jar

# 4.2 Iceberg AWS Bundle (用于 S3 FileIO 支持)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar

# 4.3 Flink MySQL CDC (适配 Flink 1.17)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/com/ververica/flink-sql-connector-mysql-cdc/${FLINK_CDC_VERSION}/flink-sql-connector-mysql-cdc-${FLINK_CDC_VERSION}.jar

# 4.4 MySQL JDBC Driver
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/mysql/mysql-connector-java/8.0.27/mysql-connector-java-8.0.27.jar

# --------------------------------------------------------------------------------
# 5. 配置与权限
# --------------------------------------------------------------------------------
# 确保所有下载的 JAR 都有读取权限
RUN chmod 644 /opt/flink/lib/*.jar && \
    chmod 644 /opt/flink/plugins/s3-fs-presto/*.jar

# 切换回 flink 用户
USER flink
