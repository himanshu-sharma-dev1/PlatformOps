FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    T_VERSION=1.8.5 \
    PYTHONPATH=/app:/app/apps:/app/apps/platformops:/app/apps/platformops/lib

# Install system dependencies, terraform, openssh, and postgresql-client
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    unzip \
    openssh-client \
    sshpass \
    postgresql-client \
    procps \
    build-essential \
    libpq-dev \
    && wget -q https://releases.hashicorp.com/terraform/${T_VERSION}/terraform_${T_VERSION}_linux_amd64.zip \
    && unzip -q terraform_${T_VERSION}_linux_amd64.zip -d /usr/local/bin/ \
    && rm terraform_${T_VERSION}_linux_amd64.zip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . /app/

# Ensure entrypoint script is executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
