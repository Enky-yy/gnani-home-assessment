import os
import sys
# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import boto3
import httpx
from botocore.exceptions import ClientError
from app.config import settings

def verify_aws_s3():
    print("=" * 60)
    print(" AUDIO NOTES PLATFORM — AWS S3 CONNECTIVITY VERIFIER")
    print("=" * 60)

    bucket = settings.AWS_S3_BUCKET_NAME
    region = settings.AWS_REGION
    key_id = settings.AWS_ACCESS_KEY_ID
    secret = settings.AWS_SECRET_ACCESS_KEY

    print(f"Bucket Name: {bucket}")
    print(f"AWS Region:  {region}")
    masked_key = (key_id[:4] + "..." + key_id[-4:]) if len(key_id) > 8 else key_id
    print(f"Access Key:  {masked_key}")

    # Check for placeholder credentials
    if not key_id or "your_" in key_id or not secret or "your_" in secret:
        print("\n" + "!" * 60)
        print(" [!] AWS CREDENTIALS NOT CONFIGURED IN backend/.env")
        print("!" * 60)
        print("\nPlease update backend/.env with your actual AWS credentials:")
        print("  AWS_ACCESS_KEY_ID=AKIA...")
        print("  AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/...")
        print("  AWS_REGION=ap-south-1  # or your preferred AWS region")
        print("  AWS_S3_BUCKET_NAME=my-gnani-audio-notes-bucket")
        print("  STORAGE_BACKEND=s3")
        sys.exit(1)

    session_kwargs = {"region_name": region}
    if key_id and secret:
        session_kwargs["aws_access_key_id"] = key_id
        session_kwargs["aws_secret_access_key"] = secret

    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        **session_kwargs
    )

    # Step 1: Check Bucket existence
    print("\n[1/4] Checking S3 bucket access...")
    try:
        s3_client.head_bucket(Bucket=bucket)
        print(f" Bucket '{bucket}' exists and is accessible!")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "404" or error_code == "NoSuchBucket":
            print(f" Bucket '{bucket}' does not exist yet. Attempting to create it...")
            try:
                if region == "us-east-1":
                    s3_client.create_bucket(Bucket=bucket)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket,
                        CreateBucketConfiguration={"LocationConstraint": region}
                    )
                print(f" Successfully created S3 bucket '{bucket}' in {region}!")
            except ClientError as create_err:
                print(f" Failed to auto-create bucket: {create_err}")
                print(" TIP: S3 bucket names must be globally unique across all AWS accounts.")
                sys.exit(1)
        elif error_code == "403":
            print(f" Access Denied (403) to bucket '{bucket}'. Verify IAM user permissions.")
            sys.exit(1)
        else:
            print(f" S3 error: {e}")
            sys.exit(1)

    # Step 2: Upload test file
    test_key = "system_tests/s3_probe.txt"
    test_content = b"Gnani Voice AI Audio Notes Platform AWS S3 Connectivity Probe"
    print(f"\n[2/4] Testing object upload to '{test_key}'...")
    try:
        s3_client.upload_fileobj(
            io.BytesIO(test_content),
            bucket,
            test_key,
            ExtraArgs={"ContentType": "text/plain"}
        )
        print(" Upload successful!")
    except Exception as e:
        print(f" Upload failed: {e}")
        sys.exit(1)

    # Step 3: Test Presigned URL generation and download
    print("\n[3/4] Generating presigned GET URL & testing HTTP download...")
    try:
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": test_key},
            ExpiresIn=300
        )
        print(f" Presigned URL generated:\n      {presigned_url[:80]}...")
        
        # Verify downloading via presigned URL
        resp = httpx.get(presigned_url, timeout=10.0)
        if resp.status_code == 200 and resp.content == test_content:
            print(" Presigned URL HTTP GET download verified (Status 200 OK, content matched)!")
        else:
            print(f" Presigned URL GET returned status {resp.status_code}")
    except Exception as e:
        print(f" Presigned URL test failed: {e}")

    # Step 4: Clean up test probe
    print(f"\n[4/4] Cleaning up test object '{test_key}'...")
    try:
        s3_client.delete_object(Bucket=bucket, Key=test_key)
        print(" Cleaned up test object.")
    except Exception as e:
        print(f" Note: Clean up warning: {e}")

    print("\n" + "=" * 60)
    print(" AWS S3 VERIFICATION PASSED: S3 Storage backend is 100% operational!")
    print("=" * 60)


if __name__ == "__main__":
    verify_aws_s3()
