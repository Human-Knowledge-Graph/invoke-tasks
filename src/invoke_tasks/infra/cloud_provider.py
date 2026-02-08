from invoke.context import Context

from invoke_tasks.infra.infra_config import EnvConfig


def _set_aws_profile(c: Context, aws_profile: str) -> None:
    c.run(f"export AWS_PROFILE={aws_profile}")
    c.run(f"aws sts get-caller-identity --profile {aws_profile}")


def _set_google_project(c: Context, gcp_project_id: str) -> None:
    c.run(f"gcloud config set project {gcp_project_id}")


def configure_cloud_provider(c: Context, env_config: EnvConfig) -> None:
    match env_config.hosted_on.upper():
        case "AWS":
            if env_config.aws_profile is None:
                raise ValueError(
                    f"Cannot configure AWS: no aws_profile configured "
                    f"for env '{env_config.env}'."
                )
            _set_aws_profile(c, env_config.aws_profile)
        case "GCP":
            if env_config.gcp_project_id is None:
                raise ValueError(
                    f"Cannot configure GCP: no gcp_project_id configured "
                    f"for env '{env_config.env}'."
                )
            _set_google_project(c, env_config.gcp_project_id)
        case _:
            raise NotImplementedError(
                f"Unsupported hosted_on: '{env_config.hosted_on}'"
            )
