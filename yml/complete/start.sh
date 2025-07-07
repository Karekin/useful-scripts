#!/bin/bash

# Complete Data Platform Startup Script
# This script provides easy commands to start different service combinations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to check system requirements
check_system_requirements() {
    print_status "Checking system requirements..."
    
    # Check available memory
    local mem_gb=$(free -g | awk '/^Mem:/{print $2}')
    if [ "$mem_gb" -lt 8 ]; then
        print_warning "Recommended: At least 8GB RAM (current: ${mem_gb}GB)"
    fi
    
    # Check available disk space
    local disk_gb=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$disk_gb" -lt 50 ]; then
        print_warning "Recommended: At least 50GB free disk space (current: ${disk_gb}GB)"
    fi
}

# Function to apply system configurations for Doris Manager
apply_system_config() {
    print_status "Applying system configurations for Doris Manager..."
    
    # Check if running as root or with sudo
    if [ "$EUID" -eq 0 ]; then
        sysctl -w vm.max_map_count=2000000
        swapoff -a
        ulimit -n 1000000
        echo madvise > /sys/kernel/mm/transparent_hugepage/enabled
        print_status "System configurations applied successfully"
    else
        print_warning "System configurations require root privileges. Please run:"
        echo "sudo sysctl -w vm.max_map_count=2000000"
        echo "sudo swapoff -a"
        echo "sudo ulimit -n 1000000"
        echo "echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled"
    fi
}

# Function to start services
start_services() {
    local profile=$1
    local description=$2
    
    print_header "Starting $description"
    
    check_docker
    check_system_requirements
    
    if [ "$profile" = "doris-manager" ] || [ "$profile" = "all+doris-manager" ]; then
        apply_system_config
    fi
    
    print_status "Starting services with profile: $profile"
    docker-compose --profile $profile up -d
    
    print_status "Services started successfully!"
    print_status "Use 'docker-compose ps' to check service status"
    print_status "Use 'docker-compose logs -f' to view logs"
}

# Function to stop services
stop_services() {
    print_header "Stopping All Services"
    
    check_docker
    
    print_status "Stopping all services..."
    docker-compose down
    
    print_status "Services stopped successfully!"
}

# Function to restart services
restart_services() {
    print_header "Restarting Services"
    
    check_docker
    
    print_status "Restarting services..."
    docker-compose restart
    
    print_status "Services restarted successfully!"
}

# Function to show service status
show_status() {
    print_header "Service Status"
    
    check_docker
    
    docker-compose ps
}

# Function to show logs
show_logs() {
    local service=$1
    
    if [ -z "$service" ]; then
        print_status "Showing logs for all services..."
        docker-compose logs -f
    else
        print_status "Showing logs for $service..."
        docker-compose logs -f "$service"
    fi
}

# Function to show help
show_help() {
    print_header "Complete Data Platform Startup Script"
    
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  all                    Start all services (DolphinScheduler, Kafka, Flink, etc.)"
    echo "  doris-manager          Start only Doris Manager with agents"
    echo "  all+doris-manager      Start all services including Doris Manager"
    echo "  schema                 Initialize database schema only"
    echo "  stop                   Stop all services"
    echo "  restart                Restart all services"
    echo "  status                 Show service status"
    echo "  logs [SERVICE]         Show logs (all services or specific service)"
    echo "  help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 all                 # Start all services"
    echo "  $0 doris-manager       # Start Doris Manager only"
    echo "  $0 logs mysql          # Show MySQL logs"
    echo "  $0 status              # Show all service status"
    echo ""
    echo "Service Ports:"
    echo "  MySQL: 3306"
    echo "  Kafka: 9092, 29092"
    echo "  Kafka UI: 8080"
    echo "  Doris Manager: 8004"
    echo "  Doris (legacy): 8030, 8040, 9030"
    echo "  DolphinScheduler: 12345, 25333"
    echo "  Flink: 8082"
    echo "  Dinky: 8888"
    echo "  Superset: 8088"
    echo "  NocoDB: 8089"
    echo "  MinIO: 9000, 9001"
    echo "  Iceberg REST: 8181"
}

# Main script logic
case "${1:-help}" in
    "all")
        start_services "all" "All Services (DolphinScheduler, Kafka, Flink, etc.)"
        ;;
    "doris-manager")
        start_services "doris-manager" "Doris Manager with Agents"
        ;;
    "all+doris-manager")
        start_services "all doris-manager" "All Services including Doris Manager"
        ;;
    "schema")
        start_services "schema" "Database Schema Initialization"
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs "$2"
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac 