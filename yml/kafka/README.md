# 如何部署Kafka测试环境

```
version: '3.7'
services:
  zookeeper:
    image: bitnami/zookeeper:latest
    container_name: learn-zookeeper
    ports:
      - "2181:2181"
    environment:
      - ALLOW_ANONYMOUS_LOGIN=yes
    volumes:
      - ./data/zookeeper:/bitnami/zookeeper  # 持久化 Zookeeper 数据

  kafka:
    image: bitnami/kafka:latest
    container_name: learn-kafka
    ports:
      - "9092:9092"
    environment:
      - KAFKA_BROKER_ID=0
      - KAFKA_ZOOKEEPER_CONNECT=192.168.1.7:2181/kafka
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://192.168.1.7:9092
      - KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092
    volumes:
      - ./data/kafka:/bitnami/kafka         # 持久化 Kafka 数据
      - /etc/localtime:/etc/localtime
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "2"

```

**进入 kafka**

```
docker exec -it learn-kafka /bin/bash
```

```
cd /opt/bitnami/kafka/bin
```

**查看 kafka 版本**

```
kafka-topics.sh --version
```

**验证 kafka**

创建一个新的主题：

```
./kafka-topics.sh --create --topic msjx-topic --bootstrap-server localhost:9092
```

在开启一个新的终端，一个作为生产者，一个作为消费者

消费者

```
./kafka-console-consumer.sh --topic msjx-topic --from-beginning --bootstrap-server localhost:9092
```

生产者

```
./kafka-console-producer.sh --topic msjx-topic --bootstrap-server localhost:9092
```

在生产者页面输入测试内容：

```
{"id":1,"name":"arvin"}
```

容器中data文件的地址：/bitnami/kafka
