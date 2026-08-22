FROM python:3.8-slim-buster

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set arguments for user and group ids
ARG USERNAME="admin"
ARG USER_UID=1000
ARG USER_GID=1000

# Create directories and copy files
RUN mkdir /Asr
RUN echo "Current working directory:" && pwd
COPY . /Asr/

# Install dependencies
RUN apt-get update \
    && apt-get -y install nano procps nginx wget tar ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    apt-get install -y pkg-config

# Set home directory and working directory
ARG HOME="/Asr/Asr"
WORKDIR $HOME

RUN export MYSQLCLIENT_CFLAGS="-I/usr/include/mysql"
RUN export MYSQLCLIENT_LDFLAGS="-L/usr/lib/x86_64-linux-gnu -lmysqlclient"

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip cache purge && \
    python -m pip install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt
