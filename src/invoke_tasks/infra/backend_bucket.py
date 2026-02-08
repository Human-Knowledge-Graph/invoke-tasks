from invoke.context import Context

from invoke_tasks.infra.infra_config import BackendBucket, EnvConfig


def _create_aws_bucket(
    c: Context, bucket_name: str, aws_profile: str, region: str | None
) -> None:
    location = ""
    if region and region != "us-east-1":
        location = (
            f" --create-bucket-configuration LocationConstraint={region}"
            f" --region {region}"
        )
    c.run(
        f"aws s3api create-bucket --bucket {bucket_name}"
        f" --profile {aws_profile}{location}"
    )


def _create_gcp_bucket(c: Context, bucket_name: str, gcp_project_id: str) -> None:
    c.run(f"gcloud config set project {gcp_project_id}")
    c.run(f"gsutil mb -p {gcp_project_id} gs://{bucket_name}")


def create_backend_bucket(
    c: Context, env_config: EnvConfig, bucket: BackendBucket
) -> None:
    match bucket.hosted_on.upper():
        case "AWS":
            if env_config.aws_profile is None:
                raise ValueError(
                    f"Cannot create AWS bucket: no aws_profile configured "
                    f"for env '{env_config.env}'."
                )
            _create_aws_bucket(c, bucket.bucket_name, env_config.aws_profile, bucket.region)
        case "GCP":
            if env_config.gcp_project_id is None:
                raise ValueError(
                    f"Cannot create GCP bucket: no gcp_project_id configured "
                    f"for env '{env_config.env}'."
                )
            _create_gcp_bucket(c, bucket.bucket_name, env_config.gcp_project_id)
        case _:
            raise NotImplementedError(f"Unsupported hosted_on: '{bucket.hosted_on}'")
