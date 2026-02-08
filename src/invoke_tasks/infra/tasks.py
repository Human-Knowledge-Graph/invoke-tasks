"""Factory function to build the infra task collection."""

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import task

from invoke_tasks.infra.backend_bucket import create_backend_bucket as _create_backend_bucket
from invoke_tasks.infra.cloud_provider import configure_cloud_provider
from invoke_tasks.infra.infra_config import InfraConfig, load_infra_config


def build_infra_collection(config: InfraConfig | None = None) -> Collection:
    """Build and return the infra task collection.

    Args:
        config: Optional pre-loaded InfraConfig. If None, loads from cwd.
    """
    if config is None:
        config = load_infra_config()

    infra_dir = config.project_root / "infra"

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def get_backend_bucket_name(c: Context, env: str) -> None:
        bucket = config.get_backend_bucket(env)
        print(f"Backend Bucket: {bucket.bucket_name}")

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def set_cloud_provider(c: Context, env: str) -> None:
        """Configures the cloud provider (AWS profile or GCP project) based on hosted_on."""
        env_config = config.get_env(env)
        configure_cloud_provider(c, env_config)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def create_backend_bucket(c: Context, env: str) -> None:
        """Build backend bucket for terraform state."""
        env_config = config.get_env(env)
        bucket = config.get_backend_bucket(env)
        _create_backend_bucket(c, env_config, bucket)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def init(c: Context, env: str) -> None:
        """
        Runs terraform init with backend config.

        If you get this error:
        Error: Failed to get existing workspaces: querying Cloud Storage failed:
         storage: bucket doesn't exist
        Then you have to run the infra.create-backend-bucket first
        """
        bucket = config.get_backend_bucket(env)
        c.run(
            f"cd {infra_dir};"
            "terraform init --upgrade "
            f'-backend-config="bucket={bucket.bucket_name}" '
            f'-backend-config="prefix=terraform/state" ',
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def plan(c: Context, env: str) -> None:
        """Runs terraform plan with backend config."""
        init(c, env=env)
        c.run(f"cd {infra_dir};terraform plan --var-file=./{env.lower()}.tfvars ")

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "auto_approve": (
                "Auto-approve terraform apply without prompting (default: False)"
            ),
        },
    )
    def apply(c: Context, env: str, auto_approve: bool = False) -> None:
        """Runs terraform apply with backend config."""
        init(c, env=env)
        auto_approve_flag = "-auto-approve" if auto_approve else ""
        c.run(
            f"cd {infra_dir};terraform apply {auto_approve_flag} "
            f"--var-file=./{env.lower()}.tfvars ",
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "output": "Name of the output to fetch.",
        },
    )
    def raw_output(c: Context, env: str, output: str) -> None:
        """Runs terraform output to fetch a specific value."""
        init(c, env=env)
        c.run(f"cd {infra_dir};terraform output -raw {output}")

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "resource": "Name of the object to remove from state.",
        },
    )
    def state_remove(c: Context, env: str, resource: str) -> None:
        """Removes object from terraform state."""
        init(c, env=env)
        c.run(f"cd {infra_dir};terraform state rm {resource}")

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
        },
    )
    def state_list(c: Context, env: str) -> None:
        """Lists available instances in the state."""
        init(c, env=env)
        c.run(f"cd {infra_dir};terraform state list")

    @task(help={})
    def fmt(c: Context) -> None:
        """Runs terraform fmt."""
        c.run(f"cd {infra_dir};terraform fmt --recursive")

    ns_infra = Collection("infra")
    ns_infra.add_task(create_backend_bucket)
    ns_infra.add_task(get_backend_bucket_name)
    ns_infra.add_task(set_cloud_provider)
    ns_infra.add_task(init)
    ns_infra.add_task(plan)
    ns_infra.add_task(apply)
    ns_infra.add_task(raw_output)
    ns_infra.add_task(state_remove)
    ns_infra.add_task(state_list)
    ns_infra.add_task(fmt)

    return ns_infra
