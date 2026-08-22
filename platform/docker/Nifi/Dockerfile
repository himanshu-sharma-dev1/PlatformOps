FROM eclipse-temurin:21-jre-jammy

ARG NIFI_VERSION=2.10.0

RUN apt-get update -y && \
    apt-get install --no-install-recommends -y wget unzip procps && \
    cd /opt && \
    wget -q https://archive.apache.org/dist/nifi/${NIFI_VERSION}/nifi-${NIFI_VERSION}-bin.zip && \
    unzip -q nifi-${NIFI_VERSION}-bin.zip && \
    rm nifi-${NIFI_VERSION}-bin.zip && \
    mkdir -p /opt/nifi && \
    mv nifi-${NIFI_VERSION} /opt/nifi/nifi-current && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    chown -R root:root /opt/nifi

COPY platform/docker/Nifi/nifi.properties /opt/nifi/nifi-current/conf/
COPY platform/docker/Nifi/clickhouse-jdbc-0.4.6-shaded.jar /opt/nifi/nifi-current/lib/
COPY platform/docker/Nifi/mysql-connector-java-8.0.30.jar /opt/nifi/nifi-current/lib/
COPY platform/docker/Nifi/entrypoint.sh /opt/nifi/entrypoint.sh
RUN chmod 0755 /opt/nifi/entrypoint.sh
#COPY platform/docker/nifi/nifi-influx-database-nar-1.24.0.nar /opt/nifi/lib/

WORKDIR /opt/nifi/nifi-current
ENTRYPOINT ["/opt/nifi/entrypoint.sh"]
