"""Factory function to build the infra task collection."""

from pathlib import Path

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import task

from invoke_tasks.infra.backend_bucket import create_backend_bucket as _create_backend_bucket
from invoke_tasks.infra.cloud_provider import configure_cloud_provider
from invoke_tasks.infra.infra_config import InfraConfig, load_infra_config, validate_infra_yaml


def build_infra_collection(config: InfraConfig | None = None) -> Collection:
    """Build and return the infra task collection.

    Args:
        config: Optional pre-loaded InfraConfig. If None, loads from cwd.
    """
    if config is None:
        config = load_infra_config()

    def _infra_dir(env: str) -> Path:
        return config.project_root / config.get_env(env).infra_dir

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

    def _init_cmd(env: str) -> str:
        """Build the terraform init command string."""
        bucket = config.get_backend_bucket(env)
        backend_args = f'-backend-config="bucket={bucket.bucket_name}"'
        match bucket.hosted_on.upper():
            case "AWS":
                backend_args += (
                    f' -backend-config="key=terraform/state"'
                    f' -backend-config="region={bucket.region}"'
                )
            case "GCP":
                backend_args += f' -backend-config="prefix=terraform/state"'
        return (
            f"cd {_infra_dir(env)} && "
            f"terraform init --upgrade -reconfigure {backend_args}"
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def init(c: Context, env: str) -> None:
        """
        Runs terraform init with backend config.

        If you get this error:
        Error: Failed to get existing workspaces: querying Cloud Storage failed:
         storage: bucket doesn't exist
        Then you have to run the infra.create-backend-bucket first
        """
        c.run(_init_cmd(env), pty=True)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def plan(c: Context, env: str) -> None:
        """Runs terraform plan with backend config."""
        c.run(
            f"{_init_cmd(env)} && "
            f"terraform plan --var-file=./{env.lower()}.tfvars",
            pty=True,
        )

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
        c.run(_init_cmd(env))
        auto_approve_flag = "-auto-approve" if auto_approve else ""
        import subprocess

        subprocess.run(
            f"cd {_infra_dir(env)} && "
            f"terraform apply {auto_approve_flag} "
            f"--var-file=./{env.lower()}.tfvars",
            shell=True,
            check=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "auto_approve": (
                "Auto-approve terraform destroy without prompting (default: False)"
            ),
        },
    )
    def destroy(c: Context, env: str, auto_approve: bool = False) -> None:
        """Runs terraform destroy with backend config."""
        c.run(_init_cmd(env))
        auto_approve_flag = "-auto-approve" if auto_approve else ""
        import subprocess

        subprocess.run(
            f"cd {_infra_dir(env)} && "
            f"terraform destroy {auto_approve_flag} "
            f"--var-file=./{env.lower()}.tfvars",
            shell=True,
            check=True,
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def output(c: Context, env: str) -> None:
        """Runs terraform output to display all outputs."""
        c.run(
            f"{_init_cmd(env)} && terraform output",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "output": "Name of the output to fetch.",
        },
    )
    def raw_output(c: Context, env: str, output: str) -> None:
        """Runs terraform output to fetch a specific value."""
        c.run(
            f"{_init_cmd(env)} && terraform output -raw {output}",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "resource": "Name of the object to remove from state.",
        },
    )
    def state_remove(c: Context, env: str, resource: str) -> None:
        """Removes object from terraform state."""
        c.run(
            f"{_init_cmd(env)} && terraform state rm {resource}",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
        },
    )
    def state_list(c: Context, env: str) -> None:
        """Lists available instances in the state."""
        c.run(
            f"{_init_cmd(env)} && terraform state list",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "json": "Output in JSON format instead of human-readable.",
        },
    )
    def show(c: Context, env: str, json: bool = False) -> None:
        """Runs terraform show to display the full state."""
        json_flag = "-json" if json else ""
        c.run(
            f"{_init_cmd(env)} && terraform show {json_flag}",
            pty=not json,
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def validate(c: Context, env: str) -> None:
        """Validates the Terraform configuration files."""
        c.run(f"{_init_cmd(env)} && terraform validate", pty=True)

    @task(
        name="import",
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "address": "Terraform resource address (e.g. aws_s3_bucket.website).",
            "resource_id": "Cloud resource ID to import (e.g. my-bucket-name).",
        },
    )
    def import_resource(c: Context, env: str, address: str, resource_id: str) -> None:
        """Imports an existing cloud resource into Terraform state."""
        c.run(
            f"{_init_cmd(env)} && "
            f"terraform import --var-file=./{env.lower()}.tfvars {address} {resource_id}",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "resource": "Terraform resource address to inspect.",
        },
    )
    def state_show(c: Context, env: str, resource: str) -> None:
        """Shows full details of a single resource in state."""
        c.run(f"{_init_cmd(env)} && terraform state show {resource}", pty=True)

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "source": "Source resource address.",
            "destination": "Destination resource address.",
        },
    )
    def state_mv(c: Context, env: str, source: str, destination: str) -> None:
        """Moves a resource within Terraform state."""
        c.run(
            f"{_init_cmd(env)} && terraform state mv {source} {destination}",
            pty=True,
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def workspace_list(c: Context, env: str) -> None:
        """Lists all Terraform workspaces."""
        c.run(f"{_init_cmd(env)} && terraform workspace list", pty=True)

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "name": "Name of the workspace to create.",
        },
    )
    def workspace_new(c: Context, env: str, name: str) -> None:
        """Creates a new Terraform workspace."""
        c.run(f"{_init_cmd(env)} && terraform workspace new {name}", pty=True)

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "name": "Name of the workspace to select.",
        },
    )
    def workspace_select(c: Context, env: str, name: str) -> None:
        """Selects an existing Terraform workspace."""
        c.run(f"{_init_cmd(env)} && terraform workspace select {name}", pty=True)

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "name": "Name of the workspace to delete.",
        },
    )
    def workspace_delete(c: Context, env: str, name: str) -> None:
        """Deletes a Terraform workspace."""
        c.run(f"{_init_cmd(env)} && terraform workspace delete {name}", pty=True)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def workspace_show(c: Context, env: str) -> None:
        """Shows the name of the current Terraform workspace."""
        c.run(f"{_init_cmd(env)} && terraform workspace show", pty=True)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def providers(c: Context, env: str) -> None:
        """Shows required providers and their version constraints."""
        c.run(f"{_init_cmd(env)} && terraform providers", pty=True)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def graph(c: Context, env: str) -> None:
        """Outputs a dependency graph in DOT format (pipe to graphviz: | dot -Tsvg)."""
        c.run(f"{_init_cmd(env)} && terraform graph", pty=False)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def console(c: Context, env: str) -> None:
        """Opens an interactive console for evaluating Terraform expressions."""
        c.run(
            f"{_init_cmd(env)} && "
            f"terraform console --var-file=./{env.lower()}.tfvars",
            pty=True,
        )

    @task(
        help={
            "env": "Environment name (e.g. PROD). Either DEV or PROD.",
            "lock_id": "Lock ID shown in the error message.",
        },
    )
    def force_unlock(c: Context, env: str, lock_id: str) -> None:
        """Releases a stuck Terraform state lock."""
        c.run(
            f"{_init_cmd(env)} && terraform force-unlock -force {lock_id}",
            pty=True,
        )

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def get(c: Context, env: str) -> None:
        """Downloads and updates Terraform modules without reinitialising the backend."""
        c.run(f"cd {_infra_dir(env)} && terraform get", pty=True)

    @task(help={"env": "Environment name (e.g. PROD). Either DEV or PROD."})
    def refresh(c: Context, env: str) -> None:
        """Updates the state file to match real infrastructure."""
        c.run(
            f"{_init_cmd(env)} && "
            f"terraform refresh --var-file=./{env.lower()}.tfvars",
            pty=True,
        )

    @task(name="validate-yaml-config", help={})
    def validate_yaml_config(c: Context) -> None:
        """Validates the structure of infra.yaml (all envs, buckets, and tfvars)."""
        try:
            validate_infra_yaml(config.project_root)
            print("infra.yaml is valid.")
        except (KeyError, ValueError, FileNotFoundError) as e:
            print(f"infra.yaml validation failed:\n{e}")
            raise SystemExit(1)

    @task(help={})
    def fmt(c: Context) -> None:
        """Runs terraform fmt on all infra directories."""
        seen: set[Path] = set()
        for env_config in config.envs:
            infra_dir = config.project_root / env_config.infra_dir
            if infra_dir not in seen:
                seen.add(infra_dir)
                c.run(f"cd {infra_dir};terraform fmt --recursive")

    ns_infra = Collection("infra")
    ns_infra.add_task(create_backend_bucket)
    ns_infra.add_task(get_backend_bucket_name)
    ns_infra.add_task(set_cloud_provider)
    ns_infra.add_task(init)
    ns_infra.add_task(validate)
    ns_infra.add_task(plan)
    ns_infra.add_task(apply)
    ns_infra.add_task(destroy)
    ns_infra.add_task(output)
    ns_infra.add_task(raw_output)
    ns_infra.add_task(import_resource)
    ns_infra.add_task(state_remove)
    ns_infra.add_task(state_list)
    ns_infra.add_task(state_show)
    ns_infra.add_task(state_mv)
    ns_infra.add_task(show)
    ns_infra.add_task(workspace_list)
    ns_infra.add_task(workspace_new)
    ns_infra.add_task(workspace_select)
    ns_infra.add_task(workspace_delete)
    ns_infra.add_task(workspace_show)
    ns_infra.add_task(providers)
    ns_infra.add_task(graph)
    ns_infra.add_task(console)
    ns_infra.add_task(force_unlock)
    ns_infra.add_task(get)
    ns_infra.add_task(refresh)
    ns_infra.add_task(fmt)
    ns_infra.add_task(validate_yaml_config)

    return ns_infra
