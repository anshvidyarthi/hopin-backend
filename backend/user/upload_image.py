from werkzeug.utils import secure_filename
import boto3, os

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

def upload_file_to_s3(
    file_obj,
    filename,
    profile_id: str,
    user_name: str,
    bucket_env_var: str,
    folder: str,
):
    bucket = os.getenv(bucket_env_var)
    if not bucket:
        raise ValueError(f"{bucket_env_var} not set in environment")

    safe_username = secure_filename(user_name)
    safe_filename = secure_filename(filename)

    key = f"{folder}/{profile_id}/{safe_username}_{safe_filename}"

    extra_args = {"ContentType": file_obj.content_type}

    s3.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra_args)

    return f"https://{bucket}.s3.amazonaws.com/{key}"

def upload_profile_photo_to_s3(file_obj, filename, profile_id: str, user_name: str):
    return upload_file_to_s3(
        file_obj=file_obj,
        filename=filename,
        profile_id=profile_id,
        user_name=user_name,
        bucket_env_var="S3_PROFILE_PHOTOS_BUCKET_NAME",
        folder="profile-photos",
    )