# containers/base/Dockerfile
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    AWS_REGION=us-east-1

# -----------------------------------------------------------------------------#
# System packages                                                               #
#   • curl, unzip : necessari per installare aws‑cli v2                         #
#   • jq          : usato da worker.sh                                          #
# -----------------------------------------------------------------------------#
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash curl unzip jq && \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------#
# AWS CLI v2 – bundle ufficiale                                                 #
# -----------------------------------------------------------------------------#
RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
 && unzip -q /tmp/awscliv2.zip -d /tmp \
 && /tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update \
 && rm -rf /tmp/aws /tmp/awscliv2.zip

# -----------------------------------------------------------------------------#
# Python dependencies & source                                                  #
# -----------------------------------------------------------------------------#
WORKDIR /app
COPY requirements.txt .
COPY src/ src/
RUN pip install --no-cache-dir -r requirements.txt -e ./src requests boto3

# -----------------------------------------------------------------------------#
# Entrypoint                                                                    #
# -----------------------------------------------------------------------------#
COPY containers/base/worker.sh /app/worker.sh
RUN chmod +x /app/worker.sh
ENTRYPOINT ["/app/worker.sh"]
