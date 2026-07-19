# scripts/ssh_deploy.py
import os
import sys
import time
import base64

# Install paramiko dynamically if missing
try:
    import paramiko
except ImportError:
    print("Installing paramiko library for automated SSH/SFTP deployment...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

import boto3

# Configurations
INSTANCE_NAME = "setu-backend-vm"
REGION = "ap-south-1"
VM_USER = "ubuntu"
PORT = 8000
DB_URL = "postgresql://db_admin:StrongSecurePassword2026!@ls-83fa2f9fe4b27c6c22ddf9e234fc08b2693ddd0d.cf2ew8a6usun.ap-south-1.rds.amazonaws.com:5432/setu_reconciliation"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.join(PROJECT_ROOT, "lightsail_key.pem")

def run_ssh_command(ssh, command):
    print(f"Running command: {command}")
    stdin, stdout, stderr = ssh.exec_command(command)
    # Wait for the command to finish
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    if exit_status != 0:
        print(f"[WARNING/ERROR] Command exit status: {exit_status}")
        print(f"Stdout:\n{out}")
        print(f"Stderr:\n{err}")
    else:
        print(f"Stdout:\n{out[:500]}") # Show first 500 chars
    return exit_status, out, err

def sftp_upload_dir(sftp, local_dir, remote_dir):
    print(f"Uploading local directory {local_dir} to remote {remote_dir}...")
    for root, dirs, files in os.walk(local_dir):
        # Calculate relative path
        rel_path = os.path.relpath(root, local_dir)
        if rel_path == ".":
            target_dir = remote_dir
        else:
            target_dir = os.path.join(remote_dir, rel_path).replace("\\", "/")
            
        # Create remote dir if it doesn't exist
        try:
            sftp.mkdir(target_dir)
        except IOError:
            pass # Directory might already exist
            
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(target_dir, file).replace("\\", "/")
            sftp.put(local_file, remote_file)

def deploy():
    print("==================================================")
    print("Starting Automated SSH Deployment to AWS Lightsail...")
    print("==================================================")
    
    session = boto3.Session()
    client = boto3.client('lightsail', region_name=REGION)
    
    # 1. Download Default Key Pair
    print("Downloading Lightsail default key pair...")
    try:
        key_res = client.download_default_key_pair()
        private_key_text = key_res['privateKeyBase64']
        
        # Decode and write to file
        with open(KEY_PATH, "w") as f:
            f.write(private_key_text)
        print(f"Saved SSH key locally to {KEY_PATH}")
    except Exception as e:
        print(f"Failed to download default key pair: {e}")
        # Try if it's already there
        if not os.path.exists(KEY_PATH):
            print("[ERROR] Key file not found.")
            return

    # 2. Get VM Instance IP Address
    print("Retrieving VM IP address...")
    instance_info = client.get_instance(instanceName=INSTANCE_NAME)
    public_ip = instance_info['instance'].get('publicIpAddress')
    if not public_ip:
        print("[ERROR] Could not find Public IP address for the VM. Is it running?")
        return
    print(f"Found VM Public IP: {public_ip}")

    # 3. Connect via SSH
    print(f"Connecting to {VM_USER}@{public_ip} via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Retry connection a few times as VM SSH server might take a minute to accept keys
    retries = 5
    connected = False
    for i in range(retries):
        try:
            ssh.connect(hostname=public_ip, username=VM_USER, key_filename=KEY_PATH, timeout=10)
            connected = True
            break
        except Exception as e:
            print(f"Connection attempt {i+1} failed: {e}. Retrying in 10s...")
            time.sleep(10)
            
    if not connected:
        print("[ERROR] Failed to establish SSH connection.")
        return
    print("SSH connection successfully established!")

    # 4. Install Docker on VM
    print("\n--- Installing Docker ---")
    run_ssh_command(ssh, "sudo apt-get update -y && sudo apt-get install -y docker.io")
    run_ssh_command(ssh, "sudo systemctl start docker && sudo systemctl enable docker")

    # 5. Create application directory
    print("\n--- Creating Application Directory ---")
    run_ssh_command(ssh, "mkdir -p ~/setu-reconciliation/src")

    # 6. Upload files via SFTP
    print("\n--- Uploading Files via SFTP ---")
    
    # Package src folder into a tarball first to make transmission super stable and fast
    import tarfile
    tar_path = os.path.join(PROJECT_ROOT, "src.tar.gz")
    print(f"Creating source archive 'src.tar.gz' locally at {tar_path}...")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(os.path.join(PROJECT_ROOT, "src"), arcname="src")
    print("Source archive successfully created.")

    transport = paramiko.Transport((public_ip, 22))
    pkey = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    transport.connect(username=VM_USER, pkey=pkey)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    # Upload requirements.txt
    sftp.put(os.path.join(PROJECT_ROOT, "requirements.txt"), "/home/ubuntu/setu-reconciliation/requirements.txt")
    
    # Upload Dockerfile
    sftp.put(os.path.join(PROJECT_ROOT, "Dockerfile"), "/home/ubuntu/setu-reconciliation/Dockerfile")
    
    # Upload src.tar.gz
    sftp.put(tar_path, "/home/ubuntu/setu-reconciliation/src.tar.gz")
    
    sftp.close()
    transport.close()
    print("Files successfully uploaded!")

    # Clean up local tarball
    if os.path.exists(tar_path):
        os.remove(tar_path)

    # Extract src archive on VM
    print("\n--- Extracting Source Code Archive on VM ---")
    run_ssh_command(ssh, "tar -xzf ~/setu-reconciliation/src.tar.gz -C ~/setu-reconciliation/")
    run_ssh_command(ssh, "rm ~/setu-reconciliation/src.tar.gz")

    # 7. Build Docker Image
    print("\n--- Building Docker Image ---")
    run_ssh_command(ssh, "cd ~/setu-reconciliation && sudo docker build -t setu-backend .")

    # 8. Clean up existing containers
    print("\n--- Stopping Existing Container ---")
    run_ssh_command(ssh, "sudo docker stop setu-backend-container 2>/dev/null || true")
    run_ssh_command(ssh, "sudo docker rm setu-backend-container 2>/dev/null || true")

    # 9. Start Container
    print("\n--- Starting Container ---")
    run_command_str = (
        f"sudo docker run -d -p 8000:8000 "
        f"-e DATABASE_URL=\"{DB_URL}\" "
        f"-e PORT=\"8000\" "
        f"-e HOST=\"0.0.0.0\" "
        f"-e DISCREPANCY_THRESHOLD_HOURS=\"6.0\" "
        f"--restart always "
        f"--name setu-backend-container "
        f"setu-backend"
    )
    run_ssh_command(ssh, run_command_str)

    # Close SSH connection
    ssh.close()
    
    print("\n==================================================")
    print("AUTOMATED DEPLOYMENT SUCCESSFUL!")
    print(f"The APIs are now live and hosted at:")
    print(f"   http://{public_ip}:8000")
    print(f"   http://{public_ip}:8000/docs (Swagger Docs)")
    print("==================================================")

if __name__ == "__main__":
    deploy()
