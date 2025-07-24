import boto3, os
from dotenv import load_dotenv
from datetime import datetime
from ..user.upload_image import upload_file_to_s3

load_dotenv()

rekognition = boto3.client(
    'rekognition',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

def upload_license_to_s3(file_obj, filename, user_id: str, user_name: str):
    return upload_file_to_s3(
        file_obj=file_obj,
        filename=filename,
        user_id=user_id,
        user_name=user_name,
        bucket_env_var="S3_LICENSES_BUCKET_NAME",
        folder="licenses"
    )

def analyze_image(bucket, key):
    response = rekognition.detect_text(Image={"S3Object": {"Bucket": bucket, "Name": key}})
    return response

def validate_license_fields(detections):
    if not detections:
        return {
            "valid": False,
            "error": "No text detected in license image",
            "name": None,
            "license_number": None,
            "expiration_date": None,
        }

    lines = [d["DetectedText"] for d in detections if d["Type"] == "LINE"]

    # Extract FN and LN lines
    first_name = next((line.replace("FN", "").strip() for line in lines if line.startswith("FN ")), None)
    last_name = next((line.replace("LN", "").strip() for line in lines if line.startswith("LN ")), None)

    name = f"{first_name} {last_name}" if first_name and last_name else None

    # Extract license number (look for line starting with DL)
    license_line = next((line for line in lines if line.startswith("DL ")), None)
    license_number = license_line.split()[-1] if license_line else None

    # Extract expiration date (look for line starting with EXP)
    expiration_line = next((line for line in lines if line.startswith("EXP ")), None)
    expiration_date = None
    if expiration_line:
        try:
            expiration_date = datetime.strptime(expiration_line.replace("EXP", "").strip(), "%m/%d/%Y")
        except ValueError:
            pass

    if not name or not license_number:
        return {
            "valid": False,
            "error": "Missing required fields: name or license number",
            "name": name,
            "license_number": license_number,
            "expiration_date": expiration_date,
        }

    if expiration_date and expiration_date < datetime.utcnow():
        return {
            "valid": False,
            "error": "License is expired",
            "name": name,
            "license_number": license_number,
            "expiration_date": expiration_date,
        }

    return {
        "valid": True,
        "error": None,
        "name": name,
        "license_number": license_number,
        "expiration_date": expiration_date,
    }

from difflib import SequenceMatcher

def is_name_match(account_name: str, license_name: str, threshold: float = 0.8) -> bool:
    """
    Compare account name to license name using a similarity threshold.
    """
    account = account_name.strip().lower()
    license = license_name.strip().lower()
    ratio = SequenceMatcher(None, account, license).ratio()
    return ratio >= threshold