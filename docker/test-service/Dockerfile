FROM python:3.11-slim
WORKDIR /app
COPY server.py /app/server.py
RUN mkdir -p /var/log/test-service /etc
RUN echo '{"service": "PlatformOpsTest", "version": "1.0.0", "status": "active"}' > /etc/test_service.conf
EXPOSE 6379
CMD ["python3", "-u", "/app/server.py"]
