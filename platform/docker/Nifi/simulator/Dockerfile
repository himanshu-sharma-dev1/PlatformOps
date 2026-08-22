FROM python:3.11-slim

WORKDIR /opt/noc-simulator
COPY platform/docker/Nifi/simulator/ /opt/noc-simulator/

ENV SIMULATOR_INPUT_DIR=/data/incoming \
    SIMULATOR_ARCHIVE_DIR=/data/sent \
    SIMULATOR_NIFI_URL=http://nifi:9080/aviat \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data/incoming /data/sent
EXPOSE 8080

ENTRYPOINT ["python", "simulator.py"]
