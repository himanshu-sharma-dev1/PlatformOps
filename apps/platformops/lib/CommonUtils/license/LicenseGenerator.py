import subprocess

def cutil_license_generator(input_file, output_file, password='your_password_here'):
    openssl_cmd = [
        "openssl",
        "enc",
        "-aes-256-cbc",   # Encryption algorithm (AES 256-bit in CBC mode)
        "-salt",          # Add salt for more secure encryption
        "-in", input_file,
        "-out", output_file,
        "-k", password,
    ]

    try:
        # Run the OpenSSL command to encrypt the file
        subprocess.run(openssl_cmd, check=True)
        print("File encrypted successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error while encrypting the file: {e}")
        return False