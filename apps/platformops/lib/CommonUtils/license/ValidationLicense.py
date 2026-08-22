import socket
import subprocess
import json
from datetime import datetime
import os
# from CommonUtils.logs.AppLogging import utils_logger

def _get_system_hostname():
    try:
        hostname = socket.gethostname()
        return hostname
    except socket.error as e:
        print("Error while getting the hostname:", e)
        return None

def _decrypt_file(input_file, password):
    openssl_cmd = [
        "openssl",
        "enc",
        "-d",             # Decrypt mode
        "-aes-256-cbc",   # Encryption algorithm (AES 256-bit in CBC mode)
        "-in", input_file,
        "-k", password,
    ]

    try:
        # Run the OpenSSL command to decrypt the file and capture the output
        result = subprocess.run(openssl_cmd, check=True, capture_output=True, text=True)
        decrypted_content = result.stdout.strip()  # Extract the decrypted content

        print("Decrypted file content:")
        print(decrypted_content)
        return decrypted_content
    except subprocess.CalledProcessError as e:
        print(f"Error while decrypting the file: {e}")
        return f"Error while decrypting the file: {e}"



def _is_today_between_dates(date_dict):
    # Get today's date
    today = datetime.now().date()

    # Parse the start and end dates from the dictionary
    start_date = datetime.strptime(date_dict["start_date"], "%d/%m/%Y").date()
    end_date = datetime.strptime(date_dict["end_date"], "%d/%m/%Y").date()
    # grace_date = end_date + timedelta(days=30)
    # Check if today's date is between the start and end dates
    is_between_dates = start_date <= today <= end_date

    # Calculate the number of days left between today and the grace date
    return is_between_dates


def cutil_validate_license(input_path,password = "your_password_here"):

    # Construct the full path to the license file using os.path.join
    input_file = os.path.join(str(input_path), "license_file")

    # Print the constructed input file path for debugging
    print(f"Input file path: {input_file}")

    # Check if the 'license_file' exists in the specified path
    if not os.path.exists(input_file):
        print("License file not found.")
        return False

    decrypted_content = _decrypt_file(input_file, password)
    try:
        decrypted_content = eval(decrypted_content)
        decrypted_content = json.loads(decrypted_content)
    except Exception as e:
        print(f"Error decrypting and loading license file: {e}")
        return False

    if _get_system_hostname() != decrypted_content["host"]:
        return False

    result = _is_today_between_dates(decrypted_content)
    return result
