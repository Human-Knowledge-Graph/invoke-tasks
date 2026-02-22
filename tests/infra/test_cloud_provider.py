"""Tests for cloud_provider module."""
from unittest.mock import MagicMock

import pytest

from invoke_tasks.infra.cloud_provider import configure_cloud_provider
from invoke_tasks.infra.infra_config import EnvConfig


def _make_env(
    env: str = "dev",
    hosted_on: str = "GCP",
    aws_profile: str | None = None,
    gcp_project_id: str | None = "my-project",
    infra_dir: str = "infra/dev",
) -> EnvConfig:
    return EnvConfig(
        env=env,
        hosted_on=hosted_on,
        aws_profile=aws_profile,
        gcp_project_id=gcp_project_id,
        infra_dir=infra_dir,
    )


class TestConfigureCloudProvider:
    def test_gcp_runs_gcloud_config_set(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="GCP", gcp_project_id="my-project")
        configure_cloud_provider(c, env)
        c.run.assert_called_once_with("gcloud config set project my-project")

    def test_gcp_case_insensitive(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="gcp", gcp_project_id="my-project")
        configure_cloud_provider(c, env)
        c.run.assert_called_once()

    def test_gcp_without_project_id_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="GCP", gcp_project_id=None)
        with pytest.raises(ValueError, match="no gcp_project_id configured"):
            configure_cloud_provider(c, env)

    def test_aws_calls_export_and_sts(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile="my-profile", gcp_project_id=None)
        configure_cloud_provider(c, env)
        assert c.run.call_count == 2

    def test_aws_export_command_contains_profile(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile="my-profile", gcp_project_id=None)
        configure_cloud_provider(c, env)
        commands = [call.args[0] for call in c.run.call_args_list]
        assert any("AWS_PROFILE=my-profile" in cmd for cmd in commands)

    def test_aws_sts_command_contains_profile(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile="my-profile", gcp_project_id=None)
        configure_cloud_provider(c, env)
        commands = [call.args[0] for call in c.run.call_args_list]
        assert any("aws sts get-caller-identity" in cmd for cmd in commands)

    def test_aws_without_profile_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile=None, gcp_project_id=None)
        with pytest.raises(ValueError, match="no aws_profile configured"):
            configure_cloud_provider(c, env)

    def test_aws_error_includes_env_name(self) -> None:
        c = MagicMock()
        env = _make_env(env="staging", hosted_on="AWS", aws_profile=None, gcp_project_id=None)
        with pytest.raises(ValueError, match="staging"):
            configure_cloud_provider(c, env)

    def test_unsupported_provider_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AZURE")
        with pytest.raises(NotImplementedError, match="Unsupported hosted_on: 'AZURE'"):
            configure_cloud_provider(c, env)
