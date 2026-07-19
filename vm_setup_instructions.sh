#!/bin/bash
# Commands to run inside the Ubuntu VM to host the Docker backend container

# 1. Update packages & install Docker
sudo apt-get update -y
sudo apt-get install -y docker.io

# 2. Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker

# 3. Create a folder for the app
mkdir -p setu-reconciliation
cd setu-reconciliation

# 4. Create the Dockerfile
cat << 'EOF' > Dockerfile
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY src/ ./src
EXPOSE 8000
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

# 5. Create requirements.txt
cat << 'EOF' > requirements.txt
fastapi>=0.110.0
uvicorn[standard]>=0.28.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
pydantic>=2.6.0
pydantic-settings>=2.2.0
python-dateutil>=2.9.0
pytest>=8.0.0
requests>=2.31.0
httpx>=0.23.0
EOF

# 6. Copy src directory (done via git or scp, but for local container test we can build)
# Copy the src folder here using SFTP/SCP or Git.
# E.g. scp -r src/ ubuntu@43.205.94.73:~/setu-reconciliation/

# 7. Build the Docker image
# sudo docker build -t setu-backend .

# 8. Run the Docker container pointing to the AWS Database
# sudo docker run -d -p 8000:8000 \
#   -e DATABASE_URL="postgresql://db_admin:StrongSecurePassword2026!@ls-83fa2f9fe4b27c6c22ddf9e234fc08b2693ddd0d.cf2ew8a6usun.ap-south-1.rds.amazonaws.com:5432/setu_reconciliation" \
#   -e PORT="8000" \
#   -e HOST="0.0.0.0" \
#   -e DISCREPANCY_THRESHOLD_HOURS="6.0" \
#   --restart always \
#   --name setu-backend-container \
#   setu-backend
