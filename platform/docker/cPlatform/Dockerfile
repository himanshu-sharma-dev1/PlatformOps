FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1

ARG USERNAME="admin"
ARG USER_UID=1000
ARG USER_GID=1000

RUN mkdir /iktara
RUN mkdir /iktara/cPlatform
COPY . /iktara/cPlatform/

RUN apt-get update \
    && apt-get -y install nano procps nginx wget tar curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

#  Install Terraform
ENV T_VERSION=1.8.5
RUN wget https://releases.hashicorp.com/terraform/${T_VERSION}/terraform_${T_VERSION}_linux_amd64.zip && \
    unzip terraform_${T_VERSION}_linux_amd64.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform_${T_VERSION}_linux_amd64.zip

RUN apt update \
    && apt install -y openssh-client \
    && apt install sshpass \
    && rm -rf /var/lib/apt/lists/*

ARG HOME="/iktara/cPlatform/cPlatform"
WORKDIR $HOME

RUN pip cache purge && \
    python -m pip install --upgrade pip && \
    pip3 install --upgrade --no-cache-dir -r requirements-cplatform.txt

# Install system dependencies for Playwright headless browsers
RUN apt update && apt install -y --no-install-recommends \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libexpat1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libcairo2 \
    libpango-1.0-0 \
    libasound2 \
    fonts-liberation \
    libxss1 \
    libxtst6 \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libdbus-1-3 \
    xdg-utils \
    wget \
    curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install playwright==1.54.0 && playwright install --with-deps

COPY platform/nginx/nginx.conf /etc/nginx/nginx.conf
COPY platform/nginx/certificate.crt /etc/nginx/ssl/
COPY platform/nginx/private.key /etc/nginx/ssl/

RUN chown -R www-data:www-data $HOME/static \
    && chown -R www-data:www-data /var/log/nginx \
    && chown -R www-data:www-data /var/www/

CMD ["bash", "entrypoint_script.sh"]