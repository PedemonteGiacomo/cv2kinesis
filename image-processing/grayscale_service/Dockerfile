FROM python:3
WORKDIR /app

# build the OpenMP grayscale binary
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY c /app/c
WORKDIR /app/c
RUN make

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
CMD ["python", "app.py"]
