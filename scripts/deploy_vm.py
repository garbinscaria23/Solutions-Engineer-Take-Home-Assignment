# scripts/deploy_vm.py
import os
import sys
import boto3

# Configurations
INSTANCE_NAME = "setu-backend-vm"
REGION = "ap-south-1"  # Mumbai (same region as database)
AZ = "ap-south-1a"
BLUEPRINT_ID = "ubuntu_22_04" # Ubuntu 22.04 LTS
BUNDLE_ID = "nano_3_1"        # $3.50/mo VM (free-tier eligible for 3 months)

# Read cloud database endpoint from .env
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

def get_database_url():
    if not os.path.exists(ENV_PATH):
        print(f"[ERROR] .env file not found at {ENV_PATH}. Run deploy_lightsail.py first to create the cloud database.")
        sys.exit(1)
        
    db_url = None
    with open(ENV_PATH, "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip()
                break
    if not db_url:
        print("[ERROR] DATABASE_URL not found in .env file.")
        sys.exit(1)
    return db_url

def deploy_vm():
    print("==================================================")
    print(f"Provisioning AWS Lightsail VM instance '{INSTANCE_NAME}'...")
    
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        print("[ERROR] AWS credentials not configured. Run 'aws configure' first.")
        return

    client = boto3.client('lightsail', region_name=REGION)

    # 1. Create or verify the VM instance
    try:
        instance_info = client.get_instance(instanceName=INSTANCE_NAME)
        print(f"VM instance '{INSTANCE_NAME}' already exists.")
        instance = instance_info['instance']
    except client.exceptions.NotFoundException:
        print(f"Creating new Ubuntu VM '{INSTANCE_NAME}' (Bundle: {BUNDLE_ID})...")
        response = client.create_instances(
            instanceNames=[INSTANCE_NAME],
            availabilityZone=AZ,
            blueprintId=BLUEPRINT_ID,
            bundleId=BUNDLE_ID
        )
        print("VM creation request submitted successfully!")
        
    # Wait for the VM to start and get its public IP
    print("Retrieving VM IP address...")
    import time
    public_ip = None
    while True:
        status_res = client.get_instance(instanceName=INSTANCE_NAME)
        instance = status_res['instance']
        state = instance['state']['name']
        print(f"Current VM State: {state}...")
        
        if state.lower() == "running":
            public_ip = instance.get('publicIpAddress')
            if public_ip:
                break
        time.sleep(10)
        
    # Open port 8000 on the firewall
    print(f"Configuring firewall to allow HTTP traffic on port 8000...")
    try:
        client.open_instance_public_ports(
            instanceName=INSTANCE_NAME,
            portInfo={
                'fromPort': 8000,
                'toPort': 8000,
                'protocol': 'tcp'
            }
        )
        print("Port 8000 opened successfully!")
    except Exception as e:
        print(f"Note: Firewall port opening completed or skipped: {e}")

    # Generate setup instructions script
    setup_script_path = os.path.join(PROJECT_ROOT, "vm_setup_instructions.sh")
    db_url = get_database_url()
    
    setup_commands = f"""#!/bin/bash
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
# E.g. scp -r src/ ubuntu@{public_ip}:~/setu-reconciliation/

# 7. Build the Docker image
# sudo docker build -t setu-backend .

# 8. Run the Docker container pointing to the AWS Database
# sudo docker run -d -p 8000:8000 \\
#   -e DATABASE_URL="{db_url}" \\
#   -e PORT="8000" \\
#   -e HOST="0.0.0.0" \\
#   -e DISCREPANCY_THRESHOLD_HOURS="6.0" \\
#   --restart always \\
#   --name setu-backend-container \\
#   setu-backend
"""
    with open(setup_script_path, "w") as f:
        f.write(setup_commands)

    print("\n==================================================")
    print("AWS Lightsail VM is Ready!")
    print(f"Public IP: {public_ip}")
    print("==================================================")
    print(f"Generated VM setup helper script: {setup_script_path}")
    print("\nHow to deploy:")
    print("1. SSH into the VM (you can do this via the AWS Lightsail Browser Console in one click).")
    print("2. Copy the contents of 'vm_setup_instructions.sh' and run them on the VM.")
    print("3. Copy your local 'src' directory to the VM using SCP:")
    print(f"   scp -i your_key.pem -r src/ ubuntu@{public_ip}:~/setu-reconciliation/")
    print("4. Run build and run commands on the VM.")
    print("==================================================")

if __name__ == "__main__":
    deploy_vm()
