# Menggunakan versi slim yang lebih ringan
FROM python:3.12-slim

# Mencegah Python menulis file .pyc dan buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Menginstal dependensi sistem yang diperlukan (termasuk libffi dan musl untuk TGCrypto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements terlebih dahulu untuk memanfaatkan Docker Cache
COPY requirements.txt .

# Install dependensi Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code
COPY . .

# Membuat direktori backup jika diperlukan
RUN mkdir -p backup

# Jalankan bot
CMD ["python", "main.py"]
