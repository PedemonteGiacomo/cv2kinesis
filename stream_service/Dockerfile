# --------------------------------------------------------------------------- #
#  Base image                                                                  #
# --------------------------------------------------------------------------- #
FROM python:3.9-slim
WORKDIR /app

# --------------------------------------------------------------------------- #
#  System packages necessari per OpenCV + turbojpeg                            #
# --------------------------------------------------------------------------- #
RUN apt-get update && apt-get install -y \
        libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
        libgomp1 libturbojpeg0 && \
    rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------------------- #
#  Python deps (requirements.txt deve contenere anche gunicorn)                #
# --------------------------------------------------------------------------- #
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --------------------------------------------------------------------------- #
#  Codice e modelli                                                            #
# --------------------------------------------------------------------------- #
COPY yolov8n.pt .
COPY app_efo.py   app.py
COPY app_server.py .

# --------------------------------------------------------------------------- #
#  Network / entry-point                                                      #
# --------------------------------------------------------------------------- #
EXPOSE 8080

# Gunicorn pubblica l’app Flask definita in app_server.py
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "app_server:flask_app"]
