# scripts/deploy_lightsail.py
import os
import sys
import time

# Ensure dependencies are available
try:
    import boto3
except ImportError:
    print("Installing boto3 library to connect to AWS...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "boto3"])
    import boto3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

# Configurations
DB_NAME = "setu-reconciliation-db"
BLUEPRINT_ID = "postgres_16" # PostgreSQL 16
BUNDLE_ID = "micro_2_0"      # Cheap Lightsail database plan (free-tier eligible for first 3 months)
DB_USERNAME = "db_admin"
DB_PASSWORD = "StrongSecurePassword2026!" # Ensure this matches AWS password rules (alphanumeric + symbols, min 8 chars)

def create_database():
    print("==================================================")
    # Check if AWS credentials are configured locally
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        print("[ERROR] No AWS credentials found on your machine.")
        print("Please configure them locally using Git Bash / CMD by running: ")
        print("  aws configure")
        print("Do NOT paste your credentials in the AI chat for security reasons.")
        print("==================================================")
        return

    # Dynamically resolve region and availability zone from AWS credentials configuration
    region = session.region_name or "ap-south-1"  # Defaults to ap-south-1 (Mumbai)
    az = f"{region}a"                            # Selects the first AZ (e.g. ap-south-1a)

    print(f"Using local AWS credentials for user: {credentials.access_key[:8]}... [truncated]")
    print(f"Connecting to Lightsail in region '{region}' (AZ '{az}')...")
    client = boto3.client('lightsail', region_name=region)

    # Check if DB already exists
    try:
        existing = client.get_relational_database(relationalDatabaseName=DB_NAME)
        print(f"Database instance '{DB_NAME}' already exists.")
        db_instance = existing['relationalDatabase']
    except client.exceptions.NotFoundException:
        print(f"Creating new Lightsail PostgreSQL database instance '{DB_NAME}'...")
        print(f"Configured Plan: {BUNDLE_ID} (1 GB RAM, 1 vCPU, 40 GB Storage) - Free Tier Eligible!")
        print("This may take 5-10 minutes to spin up on AWS...")
        
        response = client.create_relational_database(
            relationalDatabaseName=DB_NAME,
            availabilityZone=az,
            relationalDatabaseBlueprintId=BLUEPRINT_ID,
            relationalDatabaseBundleId=BUNDLE_ID,
            masterDatabaseName="setu_reconciliation",
            masterUsername=DB_USERNAME,
            masterUserPassword=DB_PASSWORD,
            publiclyAccessible=True  # Enabled to allow local connections
        )
        db_instance = response['operations'][0]
        print("Database creation request submitted to AWS!")
    
    # Wait for the database to become available and get the endpoint
    print("Waiting for database instance to reach 'Available' status and retrieve endpoint details...")
    endpoint = None
    while True:
        status_res = client.get_relational_database(relationalDatabaseName=DB_NAME)
        db_info = status_res['relationalDatabase']
        status = db_info['state']
        print(f"Current State: {status}...")
        
        if status.lower() == "available":
            # Extract endpoint address and port from masterEndpoint
            if 'masterEndpoint' in db_info:
                address = db_info['masterEndpoint']['address']
                port = db_info['masterEndpoint']['port']
                endpoint = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{address}:{port}/setu_reconciliation"
                break
        
        time.sleep(30) # Check every 30 seconds

    if endpoint:
        print("\n==================================================")
        print("AWS Lightsail Database is Ready!")
        print(f"Endpoint: {endpoint}")
        print("==================================================")
        
        # Write to local .env file
        print(f"Updating local configuration .env file at {ENV_PATH}...")
        with open(ENV_PATH, "w") as f:
            f.write(f"DATABASE_URL={endpoint}\n")
            f.write("PORT=8000\n")
            f.write("HOST=0.0.0.0\n")
            f.write("DISCREPANCY_THRESHOLD_HOURS=6.0\n")
            
        print("Local configuration updated successfully. You can now run python scripts/seed.py to seed the cloud database!")
        print("==================================================")

if __name__ == "__main__":
    create_database()
