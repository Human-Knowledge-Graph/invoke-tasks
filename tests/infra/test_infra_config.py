"""Tests for infra_config module."""
import textwrap
from pathlib import Path

import pytest
import yaml

from invoke_tasks.infra.infra_config import (
    BackendBucket,
    EnvConfig,
    InfraConfig,
    TfVars,
    _discover_project_root,
    _format_tfvars_value,
    _generate_tfvars_files,
    _parse_variables_tf,
    _read_infra_config,
    _validate_tfvars_against_variables,
    load_infra_config,
)

MINIMAL_INFRA_YAML = {
    "envs": {
        "dev": {
            "hosted_on": "GCP",
            "gcp_project_id": "my-gcp-project",
            "infra_dir": "infra/dev",
        },
        "prod": {
            "hosted_on": "AWS",
            "aws_profile": "my-aws-profile",
            "infra_dir": "infra/prod",
        },
    },
    "backend_buckets": {
        "dev": {
            "hosted_on": "GCP",
            "bucket_name": "my-dev-bucket",
        },
        "prod": {
            "hosted_on": "AWS",
            "bucket_name": "my-prod-bucket",
            "region": "us-east-1",
        },
    },
}

VARIABLES_TF_CONTENT = textwrap.dedent("""\
    variable "region" {}
    variable "project_id" {
      default = "my-project"
    }
    variable "instance_count" {}
""")


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal project with infra.yaml (no tfvars section)."""
    (tmp_path / "infra.yaml").write_text(yaml.dump(MINIMAL_INFRA_YAML))
    return tmp_path


# ──────────────────────────────────────────────────────────────────────────────
# _discover_project_root
# ──────────────────────────────────────────────────────────────────────────────


class TestDiscoverProjectRoot:
    def test_finds_infra_yaml_in_cwd(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "infra.yaml").touch()
        monkeypatch.chdir(tmp_path)
        assert _discover_project_root() == tmp_path

    def test_finds_infra_yaml_in_parent(self, tmp_path: Path, monkeypatch) -> None:
        (tmp_path / "infra.yaml").touch()
        child = tmp_path / "subdir"
        child.mkdir()
        monkeypatch.chdir(child)
        assert _discover_project_root() == tmp_path

    def test_raises_when_not_found(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError, match="Could not find infra.yaml"):
            _discover_project_root()


# ──────────────────────────────────────────────────────────────────────────────
# InfraConfig methods
# ──────────────────────────────────────────────────────────────────────────────


class TestInfraConfig:
    @pytest.fixture
    def config(self) -> InfraConfig:
        return InfraConfig(
            envs=[
                EnvConfig(
                    env="dev",
                    hosted_on="GCP",
                    aws_profile=None,
                    gcp_project_id="my-proj",
                    infra_dir="infra/dev",
                ),
                EnvConfig(
                    env="prod",
                    hosted_on="AWS",
                    aws_profile="my-profile",
                    gcp_project_id=None,
                    infra_dir="infra/prod",
                ),
            ],
            backend_buckets=[
                BackendBucket(
                    env="dev", hosted_on="GCP", bucket_name="dev-bucket", region=None
                ),
                BackendBucket(
                    env="prod",
                    hosted_on="AWS",
                    bucket_name="prod-bucket",
                    region="us-east-1",
                ),
            ],
            tfvars=[
                TfVars(env="dev", variables={"region": "us-central1"}),
            ],
            project_root=Path("/fake/root"),
        )

    def test_get_env_exact_match(self, config: InfraConfig) -> None:
        assert config.get_env("dev").env == "dev"

    def test_get_env_case_insensitive(self, config: InfraConfig) -> None:
        assert config.get_env("DEV").env == "dev"
        assert config.get_env("Prod").env == "prod"

    def test_get_env_raises_for_unknown(self, config: InfraConfig) -> None:
        with pytest.raises(ValueError, match="No env configured for 'staging'"):
            config.get_env("staging")

    def test_get_backend_bucket_returns_correct_bucket(
        self, config: InfraConfig
    ) -> None:
        bucket = config.get_backend_bucket("dev")
        assert bucket.bucket_name == "dev-bucket"

    def test_get_backend_bucket_case_insensitive(self, config: InfraConfig) -> None:
        assert config.get_backend_bucket("DEV").bucket_name == "dev-bucket"

    def test_get_backend_bucket_raises_for_unknown(self, config: InfraConfig) -> None:
        with pytest.raises(
            ValueError, match="No backend bucket configured for env 'staging'"
        ):
            config.get_backend_bucket("staging")

    def test_get_tfvars_returns_correct_entry(self, config: InfraConfig) -> None:
        tv = config.get_tfvars("dev")
        assert tv.variables == {"region": "us-central1"}

    def test_get_tfvars_case_insensitive(self, config: InfraConfig) -> None:
        assert config.get_tfvars("DEV").env == "dev"

    def test_get_tfvars_raises_for_unknown(self, config: InfraConfig) -> None:
        with pytest.raises(ValueError, match="No tfvars configured for env 'staging'"):
            config.get_tfvars("staging")


# ──────────────────────────────────────────────────────────────────────────────
# _read_infra_config
# ──────────────────────────────────────────────────────────────────────────────


class TestReadInfraConfig:
    def test_reads_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "infra.yaml").write_text(yaml.dump(MINIMAL_INFRA_YAML))
        result = _read_infra_config(tmp_path)
        assert result["envs"]["dev"]["hosted_on"] == "GCP"
        assert result["backend_buckets"]["prod"]["bucket_name"] == "my-prod-bucket"

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="infra.yaml not found"):
            _read_infra_config(tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
# load_infra_config
# ──────────────────────────────────────────────────────────────────────────────


class TestLoadInfraConfig:
    def test_loads_minimal_config(self, project_root: Path) -> None:
        config = load_infra_config(project_root)
        assert len(config.envs) == 2
        assert len(config.backend_buckets) == 2
        assert config.tfvars == []

    def test_env_fields_populated(self, project_root: Path) -> None:
        config = load_infra_config(project_root)
        dev = config.get_env("dev")
        assert dev.hosted_on == "GCP"
        assert dev.gcp_project_id == "my-gcp-project"
        assert dev.aws_profile is None
        assert dev.infra_dir == "infra/dev"

    def test_backend_bucket_fields_populated(self, project_root: Path) -> None:
        config = load_infra_config(project_root)
        prod = config.get_backend_bucket("prod")
        assert prod.bucket_name == "my-prod-bucket"
        assert prod.region == "us-east-1"

    def test_bucket_without_region_defaults_to_none(self, project_root: Path) -> None:
        config = load_infra_config(project_root)
        assert config.get_backend_bucket("dev").region is None

    def test_project_root_set_correctly(self, project_root: Path) -> None:
        config = load_infra_config(project_root)
        assert config.project_root == project_root

    def test_raises_when_envs_section_missing(self, tmp_path: Path) -> None:
        (tmp_path / "infra.yaml").write_text(yaml.dump({"backend_buckets": {}}))
        with pytest.raises(KeyError, match="'envs' key not found"):
            load_infra_config(tmp_path)

    def test_raises_when_backend_buckets_section_missing(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "infra.yaml").write_text(yaml.dump({"envs": {}}))
        with pytest.raises(KeyError, match="'backend_buckets' key not found"):
            load_infra_config(tmp_path)

    def test_raises_when_env_missing_hosted_on(self, tmp_path: Path) -> None:
        data = {
            "envs": {"dev": {"infra_dir": "infra/dev"}},
            "backend_buckets": {},
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        with pytest.raises(KeyError, match="Missing 'hosted_on'"):
            load_infra_config(tmp_path)

    def test_raises_when_env_missing_infra_dir(self, tmp_path: Path) -> None:
        data = {
            "envs": {"dev": {"hosted_on": "GCP"}},
            "backend_buckets": {},
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        with pytest.raises(KeyError, match="Missing 'infra_dir'"):
            load_infra_config(tmp_path)

    def test_raises_when_bucket_missing_hosted_on(self, tmp_path: Path) -> None:
        data = {
            "envs": {"dev": {"hosted_on": "GCP", "infra_dir": "infra/dev"}},
            "backend_buckets": {"dev": {"bucket_name": "my-bucket"}},
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        with pytest.raises(KeyError, match="Missing 'hosted_on'"):
            load_infra_config(tmp_path)

    def test_raises_when_bucket_missing_bucket_name(self, tmp_path: Path) -> None:
        data = {
            "envs": {"dev": {"hosted_on": "GCP", "infra_dir": "infra/dev"}},
            "backend_buckets": {"dev": {"hosted_on": "GCP"}},
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        with pytest.raises(KeyError, match="Missing 'bucket_name'"):
            load_infra_config(tmp_path)

    def test_raises_when_tfvars_keys_mismatch_envs(self, tmp_path: Path) -> None:
        data = {
            "envs": {
                "dev": {"hosted_on": "GCP", "infra_dir": "infra/dev"},
            },
            "backend_buckets": {
                "dev": {"hosted_on": "GCP", "bucket_name": "dev-bucket"},
            },
            "tfvars": {
                "prod": {"key": "value"},  # 'prod' not in envs
            },
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        with pytest.raises(KeyError, match="tfvars keys"):
            load_infra_config(tmp_path)

    def test_loads_tfvars_when_valid(self, tmp_path: Path) -> None:
        infra_dev = tmp_path / "infra" / "dev"
        infra_dev.mkdir(parents=True)
        (infra_dev / "variables.tf").write_text('variable "region" {}\n')
        data = {
            "envs": {
                "dev": {
                    "hosted_on": "GCP",
                    "gcp_project_id": "proj",
                    "infra_dir": "infra/dev",
                },
            },
            "backend_buckets": {
                "dev": {"hosted_on": "GCP", "bucket_name": "dev-bucket"},
            },
            "tfvars": {
                "dev": {"region": "us-central1"},
            },
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        config = load_infra_config(tmp_path)
        assert len(config.tfvars) == 1
        assert config.tfvars[0].variables == {"region": "us-central1"}

    def test_tfvars_file_written_on_load(self, tmp_path: Path) -> None:
        infra_dev = tmp_path / "infra" / "dev"
        infra_dev.mkdir(parents=True)
        (infra_dev / "variables.tf").write_text('variable "region" {}\n')
        data = {
            "envs": {
                "dev": {
                    "hosted_on": "GCP",
                    "gcp_project_id": "proj",
                    "infra_dir": "infra/dev",
                },
            },
            "backend_buckets": {
                "dev": {"hosted_on": "GCP", "bucket_name": "dev-bucket"},
            },
            "tfvars": {
                "dev": {"region": "us-central1"},
            },
        }
        (tmp_path / "infra.yaml").write_text(yaml.dump(data))
        load_infra_config(tmp_path)
        tfvars_file = infra_dev / "dev.tfvars"
        assert tfvars_file.exists()
        assert 'region = "us-central1"' in tfvars_file.read_text()


# ──────────────────────────────────────────────────────────────────────────────
# _parse_variables_tf
# ──────────────────────────────────────────────────────────────────────────────


class TestParseVariablesTf:
    def test_returns_all_variable_names(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text(VARIABLES_TF_CONTENT)
        all_vars, _ = _parse_variables_tf(tmp_path)
        assert all_vars == {"region", "project_id", "instance_count"}

    def test_identifies_defaulted_variables(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text(VARIABLES_TF_CONTENT)
        _, defaulted = _parse_variables_tf(tmp_path)
        assert defaulted == {"project_id"}

    def test_required_vars_are_all_minus_defaulted(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text(VARIABLES_TF_CONTENT)
        all_vars, defaulted = _parse_variables_tf(tmp_path)
        assert all_vars - defaulted == {"region", "instance_count"}

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="variables.tf not found"):
            _parse_variables_tf(tmp_path)

    def test_empty_variables_tf(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text("")
        all_vars, defaulted = _parse_variables_tf(tmp_path)
        assert all_vars == set()
        assert defaulted == set()

    def test_variable_without_default_not_in_defaulted(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text('variable "no_default" {}\n')
        all_vars, defaulted = _parse_variables_tf(tmp_path)
        assert "no_default" in all_vars
        assert "no_default" not in defaulted


# ──────────────────────────────────────────────────────────────────────────────
# _validate_tfvars_against_variables
# ──────────────────────────────────────────────────────────────────────────────


class TestValidateTfvarsAgainstVariables:
    def test_valid_tfvars_passes(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text(
            'variable "region" {}\nvariable "project_id" { default = "x" }\n'
        )
        tv = TfVars(env="dev", variables={"region": "us-central1"})
        _validate_tfvars_against_variables(tmp_path, tv)  # should not raise

    def test_all_required_vars_provided_passes(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text(
            'variable "a" {}\nvariable "b" {}\n'
        )
        tv = TfVars(env="dev", variables={"a": "1", "b": "2"})
        _validate_tfvars_against_variables(tmp_path, tv)

    def test_raises_for_missing_required_var(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text('variable "region" {}\n')
        tv = TfVars(env="dev", variables={})
        with pytest.raises(ValueError, match="missing required variables"):
            _validate_tfvars_against_variables(tmp_path, tv)

    def test_raises_for_extra_var(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text('variable "region" {}\n')
        tv = TfVars(env="dev", variables={"region": "us-central1", "extra": "value"})
        with pytest.raises(ValueError, match="extra keys not in variables.tf"):
            _validate_tfvars_against_variables(tmp_path, tv)

    def test_raises_for_both_missing_and_extra(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text('variable "region" {}\n')
        tv = TfVars(env="dev", variables={"extra": "value"})
        with pytest.raises(ValueError):
            _validate_tfvars_against_variables(tmp_path, tv)

    def test_error_includes_env_name(self, tmp_path: Path) -> None:
        (tmp_path / "variables.tf").write_text('variable "region" {}\n')
        tv = TfVars(env="staging", variables={})
        with pytest.raises(ValueError, match="staging"):
            _validate_tfvars_against_variables(tmp_path, tv)


# ──────────────────────────────────────────────────────────────────────────────
# _format_tfvars_value
# ──────────────────────────────────────────────────────────────────────────────


class TestFormatTfvarsValue:
    def test_string_value(self) -> None:
        assert _format_tfvars_value("us-central1") == '"us-central1"'

    def test_integer_value(self) -> None:
        assert _format_tfvars_value(42) == '"42"'

    def test_list_value(self) -> None:
        result = _format_tfvars_value(["a", "b"])
        assert result == '[\n  "a",\n  "b",\n]'

    def test_single_item_list(self) -> None:
        result = _format_tfvars_value(["only"])
        assert result == '[\n  "only",\n]'

    def test_dict_value(self) -> None:
        result = _format_tfvars_value({"key": "value"})
        assert result == '{\n  "key" = "value"\n}'

    def test_boolean_value(self) -> None:
        assert _format_tfvars_value(True) == '"True"'


# ──────────────────────────────────────────────────────────────────────────────
# _generate_tfvars_files
# ──────────────────────────────────────────────────────────────────────────────


class TestGenerateTfvarsFiles:
    def test_generates_tfvars_file(self, tmp_path: Path) -> None:
        tv = TfVars(env="dev", variables={"region": "us-central1"})
        _generate_tfvars_files(tmp_path, tv)
        assert (tmp_path / "dev.tfvars").exists()

    def test_file_contains_key_value_pairs(self, tmp_path: Path) -> None:
        tv = TfVars(env="dev", variables={"region": "us-central1", "project": "my-proj"})
        _generate_tfvars_files(tmp_path, tv)
        content = (tmp_path / "dev.tfvars").read_text()
        assert 'region = "us-central1"' in content
        assert 'project = "my-proj"' in content

    def test_file_uses_lowercase_env_name(self, tmp_path: Path) -> None:
        tv = TfVars(env="PROD", variables={"key": "value"})
        _generate_tfvars_files(tmp_path, tv)
        assert (tmp_path / "prod.tfvars").exists()

    def test_raises_when_infra_dir_missing(self, tmp_path: Path) -> None:
        tv = TfVars(env="dev", variables={"region": "us-central1"})
        missing = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError, match="infra directory not found"):
            _generate_tfvars_files(missing, tv)

    def test_file_ends_with_newline(self, tmp_path: Path) -> None:
        tv = TfVars(env="dev", variables={"key": "val"})
        _generate_tfvars_files(tmp_path, tv)
        content = (tmp_path / "dev.tfvars").read_text()
        assert content.endswith("\n")
