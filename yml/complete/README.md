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

dinky 默认的用户和密码：admin  dinky123!@#

minio 默认的用户和密码：admin  password

生成数据
