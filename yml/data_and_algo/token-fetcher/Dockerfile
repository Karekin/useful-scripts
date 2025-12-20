# Token Fetcher for GitHub App Installation Access Token
#
# This lightweight container generates short-lived tokens for git-sync
# to authenticate with GitHub private repositories.

FROM python:3.11-alpine

LABEL maintainer="CloudMold Infrastructure Team"
LABEL description="GitHub App Installation Token Fetcher"

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY fetch_token.py /app/fetch_token.py
RUN chmod +x /app/fetch_token.py

WORKDIR /app

# Run as non-root user for security
RUN adduser -D -u 1000 tokenuser
USER tokenuser

CMD ["python", "/app/fetch_token.py"]

