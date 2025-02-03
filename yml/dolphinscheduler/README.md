> 本文由 [简悦 SimpRead](http://ksria.com/simpread/) 转码， 原文地址 [blog.csdn.net](https://blog.csdn.net/qq_31247885/article/details/132102578)

默认已[安装 Docker](https://so.csdn.net/so/search?q=%E5%AE%89%E8%A3%85Docker&spm=1001.2101.3001.7020 "安装Docker") 和 Docker-compose 环境  
本案例安装海豚调度 3.1.0 并将 [PostgreSQL](https://so.csdn.net/so/search?q=PostgreSQL&spm=1001.2101.3001.7020) 替换为 mysql

这是官网 docker 部署教程：[https://dolphinscheduler.apache.org/zh-cn/docs/3.1.0/guide/start/docker](https://dolphinscheduler.apache.org/zh-cn/docs/3.1.0/guide/start/docker "https://dolphinscheduler.apache.org/zh-cn/docs/3.1.0/guide/start/docker")

但是官网教程里并没有表名基于 docker 的情况下如何将数据库替换为 mysql

一、资源下载
------

###### 源码下载：[https://archive.apache.org/dist/dolphinscheduler/3.1.0/apache-dolphinscheduler-3.1.0-src.tar.gz](https://archive.apache.org/dist/dolphinscheduler/3.1.0/apache-dolphinscheduler-3.1.0-src.tar.gz "https://archive.apache.org/dist/dolphinscheduler/3.1.0/apache-dolphinscheduler-3.1.0-src.tar.gz")

###### mysql 驱动下载：[https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.16/mysql-connector-java-8.0.16.jar](https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.16/mysql-connector-java-8.0.16.jar "https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.16/mysql-connector-java-8.0.16.jar")

二、安装
----

解压后有很多文件夹，其实这些都是些源码。可以不用管，也可以删除

```
tar -zxf apache-dolphinscheduler-3.1.0-src.tar.gz
 
cd apache-dolphinscheduler-3.1.0-src/deploy/docker
 
ls -a
里面只有两个文件是我们需要用到的，.env文件是所有镜像需要用到的环境变量，平时是隐藏的
docker-compose.yml .env
```

打开 [docker-compose](https://so.csdn.net/so/search?q=docker-compose&spm=1001.2101.3001.7020).yml 文件将里面的 PostgreSQL 删除加入 mysql 启动命令

同时将下载好的 mysql 镜像放到和 docker-compose.yml 同级目录

一下是我调整后完整的 docker-compose.yml 文件：

```
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
 
version: "3.8"
 
services:
  mysql:
    image: "registry.creditx.com/xfeature/xai_mysql:latest"
    profiles: ["all", "schema"]
    command: --max_allowed_packet=209715200
    ports:
      - "3306:3306"
    volumes:
      - "./mysql/init-sql:/docker-entrypoint-initdb.d"
      - "./mysql/data:/var/lib/mysql"
    environment:
      - MYSQL_ROOT_PASSWORD=CraiditX123
      - MYSQL_DATABASE=dolphinscheduler
      - TZ=Asia/Shanghai
    networks:
      - dolphinscheduler
 
  dolphinscheduler-zookeeper:
    image: bitnami/zookeeper:3.6.2
    profiles: ["all"]
    environment:
      ALLOW_ANONYMOUS_LOGIN: "yes"
      ZOO_4LW_COMMANDS_WHITELIST: srvr,ruok,wchs,cons
    volumes:
      - dolphinscheduler-zookeeper:/bitnami/zookeeper
    healthcheck:
      test: ["CMD", "bash", "-c", "cat < /dev/null > /dev/tcp/127.0.0.1/2181"]
      interval: 5s
      timeout: 60s
      retries: 120
    networks:
      - dolphinscheduler
 
  dolphinscheduler-schema-initializer:
    image: apache/dolphinscheduler-tools:3.1.0
    env_file: .env
    profiles: ["schema"]
    command: [ tools/bin/upgrade-schema.sh ]
    depends_on:
      - mysql
    volumes:
      - dolphinscheduler-logs:/opt/dolphinscheduler/logs
      - dolphinscheduler-shared-local:/opt/soft
      - dolphinscheduler-resource-local:/dolphinscheduler
      - "./mysql-connector-java-8.0.16.jar:/opt/dolphinscheduler/tools/libs/mysql-connector-java-8.0.16.jar"
    networks:
      - dolphinscheduler
 
  dolphinscheduler-api:
    image: apache/dolphinscheduler-api:3.1.0
    ports:
      - "12345:12345"
      - "25333:25333"
    profiles: ["all"]
    env_file: .env
    healthcheck:
      test: [ "CMD", "curl", "http://localhost:12345/dolphinscheduler/actuator/health" ]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      dolphinscheduler-zookeeper:
        condition: service_healthy
    volumes:
      - dolphinscheduler-logs:/opt/dolphinscheduler/logs
      - dolphinscheduler-shared-local:/opt/soft
      - dolphinscheduler-resource-local:/dolphinscheduler
      - "./mysql-connector-java-8.0.16.jar:/opt/dolphinscheduler/libs/mysql-connector-java-8.0.16.jar"
    networks:
      - dolphinscheduler
 
  dolphinscheduler-alert:
    image: apache/dolphinscheduler-alert-server:3.1.0
    profiles: ["all"]
    env_file: .env
    healthcheck:
      test: [ "CMD", "curl", "http://localhost:50053/actuator/health" ]
      interval: 30s
      timeout: 5s
      retries: 3
    volumes:
      - dolphinscheduler-logs:/opt/dolphinscheduler/logs
      - "./mysql-connector-java-8.0.16.jar:/opt/dolphinscheduler/libs/mysql-connector-java-8.0.16.jar"
    networks:
      - dolphinscheduler
 
  dolphinscheduler-master:
    image: apache/dolphinscheduler-master:3.1.0
    profiles: ["all"]
    env_file: .env
    healthcheck:
      test: [ "CMD", "curl", "http://localhost:5679/actuator/health" ]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      dolphinscheduler-zookeeper:
        condition: service_healthy
    volumes:
      - dolphinscheduler-logs:/opt/dolphinscheduler/logs
      - dolphinscheduler-shared-local:/opt/soft
      - "./mysql-connector-java-8.0.16.jar:/opt/dolphinscheduler/libs/mysql-connector-java-8.0.16.jar"
    networks:
      - dolphinscheduler
 
  dolphinscheduler-worker:
    image: apache/dolphinscheduler-worker:3.1.0
    profiles: ["all"]
    env_file: .env
    healthcheck:
      test: [ "CMD", "curl", "http://localhost:1235/actuator/health" ]
      interval: 30s
      timeout: 5s
      retries: 3
    depends_on:
      dolphinscheduler-zookeeper:
        condition: service_healthy
    volumes:
      - dolphinscheduler-worker-data:/tmp/dolphinscheduler
      - dolphinscheduler-logs:/opt/dolphinscheduler/logs
      - dolphinscheduler-shared-local:/opt/soft
      - dolphinscheduler-resource-local:/dolphinscheduler
      - "./mysql-connector-java-8.0.16.jar:/opt/dolphinscheduler/libs/mysql-connector-java-8.0.16.jar"
    networks:
      - dolphinscheduler
 
networks:
  dolphinscheduler:
    driver: bridge
 
volumes:
  mysql:
  dolphinscheduler-zookeeper:
  dolphinscheduler-worker-data:
  dolphinscheduler-logs:
  dolphinscheduler-shared-local:
  dolphinscheduler-resource-local:
```

三、启动
----

初始化数据库：

docker-compose --profile schema up -d  
有可能 mysql 还未启动起来导致初始化失败可以再启动一下 tool 模块  
docker-compose --profile schema start dolphinscheduler-schema-initializer

初始化完成后启动所有服务

docker-compose --profile all up -d

备注：我本来是打算直接部署最新版本 3.1.7 的。但是 apache/dolphinscheduler-tools:3.1.7 容器一直启动不起来抛资源不够，但是我还有 7 个 G 的运行内存，没找到原因：

![](https://i-blog.csdnimg.cn/blog_migrate/8317d8324c0ae49151676443a661d62c.png)




docker cp apache-seatunnel-2.3.3-bin.tar.gz dolphinscheduler-dolphinscheduler-worker-1:/opt/soft

tar -zxvf /opt/soft/apache-seatunnel-2.3.3-bin.tar.gz --strip-components 1 -C /opt/soft/seatunnel

docker cp connector-jdbc-2.3.3.jar dolphinscheduler-dolphinscheduler-worker-1:/opt/soft/seatunnel/connectors/seatunnel

docker cp connector-doris-2.3.3.jar dolphinscheduler-dolphinscheduler-worker-1:/opt/soft/seatunnel/connectors/seatunnel

docker cp mysql-connector-java-8.0.16.jar dolphinscheduler-dolphinscheduler-worker-1:/opt/soft/seatunnel/lib

/opt/soft/seatunnel/connectors/seatunnel


docker cp seatunnel-hadoop3-3.1.4-uber-2.3.3-optional.jar dolphinscheduler-dolphinscheduler-worker-1:/opt/soft/seatunnel/lib



登录界面：http://localhost:12345/dolphinscheduler/ui/login
DolphinScheduler 默认的用户和密码分别为 admin 和 dolphinscheduler123

生成数据
