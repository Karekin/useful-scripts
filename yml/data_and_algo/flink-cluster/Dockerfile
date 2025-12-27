FROM flink:1.20.3-java17

# --------------------------------------------------------------------------------
# 1. 定义版本变量 (方便统一管理)
# --------------------------------------------------------------------------------
ARG FLINK_VERSION=1.20.3
ARG ICEBERG_VERSION=1.7.1
ARG FLINK_CDC_VERSION=3.3.0
ARG AMORO_VERSION=0.7.1-incubating
ARG KAFKA_CONN_VERSION=3.4.0-1.20
ARG FLINK_SHADED_HADOOP_VERSION=2.8.3-10.0

# --------------------------------------------------------------------------------
# 2. 创建插件目录
# --------------------------------------------------------------------------------
RUN mkdir -p /opt/flink/plugins/s3-fs-presto

# --------------------------------------------------------------------------------
# 3. 下载 S3 文件系统插件 (必须放 plugins 目录)
#    注意：Flink 官方镜像通常不自带 s3 插件，或者只在 opt 下作为可选组件
#    这里我们显式下载或移动。如果 base 镜像 /opt/flink/opt 下有，可以直接 cp。
#    为了稳健，我们假设从 Maven 中央仓库或 Apache Archive 下载。
# --------------------------------------------------------------------------------
# 检查 /opt/flink/opt 下是否有 s3-fs-presto，如果有则复制，没有则下载 (这里直接用 wget 下载更通用)
RUN wget -P /opt/flink/plugins/s3-fs-presto/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-s3-fs-presto/${FLINK_VERSION}/flink-s3-fs-presto-${FLINK_VERSION}.jar

# --------------------------------------------------------------------------------
# 4. 下载连接器 JARs (放 lib 目录)
# --------------------------------------------------------------------------------

# 4.1 Iceberg Flink Runtime (注意: 1.7.x 开始支持 Flink 1.20)
#     Iceberg 1.7.1 for Flink 1.20
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/iceberg/iceberg-flink-runtime-1.20/${ICEBERG_VERSION}/iceberg-flink-runtime-1.20-${ICEBERG_VERSION}.jar

# 4.2 Iceberg AWS Bundle (用于 S3 FileIO)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/iceberg/iceberg-aws-bundle/${ICEBERG_VERSION}/iceberg-aws-bundle-${ICEBERG_VERSION}.jar

# 4.3 Flink MySQL CDC (FAT JAR)
# 注意：Flink CDC 3.x 以后 GroupId 变更为 org.apache.flink
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-mysql-cdc/${FLINK_CDC_VERSION}/flink-sql-connector-mysql-cdc-${FLINK_CDC_VERSION}.jar

# 4.4 MySQL JDBC Driver (显式依赖，配合 CDC 使用)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/mysql/mysql-connector-java/8.0.27/mysql-connector-java-8.0.27.jar

# 4.5 Kafka Connector (可选，作为 MQ 接入储备)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONN_VERSION}/flink-sql-connector-kafka-${KAFKA_CONN_VERSION}.jar

# 4.6 Flink Shaded Hadoop (解决 ClassNotFoundException: org.apache.hadoop.conf.Configuration)
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/flink/flink-shaded-hadoop-2-uber/${FLINK_SHADED_HADOOP_VERSION}/flink-shaded-hadoop-2-uber-${FLINK_SHADED_HADOOP_VERSION}.jar

# 4.7 Amoro Flink Runtime (支持 type='amoro' 的 Catalog)
# 注意：使用 1.17 版本的 Runtime，这是目前 Maven 上可用的较新版本，通常可以兼容 Flink 1.20
RUN wget -P /opt/flink/lib/ \
    https://repo.maven.apache.org/maven2/org/apache/amoro/amoro-mixed-format-flink-runtime-1.17/${AMORO_VERSION}/amoro-mixed-format-flink-runtime-1.17-${AMORO_VERSION}.jar

# --------------------------------------------------------------------------------
# 5. 配置与权限
# --------------------------------------------------------------------------------
# 确保所有下载的 JAR 都有读取权限
RUN chmod 644 /opt/flink/lib/*.jar && \
    chmod 644 /opt/flink/plugins/s3-fs-presto/*.jar

# 切换回 flink 用户 (官方镜像默认用户)
USER flink

