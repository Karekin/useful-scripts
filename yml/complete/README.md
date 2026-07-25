# Complete Data Platform Docker Compose Setup

This Docker Compose configuration provides a complete data platform with Apache Doris, DolphinScheduler, Kafka, Flink, and various data lake components.

## 🚀 Quick Start

### Prerequisites

1. **Docker & Docker Compose**: Ensure you have Docker and Docker Compose installed
2. **System Requirements**: 
   - At least 8GB RAM
   - 50GB free disk space
   - Docker with at least 4GB memory allocation

3. **System Configuration** (for Doris Manager):
   ```bash
   # Run these commands on your host machine
   sudo sysctl -w vm.max_map_count=2000000
   sudo swapoff -a
   sudo ulimit -n 1000000
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   ```

### Starting Services

#### Option 1: Start All Services
```bash
docker-compose --profile all up -d
```

#### Option 2: Start with Doris Manager
```bash
docker-compose --profile all --profile doris-manager up -d
```

#### Option 3: Start Only Doris Manager
```bash
docker-compose --profile doris-manager up -d
```

#### Option 4: Initialize Database Schema
```bash
docker-compose --profile schema up -d
```

## 📊 Service Overview

### Database Services
- **MySQL 8.0**: Primary database for DolphinScheduler and other services
  - Port: 3306
  - Credentials: root/123456

### Coordination Services
- **Zookeeper**: Service coordination for Kafka and DolphinScheduler
  - Port: 2181

### Message Queue Services
- **Kafka 3.6.1**: Distributed streaming platform
  - Internal Port: 9092
  - External Port: 29092
- **Kafka UI**: Web interface for Kafka management
  - Port: 8080

### Doris Services

#### Doris Manager (Recommended)
- **Doris Manager**: Cluster management for Apache Doris
  - Web UI: http://localhost:8004
  - API: http://localhost:8010
  - Agent Port: 8972
  - Prometheus: http://localhost:9090
  - AlertManager: http://localhost:9093
  - Grafana: http://localhost:3000

#### Legacy Standalone Doris
- **Doris Standalone**: Single-node Doris instance
  - HTTP Port: 8030
  - BE Port: 8040
  - MySQL Port: 9030

### Data Lake Services
- **MinIO**: S3-compatible object storage
  - API Port: 9000
  - Console Port: 9001
  - Credentials: admin/password
- **Iceberg REST**: REST API for Apache Iceberg
  - Port: 8181

### Processing Services
- **Apache Spark**: Distributed computing engine
- **Apache Flink**: Stream processing framework
  - JobManager UI: http://localhost:8082
  - TaskManager: 2 replicas

### Development & Management Tools
- **Dinky**: SQL development platform
  - Port: 8888
- **Apache Superset**: Data visualization platform
  - Port: 8088
  - Credentials: admin/doris
- **NocoDB**: Airtable alternative
  - Port: 8089

### Workflow Orchestration
- **DolphinScheduler**: Distributed workflow orchestration platform
  - API Port: 12345
  - UI Port: 25333

## 🔧 Configuration

### Environment Variables
The configuration uses common environment variables defined at the top of the compose file:
- `AWS_ACCESS_KEY_ID`: admin
- `AWS_SECRET_ACCESS_KEY`: password
- `AWS_REGION`: us-east-1

### Health Checks
All services include health checks with:
- Interval: 30s
- Timeout: 10s
- Retries: 3
- Start period: 40s (varies by service)

### Logging
Standardized logging configuration:
- Driver: json-file
- Max size: 100MB
- Max files: 3

## 🐳 Doris Manager Setup

### First Time Setup
1. Start Doris Manager:
   ```bash
   docker-compose --profile doris-manager up -d
   ```

2. Wait for initialization (1-2 minutes):
   ```
   =============================
   Everything is ready, enjoy!
   =============================
   ```

3. Access the web interface: http://localhost:8004

### Cluster Deployment
1. **Add Agents**: The compose file includes 2 agent containers
2. **Download Doris**: Use the manager to download Doris binary packages
3. **Deploy Cluster**: Follow the web interface instructions to deploy your Doris cluster

### Agent Configuration
- **Agent 1**: `doris-agent1` container
- **Agent 2**: `doris-agent2` container
- Both agents run with privileged mode for system access

## 📁 Directory Structure

```
yml/complete/
├── docker-compose.yml          # Main compose file
├── .env.example                # Safe template; copy to ignored .env and set local secrets
├── data/                       # Persistent data
│   ├── mysql/                  # MySQL data
│   ├── kafka/                  # Kafka data
│   ├── doris/                  # Legacy Doris data
│   ├── doris-manager/          # Doris Manager data
│   ├── doris-agent1/           # Agent 1 data
│   ├── doris-agent2/           # Agent 2 data
│   └── ...                     # Other service data
├── jars/                       # JAR files and dependencies
├── scripts/                    # Utility scripts
└── sql/                        # SQL initialization files
```

## 🔍 Monitoring & Management

### Service Health
Check service health:
```bash
docker-compose ps
```

### Logs
View service logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f doris-manager
```

### Resource Usage
Monitor resource usage:
```bash
docker stats
```

## 🛠️ Troubleshooting

### Common Issues

1. **Port Conflicts**
   - Check if ports are already in use: `netstat -tulpn | grep :PORT`
   - Modify ports in docker-compose.yml if needed

2. **Memory Issues**
   - Increase Docker memory allocation
   - Reduce service replicas if needed

3. **Doris Manager Startup**
   - Ensure system requirements are met
   - Check logs: `docker-compose logs doris-manager`

4. **Service Dependencies**
   - Services start in dependency order
   - Check health check status: `docker-compose ps`

### Performance Optimization

1. **MySQL Optimization**
   - Buffer pool size: 1GB
   - Log file size: 256MB
   - Flush method: O_DIRECT

2. **Kafka Optimization**
   - Log retention: 7 days
   - Segment size: 1GB
   - Partitions: 3

3. **Resource Limits**
   - Consider adding resource limits for production use
   - Monitor memory and CPU usage

## 🔐 Security Considerations

1. **Default Passwords**: Change default passwords in production
2. **Network Security**: Use internal networks for service communication
3. **Volume Permissions**: Ensure proper file permissions for data volumes
4. **Privileged Mode**: Doris Manager requires privileged mode for system access

## 📈 Scaling

### Horizontal Scaling
- **Flink TaskManagers**: Currently 2 replicas, can be increased
- **Doris Agents**: Add more agent containers as needed
- **Kafka**: Add more broker containers for production

### Vertical Scaling
- Adjust memory and CPU limits in docker-compose.yml
- Increase MySQL buffer pool size
- Optimize Kafka heap size

## 🆘 Support

For issues and questions:
1. Check service logs
2. Verify system requirements
3. Review configuration files
4. Check Docker and Docker Compose versions

## 📝 Changelog

### v2.0.0 (Current)
- Added Doris Manager support
- Optimized service configurations
- Improved health checks and dependencies
- Enhanced logging and monitoring
- Better resource management
- Fixed port conflicts
- Added comprehensive documentation

### v1.0.0 (Previous)
- Initial setup with basic services
- Standalone Doris configuration
- Basic DolphinScheduler setup

