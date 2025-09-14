import os
import boto3
from typing import Optional, Tuple
from urllib.parse import urlparse


def _s3_client(region: Optional[str] = None):
    region_name = region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    client_kwargs = {"region_name": region_name}
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token = os.getenv("AWS_SESSION_TOKEN")
    
    print(f"AWS Region: {region_name}")
    print(f"Has AWS Key: {bool(aws_access_key_id)}")
    print(f"Has AWS Secret: {bool(aws_secret_access_key)}")
    
    if aws_access_key_id and aws_secret_access_key:
        client_kwargs.update({
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
        })
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token
    return boto3.client("s3", **client_kwargs)


def build_post_object_key(file_name: str) -> str:
    return f"uploads/post/{file_name}"


def generate_presigned_put_url(file_name: str, content_type: Optional[str] = None, expires_in: int = 3600) -> Tuple[str, str, str]:
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_S3_BUCKET") or "zpc-app"
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    key = build_post_object_key(file_name)
    
    print(f"=== Generating presigned PUT URL ===")
    print(f"Bucket: {bucket}")
    print(f"Region: {region}")
    print(f"Key: {key}")
    print(f"Content-Type: {content_type}")
    print(f"Expires in: {expires_in} seconds")
    
    s3 = _s3_client(region)
    
    params = {"Bucket": bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    
    print(f"S3 params: {params}")
    
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=expires_in,
    )
    
    # Use the correct S3 endpoint format
    public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    
    print(f"Generated presigned URL: {url}")
    print(f"Public URL: {public_url}")
    print(f"=== End presigned URL generation ===")
    
    return url, key, public_url


def generate_presigned_get_url_from_url(s3_url: str, expires_in: int = 3600) -> Optional[str]:
    try:
        print(f"\nGenerating presigned GET URL for: {s3_url}")
        
        # Parse S3 URL using urlparse
        parsed = urlparse(s3_url)
        if not parsed.netloc or not parsed.path:
            print(f"Invalid S3 URL format: {s3_url}")
            return None
            
        # Extract bucket from hostname (e.g., "zpc-app.s3.us-east-1.amazonaws.com")
        hostname_parts = parsed.netloc.split('.')
        bucket = hostname_parts[0]
        region = hostname_parts[2]  # us-east-1
        
        # Remove leading slash from path to get key
        key = parsed.path.lstrip('/')
        
        print(f"Parsed bucket: {bucket}")
        print(f"Parsed region: {region}")
        print(f"Parsed key: {key}")
        
        s3 = _s3_client(region)
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expires_in
        )
        print(f"Generated presigned URL: {url}")
        return url
    except Exception as e:
        print(f"Error generating presigned GET URL: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None