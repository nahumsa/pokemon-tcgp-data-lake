import pyarrow as pa
import pyarrow.parquet as pq
import boto3
from pydantic import BaseModel
from io import BytesIO
from botocore.exceptions import BotoCoreError, NoCredentialsError

from configs import BaseS3Config


class LoadDataToS3:
    def __init__(self, config: BaseS3Config) -> None:
        self.s3_client = boto3.client(
            config.service_name,
            endpoint_url=config.endpoint_url,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
        )

    def _convert_pydantic_to_parquet(self, model_instances: list[BaseModel]) -> bytes:
        if not model_instances:
            raise ValueError("Model list is empty")

        data_dicts = [model.model_dump() for model in model_instances]
        table = pa.Table.from_pydict({key: [d[key] for d in data_dicts] for key in data_dicts[0]})

        buffer = BytesIO()
        pq.write_table(table, buffer)
        return buffer.getvalue()

    def _create_bucket_if_not_exists(self, bucket_name: str):
        try:
            # List existing buckets
            existing_buckets = [b["Name"] for b in self.s3_client.list_buckets()["Buckets"]]
            if bucket_name not in existing_buckets:
                self.s3_client.create_bucket(Bucket=bucket_name)
                print(f"Bucket '{bucket_name}' created successfully.")

            else:
                print(f"Bucket '{bucket_name}' already exists.")

        except BotoCoreError as e:
            print(f"Error checking/creating bucket: {e}")

    def load(self, data: list[BaseModel], bucket_name: str, object_name: str):
        try:
            parquet_data = self._convert_pydantic_to_parquet(data)
            self._create_bucket_if_not_exists(bucket_name)
            self.s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=parquet_data)
            print(f"Successfully uploaded {object_name} to bucket {bucket_name}")

        except NoCredentialsError:
            print("credentials not found.")

        except BotoCoreError as e:
            print(f"error: {e}")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")


