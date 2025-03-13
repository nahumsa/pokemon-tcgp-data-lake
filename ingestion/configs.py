from typing import Optional
from pydantic_settings import BaseSettings


class BaseS3Config(BaseSettings):
    aws_access_key_id: str
    aws_secret_access_key: str
    endpoint_url: Optional[str] = None
    service_name: str = "s3"
    region_name: Optional[str] = None

