# 使用基础镜像，这里以Ubuntu为例
FROM ubuntu:20.04

# 更新apt源并安装基本软件包
RUN apt-get update && apt-get install -y  openjdk-8-jdk telnet vim && rm -rf /var/lib/apt/lists/*

# 这里是设置了jdk的环境
ENV JAVA_HOME=/usr/lib/jvm/java-1.8.0-openjdk-arm64
ENV PATH="$JAVA_HOME/bin:$PATH"

# 下载HBase的二进制包，这里以HBase 2.6.0为例
ARG HBASE_VERSION=2.6.0
COPY hbase-${HBASE_VERSION}-hadoop3-bin.tar.gz /tmp/

# 解压HBase到/opt/hbase目录
RUN tar xzf /tmp/hbase-${HBASE_VERSION}-hadoop3-bin.tar.gz -C /opt/ \
    && mv /opt/hbase-${HBASE_VERSION}-hadoop3 /opt/hbase \
    && rm -f /tmp/hbase-${HBASE_VERSION}-hadoop3-bin.tar.gz

# 设置HBase的环境变量
ENV PATH="/opt/hbase/bin:$PATH"
ENV HBASE_HOME="/opt/hbase"
ENV HBASE_MANAGES_ZK=false

# 暴露HBase的端口
EXPOSE 60010 16010


# 复制模板配置文件
COPY hbase-site.xml /opt/hbase/conf/hbase-site.xml

# 在容器启动时生成配置文件

CMD ["tail", "-f", "/dev/null"]
