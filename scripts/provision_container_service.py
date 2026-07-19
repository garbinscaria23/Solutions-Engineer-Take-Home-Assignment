# scripts/provision_container_service.py
import os
import sys
import boto3

# Configurations
SERVICE_NAME = "setu-reconciliation-service"
REGION = "ap-south-1"  # Mumbai (matches the database region)
POWER = "micro"        # Cheapest scale tier ($7/mo)
SCALE = 1              # Number of container instances

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

def provision_service():
    print("==================================================")
    print(f"Provisioning AWS Lightsail Container Service '{SERVICE_NAME}'...")
    
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        print("[ERROR] AWS credentials not configured. Run 'aws configure' first.")
        return

    client = boto3.client('lightsail', region_name=REGION)
    db_url = get_database_url()

    # 1. Create or verify the container service
    try:
        service_info = client.get_container_services(serviceName=SERVICE_NAME)
        print(f"Container service '{SERVICE_NAME}' already exists.")
        service = service_info['containerServices'][0]
    except client.exceptions.NotFoundException:
        print(f"Creating new container service '{SERVICE_NAME}' (Power: {POWER}, Scale: {SCALE})...")
        response = client.create_container_service(
            serviceName=SERVICE_NAME,
            power=POWER,
            scale=SCALE
        )
        service = response['containerService']
        print("Service creation initiated! It will take a few minutes to become ready.")

    # 2. Print deployment instructions
    print("\n==================================================")
    print("    DEPOYMENT INSTRUCTIONS")
    print("==================================================")
    print("To build and push your Docker image to this service, run these commands in your Git Bash terminal:")
    print("\n1. Build the Docker image locally:")
    print("   docker build -t setu-backend .")
    print("\n2. Push the image to AWS Lightsail (requires Lightsail Control plugin installed):")
    print(f"   aws lightsail push-container-image --service-name {SERVICE_NAME} --label backend --image setu-backend")
    print("\n==================================================")
    print("Note: When the push completes, it will print an image reference name like:")
    print(f"   :\"{SERVICE_NAME}.backend.X\" (where X is a number, e.g. :\"{SERVICE_NAME}.backend.1\")")
    print("==================================================")

    # Save target config file to make deployment registration easier
    deploy_config_path = os.path.join(PROJECT_ROOT, "lightsail_deployment.json")
    deploy_config = {
        "serviceName": SERVICE_NAME,
        "containers": {
            "backend": {
                "image": f":{SERVICE_NAME}.backend.latest", # Or replace with exact pushed label
                "command": [],
                "environment": {
                    "DATABASE_URL": db_url,
                    "PORT": "8000",
                    "HOST": "0.0.0.0",
                    "DISCREPANCY_THRESHOLD_HOURS": "6.0"
                },
                "ports": {
                    "8000": "HTTP"
                }
            }
        },
        "publicEndpoint": {
            "containerName": "backend",
            "containerPort": 8000,
            "healthCheck": {
                "path": "/",
                "intervalSeconds": 10,
                "timeoutSeconds": 5,
                "successThreshold": 2,
                "failThreshold": 2
            }
        }
    }
    
    with open(deploy_config_path, "w") as f:
        json.dump(deploy_config, f, indent=2)
    
    print(f"\nGenerated deployment config file: {deploy_config_path}")
    print("You can apply this deployment template on AWS by running:")
    print(f"   aws lightsail create-container-service-deployment --cli-input-json file://lightsail_deployment.json")
    print("==================================================")

if __name__ == "__main__":
    import json
    provision_service()
