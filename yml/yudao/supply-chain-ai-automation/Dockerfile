FROM mysql:8.0

# Use the MySQL 8 client so the autonomous runner can authenticate with the
# same caching_sha2_password policy as the governed local database.
RUN microdnf install -y python3 && microdnf clean all

WORKDIR /app
