"""
AWS S3 Utilities
Helper functions for uploading and downloading files from AWS S3
"""

import os
import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class S3Utils:
    """Utility class for AWS S3 operations"""
    
    def __init__(self):
        """Initialize S3 client with credentials from environment variables"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            self._credentials_validated = False
            logger.info("S3 client initialized (credentials will be validated on first use)")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise
    
    def _validate_credentials(self):
        """Validate AWS credentials on first use"""
        if not self._credentials_validated:
            try:
                # Test credentials by listing buckets
                self.s3_client.list_buckets()
                self._credentials_validated = True
                logger.info("AWS credentials validated successfully")
            except NoCredentialsError:
                logger.error("AWS credentials not found")
                raise Exception("AWS credentials not configured. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables.")
            except Exception as e:
                logger.error(f"AWS credential validation failed: {str(e)}")
                raise Exception(f"AWS credential validation failed: {str(e)}")
    
    def download_file(self, bucket: str, key: str, local_path: str) -> bool:
        """
        Download a file from S3 to local filesystem
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            local_path: Local file path to save the downloaded file
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            Exception: If download fails
        """
        self._validate_credentials()  # Validate credentials before use
        
        try:
            logger.info(f"Downloading s3://{bucket}/{key} to {local_path}")
            self.s3_client.download_file(bucket, key, local_path)
            
            # Verify file was downloaded
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                logger.info(f"Successfully downloaded {key} ({os.path.getsize(local_path)} bytes)")
                return True
            else:
                raise Exception("Downloaded file is empty or doesn't exist")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise Exception(f"File not found in S3: s3://{bucket}/{key}")
            elif error_code == 'NoSuchBucket':
                raise Exception(f"Bucket not found: {bucket}")
            else:
                raise Exception(f"S3 download failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to download s3://{bucket}/{key}: {str(e)}")
            raise
    
    def upload_file(self, local_path: str, bucket: str, key: str) -> str:
        """
        Upload a file from local filesystem to S3
        
        Args:
            local_path: Local file path to upload
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            Public URL of the uploaded file
            
        Raises:
            Exception: If upload fails
        """
        self._validate_credentials()  # Validate credentials before use
        
        try:
            # Verify local file exists
            if not os.path.exists(local_path):
                raise Exception(f"Local file not found: {local_path}")
            
            file_size = os.path.getsize(local_path)
            logger.info(f"Uploading {local_path} to s3://{bucket}/{key} ({file_size} bytes)")
            
            # Upload file
            self.s3_client.upload_file(local_path, bucket, key)
            
            # Generate public URL
            region = os.getenv('AWS_REGION', 'us-east-1')
            if region == 'us-east-1':
                url = f"https://s3.amazonaws.com/{bucket}/{key}"
            else:
                url = f"https://s3-{region}.amazonaws.com/{bucket}/{key}"
            
            logger.info(f"Successfully uploaded to {url}")
            return url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise Exception(f"Bucket not found: {bucket}")
            else:
                raise Exception(f"S3 upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to s3://{bucket}/{key}: {str(e)}")
            raise
    
    def file_exists(self, bucket: str, key: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        self._validate_credentials()  # Validate credentials before use
        
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.error(f"Error checking if s3://{bucket}/{key} exists: {str(e)}")
                return False
    
    def get_file_size(self, bucket: str, key: str) -> Optional[int]:
        """
        Get the size of a file in S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            File size in bytes, or None if file doesn't exist
        """
        self._validate_credentials()  # Validate credentials before use
        
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            return response['ContentLength']
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            else:
                logger.error(f"Error getting size of s3://{bucket}/{key}: {str(e)}")
                return None
    
    def delete_file(self, bucket: str, key: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        self._validate_credentials()  # Validate credentials before use
        
        try:
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Deleted s3://{bucket}/{key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete s3://{bucket}/{key}: {str(e)}")
            return False 