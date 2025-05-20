FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    build-essential \
    libusb-1.0-0-dev \
    libusb-0.1-4 \
    libudev-dev \
    libjpeg8 \
    libgtk2.0-dev \
    usbutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip3 install --upgrade pip setuptools wheel

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
COPY libs/ /app/libs/
ENV LD_LIBRARY_PATH=/app/libs

EXPOSE 5000
CMD ["python3", "run.py"]
