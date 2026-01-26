FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Force IPv4 (many build envs fail on IPv6) + safer apt behavior
RUN printf 'Acquire::ForceIPv4 "true";\nAcquire::Retries "5";\n' > /etc/apt/apt.conf.d/99force-ipv4

# Install WeasyPrint dependencies
RUN apt-get update --allow-releaseinfo-change \
 && apt-get install -y --no-install-recommends \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    pango1.0-tools \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libxml2 \
    libxslt1.1 \
    libjpeg-dev \
    zlib1g-dev \
    libssl-dev \
    ca-certificates \
    fonts-dejavu-core \
    fonts-freefont-ttf \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD exec gunicorn multirx.wsgi:application --timeout 120 --bind 0.0.0.0:$PORT
