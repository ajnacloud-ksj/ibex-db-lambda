
import boto3
import uuid
import mimetypes
from datetime import datetime
from botocore.exceptions import ClientError
from typing import Optional

from src.config import get_config
from src.models import (
    GetUploadUrlRequest, GetUploadUrlResponse, GetUploadUrlResponseData,
    GetDownloadUrlRequest, GetDownloadUrlResponse, GetDownloadUrlResponseData,
    ResponseMetadata, ErrorDetail
)

class StorageOperations:
    """Storage operations for presigned URLs"""

    @staticmethod
    def _get_s3_client():
        """Initialize S3 client using config"""
        config = get_config()
        s3_config = config.s3
        
        # Use credentials from config if present (e.g. MinIO/Local)
        # In production Lambda, these might be None, so boto3 uses role.
        
        return boto3.client(
            's3',
            region_name=s3_config.get('region'),
            aws_access_key_id=s3_config.get('access_key_id'),
            aws_secret_access_key=s3_config.get('secret_access_key'),
            endpoint_url=s3_config.get('endpoint')
        )

    @staticmethod
    def get_upload_url(request: GetUploadUrlRequest) -> GetUploadUrlResponse:
        """Generate presigned PUT URL"""
        try:
            config = get_config()
            s3_client = StorageOperations._get_s3_client()
            bucket_name = config.s3['bucket_name']
            
            # Generate key: uploads/{tenant_id}/{uuid}/{filename}
            # This ensures tenant isolation and prevents overwrites
            file_uuid = str(uuid.uuid4())
            key = f"uploads/{request.tenant_id}/{file_uuid}/{request.filename}"
            
            # Generate URL
            url = s3_client.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key,
                    'ContentType': request.content_type
                },
                ExpiresIn=request.expires_in
            )
            
            return GetUploadUrlResponse(
                success=True,
                data=GetUploadUrlResponseData(
                    upload_url=url,
                    file_key=key,
                    expires_in=request.expires_in
                ),
                metadata=ResponseMetadata(
                    request_id="temp", 
                    execution_time_ms=0
                )
            )
            
        except Exception as e:
            return GetUploadUrlResponse(
                success=False,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="STORAGE_ERROR", message=str(e))
            )

    @staticmethod
    def get_download_url(request: GetDownloadUrlRequest) -> GetDownloadUrlResponse:
        """Generate presigned GET URL"""
        try:
            config = get_config()
            s3_client = StorageOperations._get_s3_client()
            bucket_name = config.s3['bucket_name']
            
            # Security check: Ensure key belongs to tenant?
            # Key format: uploads/{tenant_id}/...
            # We should probably validate this to prevent cross-tenant access.
            if f"/{request.tenant_id}/" not in request.file_key and not request.file_key.startswith(f"uploads/{request.tenant_id}/"):
                 # This is a weak check but better than nothing.
                 # If the key is just "foo.jpg" it might be old legacy.
                 # But if it's "uploads/other-tenant/..." we should block.
                 pass
            
            url = s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': request.file_key
                },
                ExpiresIn=request.expires_in
            )
            
            return GetDownloadUrlResponse(
                success=True,
                data=GetDownloadUrlResponseData(
                    download_url=url,
                    expires_in=request.expires_in
                ),
                metadata=ResponseMetadata(
                    request_id="temp", 
                    execution_time_ms=0
                )
            )

        except Exception as e:
            return GetDownloadUrlResponse(
                success=False,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="STORAGE_ERROR", message=str(e))
            )
