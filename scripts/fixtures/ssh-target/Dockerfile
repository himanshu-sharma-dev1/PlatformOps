FROM alpine:3.20

RUN apk add --no-cache docker-cli openssh-server python3 py3-pip \
    && pip install --no-cache-dir --break-system-packages docker

COPY scripts/fixtures/ssh-target/entrypoint.sh /usr/local/bin/acceptance-ssh-entrypoint
COPY scripts/fixtures/ssh-target/docker-wrapper.sh /usr/local/bin/docker
RUN chmod 0755 /usr/local/bin/acceptance-ssh-entrypoint
RUN mv /usr/bin/docker /usr/bin/docker.real && chmod 0755 /usr/local/bin/docker

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/acceptance-ssh-entrypoint"]
