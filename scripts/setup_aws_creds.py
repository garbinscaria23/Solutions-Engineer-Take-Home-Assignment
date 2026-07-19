# scripts/setup_aws_creds.py
import os

AWS_DIR = os.path.expanduser("~/.aws")
CREDENTIALS_PATH = os.path.join(AWS_DIR, "credentials")
CONFIG_PATH = os.path.join(AWS_DIR, "config")

def configure_aws():
    if not os.path.exists(AWS_DIR):
        os.makedirs(AWS_DIR)

    # Write credentials
    with open(CREDENTIALS_PATH, "w") as f:
        f.write("[default]\n")
        f.write("aws_access_key_id = AKIAR3HUOQP66B72YV22\n")
        f.write("aws_secret_access_key = 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\n")

    # Write config
    with open(CONFIG_PATH, "w") as f:
        f.write("[default]\n")
        f.write("region = ap-south-1\n")
        f.write("output = json\n")

    print("AWS credentials and config successfully configured locally on this machine!")

if __name__ == "__main__":
    configure_aws()
