FROM python:3.11-slim

# Installa compilatori e librerie OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make libgomp1 curl unzip jq \
    && rm -rf /var/lib/apt/lists/*

# Installa AWS CLI v2
RUN curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli --update \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

WORKDIR /app

# Copia codice C e compila
COPY containers/grayscale/c /app/c
WORKDIR /app/c
RUN make && ls -la ../bin/

WORKDIR /app

# Copia l'adapter Python
COPY containers/grayscale/adapter.py /app/adapter.py
RUN chmod +x /app/adapter.py

# Installa dipendenze Python per DICOM support
RUN pip install --no-cache-dir boto3 requests pydicom pillow numpy

# Verifica che il binario sia stato creato
RUN ls -la /app/bin/grayscale && ldd /app/bin/grayscale

# Test rapido del binario (opzionale)
RUN echo "Testing grayscale binary..." && /app/bin/grayscale 2>&1 || echo "Binary ready (expected usage error)"

# Comando di default
ENTRYPOINT ["/app/adapter.py"]
