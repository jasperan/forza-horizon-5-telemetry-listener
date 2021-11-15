# For more information, please refer to https://aka.ms/vscode-docker-python
FROM oraclelinux:8

RUN dnf -y install oracle-instantclient-release-el8 && \
    dnf -y install oracle-instantclient-basic oracle-instantclient-devel oracle-instantclient-sqlplus && \
    rm -rf /var/cache/dnf

RUN yum -y update && yum install -y python3 python3-pip

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

WORKDIR /app
COPY . /app
# Wallet is no longer needed as we're using TLS to connect to ADB. See src/testing_db_tls.py for more info.
# Copy wallet to /home/appuser/wallets/Wallet_forza
COPY wallet /home/appuser/wallets/Wallet_forza

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN useradd appuser && chown -R appuser /app
USER appuser
EXPOSE 65530/udp

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
#ENTRYPOINT "python3" "listener.py"
ENTRYPOINT "/bin/bash"