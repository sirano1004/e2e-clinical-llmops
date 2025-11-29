import certifi
import os

# 1. Path to your downloaded Zscaler cert
ZSCALER_CERT_PATH = "zscaler.pem" # Make sure this file exists!

# 2. Path to the venv's internal certificate bundle
venv_cert_path = certifi.where()

print(f"📍 Target Bundle: {venv_cert_path}")

# 3. Read Zscaler Cert
if not os.path.exists(ZSCALER_CERT_PATH):
    print(f"❌ Error: Could not find {ZSCALER_CERT_PATH}")
    print("Please export the Zscaler root CA and save it in this folder.")
else:
    with open(ZSCALER_CERT_PATH, "r") as f:
        zscaler_content = f.read()

    # 4. Check if already added
    with open(venv_cert_path, "r") as f:
        current_bundle = f.read()

    if "Zscaler" in current_bundle or zscaler_content in current_bundle:
        print("✅ Zscaler certificate is already present in the bundle.")
    else:
        # 5. Append
        print("🔄 Appending Zscaler certificate...")
        with open(venv_cert_path, "a") as f:
            f.write("\n\n# Zscaler Custom Cert\n")
            f.write(zscaler_content)
        print("✅ Success! Restart your Spyder kernel.")