FROM oraclelinux:8

# Oracle Instant Client (for thick mode DB connections)
RUN dnf install -y oracle-instantclient-release-el8 && \
    dnf install -y oracle-instantclient-basic && \
    dnf install -y python39 python39-pip && \
    dnf clean all

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user
RUN useradd -m appuser
USER appuser

# Expose both UDP (telemetry) and TCP (dashboard/API) ports
EXPOSE 65530/udp
EXPOSE 8080/tcp

# Entry point: new FastAPI-based app
ENTRYPOINT ["python3", "app.py"]
CMD ["--mode", "race"]