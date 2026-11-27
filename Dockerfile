FROM oraclelinux:8

# Oracle Instant Client (thick mode, required for SODA) and Python 3.12
RUN dnf install -y oracle-instantclient-release-el8 && \
    dnf install -y oracle-instantclient-basic python3.12 python3.12-pip && \
    dnf clean all

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN python3.12 -m pip install --no-cache-dir -r requirements.txt

# Copy application code (wallet/ and config.yaml are excluded by .dockerignore;
# mount them at run time, see README)
COPY . .

# Non-root user
RUN useradd -m appuser
USER appuser

# Expose both UDP (telemetry) and TCP (dashboard/API) ports
EXPOSE 65530/udp
EXPOSE 8080/tcp

# Bind the dashboard on all interfaces inside the container so -p 8080:8080 works
ENTRYPOINT ["python3.12", "app.py", "--web-host", "0.0.0.0"]
CMD ["--mode", "race"]
