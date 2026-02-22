"""Tests for backend_bucket module."""
from unittest.mock import MagicMock

import pytest

from invoke_tasks.infra.backend_bucket import (
    _create_aws_bucket,
    _create_gcp_bucket,
    create_backend_bucket,
)
from invoke_tasks.infra.infra_config import BackendBucket, EnvConfig


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


def _make_bucket(
    env: str = "dev",
    hosted_on: str = "GCP",
    bucket_name: str = "my-bucket",
    region: str | None = None,
) -> BackendBucket:
    return BackendBucket(
        env=env, hosted_on=hosted_on, bucket_name=bucket_name, region=region
    )


# ──────────────────────────────────────────────────────────────────────────────
# _create_aws_bucket
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateAwsBucket:
    def test_bucket_name_in_command(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", None)
        cmd = c.run.call_args.args[0]
        assert "--bucket my-bucket" in cmd

    def test_profile_in_command(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", None)
        cmd = c.run.call_args.args[0]
        assert "--profile my-profile" in cmd

    def test_us_east_1_has_no_location_constraint(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", "us-east-1")
        cmd = c.run.call_args.args[0]
        assert "LocationConstraint" not in cmd

    def test_no_region_has_no_location_constraint(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", None)
        cmd = c.run.call_args.args[0]
        assert "LocationConstraint" not in cmd

    def test_other_region_includes_location_constraint(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", "eu-west-1")
        cmd = c.run.call_args.args[0]
        assert "LocationConstraint=eu-west-1" in cmd

    def test_other_region_includes_region_flag(self) -> None:
        c = MagicMock()
        _create_aws_bucket(c, "my-bucket", "my-profile", "eu-west-1")
        cmd = c.run.call_args.args[0]
        assert "--region eu-west-1" in cmd


# ──────────────────────────────────────────────────────────────────────────────
# _create_gcp_bucket
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateGcpBucket:
    def test_sets_project_and_creates_bucket(self) -> None:
        c = MagicMock()
        _create_gcp_bucket(c, "my-bucket", "my-project")
        assert c.run.call_count == 2

    def test_sets_gcp_project_first(self) -> None:
        c = MagicMock()
        _create_gcp_bucket(c, "my-bucket", "my-project")
        first_cmd = c.run.call_args_list[0].args[0]
        assert "gcloud config set project my-project" in first_cmd

    def test_creates_bucket_with_gsutil(self) -> None:
        c = MagicMock()
        _create_gcp_bucket(c, "my-bucket", "my-project")
        second_cmd = c.run.call_args_list[1].args[0]
        assert "gsutil mb" in second_cmd
        assert "gs://my-bucket" in second_cmd

    def test_project_id_passed_to_gsutil(self) -> None:
        c = MagicMock()
        _create_gcp_bucket(c, "my-bucket", "my-project")
        second_cmd = c.run.call_args_list[1].args[0]
        assert "-p my-project" in second_cmd


# ──────────────────────────────────────────────────────────────────────────────
# create_backend_bucket
# ──────────────────────────────────────────────────────────────────────────────


class TestCreateBackendBucket:
    def test_gcp_invokes_gcp_bucket_creation(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="GCP", gcp_project_id="my-project")
        bucket = _make_bucket(hosted_on="GCP", bucket_name="my-bucket")
        create_backend_bucket(c, env, bucket)
        # gcloud + gsutil calls
        assert c.run.call_count == 2

    def test_gcp_passes_bucket_name(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="GCP", gcp_project_id="my-project")
        bucket = _make_bucket(hosted_on="GCP", bucket_name="my-gcp-bucket")
        create_backend_bucket(c, env, bucket)
        all_commands = " ".join(call.args[0] for call in c.run.call_args_list)
        assert "my-gcp-bucket" in all_commands

    def test_aws_invokes_s3api(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile="my-profile", gcp_project_id=None)
        bucket = _make_bucket(hosted_on="AWS", bucket_name="my-bucket", region="us-east-1")
        create_backend_bucket(c, env, bucket)
        cmd = c.run.call_args.args[0]
        assert "s3api create-bucket" in cmd

    def test_aws_passes_bucket_name(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile="my-profile", gcp_project_id=None)
        bucket = _make_bucket(hosted_on="AWS", bucket_name="my-aws-bucket")
        create_backend_bucket(c, env, bucket)
        cmd = c.run.call_args.args[0]
        assert "--bucket my-aws-bucket" in cmd

    def test_aws_without_profile_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AWS", aws_profile=None, gcp_project_id=None)
        bucket = _make_bucket(hosted_on="AWS")
        with pytest.raises(ValueError, match="no aws_profile configured"):
            create_backend_bucket(c, env, bucket)

    def test_gcp_without_project_id_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="GCP", gcp_project_id=None)
        bucket = _make_bucket(hosted_on="GCP")
        with pytest.raises(ValueError, match="no gcp_project_id configured"):
            create_backend_bucket(c, env, bucket)

    def test_unsupported_provider_raises(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="AZURE")
        bucket = _make_bucket(hosted_on="AZURE")
        with pytest.raises(NotImplementedError, match="Unsupported hosted_on"):
            create_backend_bucket(c, env, bucket)

    def test_gcp_case_insensitive(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="gcp", gcp_project_id="my-project")
        bucket = _make_bucket(hosted_on="gcp")
        create_backend_bucket(c, env, bucket)
        assert c.run.call_count == 2

    def test_aws_case_insensitive(self) -> None:
        c = MagicMock()
        env = _make_env(hosted_on="aws", aws_profile="my-profile", gcp_project_id=None)
        bucket = _make_bucket(hosted_on="aws", region="us-east-1")
        create_backend_bucket(c, env, bucket)
        cmd = c.run.call_args.args[0]
        assert "s3api create-bucket" in cmd
