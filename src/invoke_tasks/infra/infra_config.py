from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _discover_project_root() -> Path:
    """Walk up from cwd looking for infra.yaml."""
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "infra.yaml").exists():
            return parent
    raise FileNotFoundError(
        "Could not find infra.yaml in current directory or any parent. "
        "Pass project_root explicitly or ensure infra.yaml exists."
    )


@dataclass
class EnvConfig:
    env: str
    hosted_on: str
    aws_profile: str | None
    gcp_project_id: str | None


@dataclass
class BackendBucket:
    env: str
    hosted_on: str
    bucket_name: str
    region: str | None


@dataclass
class TfVars:
    env: str
    variables: dict[str, Any]


@dataclass
class InfraConfig:
    envs: list[EnvConfig]
    backend_buckets: list[BackendBucket]
    tfvars: list[TfVars]
    project_root: Path

    def get_env(self, env: str) -> EnvConfig:
        for e in self.envs:
            if e.env.upper() == env.upper():
                return e
        raise ValueError(
            f"No env configured for '{env}'. Available: {[e.env for e in self.envs]}"
        )

    def get_backend_bucket(self, env: str) -> BackendBucket:
        for bucket in self.backend_buckets:
            if bucket.env.upper() == env.upper():
                return bucket
        raise ValueError(
            f"No backend bucket configured for env '{env}'. "
            f"Available: {[b.env for b in self.backend_buckets]}"
        )

    def get_tfvars(self, env: str) -> TfVars:
        for tv in self.tfvars:
            if tv.env.upper() == env.upper():
                return tv
        raise ValueError(
            f"No tfvars configured for env '{env}'. "
            f"Available: {[tv.env for tv in self.tfvars]}"
        )


def _read_infra_config(project_root: Path) -> dict:
    infra_yaml_path = project_root / "infra.yaml"
    if not infra_yaml_path.exists():
        raise FileNotFoundError(
            f"infra.yaml not found at {infra_yaml_path}. "
            f"Please create it in the project root: {project_root}"
        )
    with open(infra_yaml_path) as f:
        return yaml.safe_load(f)


def load_infra_config(project_root: Path | str | None = None) -> InfraConfig:
    if project_root is None:
        resolved_root = _discover_project_root()
    else:
        resolved_root = Path(project_root).resolve()

    infra_yaml_path = resolved_root / "infra.yaml"
    raw = _read_infra_config(resolved_root)
    for section in ("envs", "backend_buckets"):
        if section not in raw:
            raise KeyError(
                f"'{section}' key not found in {infra_yaml_path}. "
                f"Please define {section} in infra.yaml."
            )

    envs = []
    for env, values in raw["envs"].items():
        if "hosted_on" not in values:
            raise KeyError(
                f"Missing 'hosted_on' for env '{env}' in {infra_yaml_path}."
            )
        envs.append(
            EnvConfig(
                env=env,
                hosted_on=values["hosted_on"],
                aws_profile=values.get("aws_profile"),
                gcp_project_id=values.get("gcp_project_id"),
            )
        )

    buckets = []
    for env, values in raw["backend_buckets"].items():
        for key in ("hosted_on", "bucket_name"):
            if key not in values:
                raise KeyError(
                    f"Missing '{key}' for env '{env}' in {infra_yaml_path}."
                )
        buckets.append(
            BackendBucket(
                env=env,
                hosted_on=values["hosted_on"],
                bucket_name=values["bucket_name"],
                region=values.get("region"),
            )
        )

    tfvars: list[TfVars] = []
    if "tfvars" in raw:
        env_names = {e.env for e in envs}
        tfvars_keys = set(raw["tfvars"].keys())
        if env_names != tfvars_keys:
            raise KeyError(
                f"tfvars keys {tfvars_keys} do not match envs keys {env_names} "
                f"in {infra_yaml_path}. They must have the same environments."
            )

        tfvars = [
            TfVars(env=env, variables=values)
            for env, values in raw["tfvars"].items()
        ]

    config = InfraConfig(
        envs=envs,
        backend_buckets=buckets,
        tfvars=tfvars,
        project_root=resolved_root,
    )
    if tfvars:
        _generate_tfvars_files(resolved_root, config.tfvars)
    return config


def _format_tfvars_value(value: Any) -> str:
    """Format a Python value as a Terraform tfvars value."""
    if isinstance(value, list):
        items = ",\n".join(f'  "{item}"' for item in value)
        return f"[\n{items},\n]"
    elif isinstance(value, dict):
        items = "\n".join(f'  "{k}" = "{v}"' for k, v in value.items())
        return f"{{\n{items}\n}}"
    else:
        return f'"{value}"'


def _generate_tfvars_files(project_root: Path, tfvars: list[TfVars]) -> None:
    infra_dir = project_root / "infra"
    if not infra_dir.exists():
        raise FileNotFoundError(
            f"infra/ directory not found at {infra_dir}. "
            f"Please create it in the project root: {project_root}"
        )
    for tv in tfvars:
        tfvars_path = infra_dir / f"{tv.env.lower()}.tfvars"
        lines = [
            f"{key} = {_format_tfvars_value(value)}"
            for key, value in tv.variables.items()
        ]
        tfvars_path.write_text("\n".join(lines) + "\n")
