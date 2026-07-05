"""Tests for infra tasks module."""
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from invoke.context import Context

from invoke_tasks.infra.infra_config import BackendBucket, EnvConfig, InfraConfig
from invoke_tasks.infra.tasks import build_infra_collection


def make_ctx() -> MagicMock:
    ctx = MagicMock(spec=Context)
    ctx.run.return_value = MagicMock(exited=0, stdout="")
    return ctx


def make_config(tmp_path: Path, hosted_on: str = "GCP") -> InfraConfig:
    aws_profile = "my-aws-profile" if hosted_on == "AWS" else None
    gcp_project_id = "my-gcp-project" if hosted_on == "GCP" else None
    return InfraConfig(
        envs=[
            EnvConfig(
                env="PROD",
                hosted_on=hosted_on,
                aws_profile=aws_profile,
                gcp_project_id=gcp_project_id,
                infra_dir="infra",
            )
        ],
        backend_buckets=[
            BackendBucket(
                env="PROD",
                hosted_on=hosted_on,
                bucket_name="my-state-bucket",
                region="us-east-1" if hosted_on == "AWS" else None,
            )
        ],
        tfvars=[],
        project_root=tmp_path,
    )


def run_cmds(ctx: MagicMock) -> list[str]:
    return [call.args[0] for call in ctx.run.call_args_list]


def get_task(collection, name):
    return collection.tasks[name]


# ─────────────────────────────────────────────────────────────
# get_backend_bucket_name
# ─────────────────────────────────────────────────────────────


class TestGetBackendBucketName:
    def test_prints_bucket_name(self, tmp_path: Path, capsys) -> None:
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "get-backend-bucket-name")(make_ctx(), env="PROD")
        assert "my-state-bucket" in capsys.readouterr().out

    def test_prints_backend_bucket_label(self, tmp_path: Path, capsys) -> None:
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "get-backend-bucket-name")(make_ctx(), env="PROD")
        assert "Backend Bucket" in capsys.readouterr().out


# ─────────────────────────────────────────────────────────────
# set_cloud_provider
# ─────────────────────────────────────────────────────────────


class TestSetCloudProvider:
    def test_calls_configure_cloud_provider(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("invoke_tasks.infra.tasks.configure_cloud_provider") as mock_configure:
            get_task(collection, "set-cloud-provider")(ctx, env="PROD")
        mock_configure.assert_called_once()

    def test_passes_correct_env_config(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("invoke_tasks.infra.tasks.configure_cloud_provider") as mock_configure:
            get_task(collection, "set-cloud-provider")(ctx, env="PROD")
        _, env_config_arg = mock_configure.call_args.args
        assert env_config_arg.env.upper() == "PROD"


# ─────────────────────────────────────────────────────────────
# create_backend_bucket
# ─────────────────────────────────────────────────────────────


class TestCreateBackendBucket:
    def test_calls_create_backend_bucket(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("invoke_tasks.infra.tasks._create_backend_bucket") as mock_create:
            get_task(collection, "create-backend-bucket")(ctx, env="PROD")
        mock_create.assert_called_once()

    def test_passes_env_config_and_bucket(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("invoke_tasks.infra.tasks._create_backend_bucket") as mock_create:
            get_task(collection, "create-backend-bucket")(ctx, env="PROD")
        _, env_config_arg, bucket_arg = mock_create.call_args.args
        assert env_config_arg.env.upper() == "PROD"
        assert bucket_arg.bucket_name == "my-state-bucket"


# ─────────────────────────────────────────────────────────────
# init
# ─────────────────────────────────────────────────────────────


class TestInit:
    def test_includes_terraform_init_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "init")(ctx, env="PROD")
        assert any("terraform init" in cmd for cmd in run_cmds(ctx))

    def test_includes_bucket_name_in_backend_config(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "init")(ctx, env="PROD")
        assert any("my-state-bucket" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "init")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True

    def test_gcp_includes_prefix_backend_config(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path, hosted_on="GCP")
        collection = build_infra_collection(config)
        get_task(collection, "init")(ctx, env="PROD")
        assert any("prefix=terraform/state" in cmd for cmd in run_cmds(ctx))

    def test_aws_includes_key_and_region_backend_config(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path, hosted_on="AWS")
        collection = build_infra_collection(config)
        get_task(collection, "init")(ctx, env="PROD")
        cmds = run_cmds(ctx)
        assert any("key=terraform/state" in cmd for cmd in cmds)
        assert any("region=us-east-1" in cmd for cmd in cmds)


# ─────────────────────────────────────────────────────────────
# plan
# ─────────────────────────────────────────────────────────────


class TestPlan:
    def test_includes_terraform_plan_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "plan")(ctx, env="PROD")
        assert any("terraform plan" in cmd for cmd in run_cmds(ctx))

    def test_includes_var_file(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "plan")(ctx, env="PROD")
        assert any("--var-file" in cmd for cmd in run_cmds(ctx))

    def test_var_file_uses_lowercase_env_name(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "plan")(ctx, env="PROD")
        assert any("prod.tfvars" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "plan")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# apply
# ─────────────────────────────────────────────────────────────


class TestApply:
    def test_includes_terraform_apply_in_subprocess_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "apply")(ctx, env="PROD")
        cmd = mock_sub.call_args.args[0]
        assert "terraform apply" in cmd

    def test_without_auto_approve_has_no_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "apply")(ctx, env="PROD", auto_approve=False)
        cmd = mock_sub.call_args.args[0]
        assert "-auto-approve" not in cmd

    def test_with_auto_approve_includes_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "apply")(ctx, env="PROD", auto_approve=True)
        cmd = mock_sub.call_args.args[0]
        assert "-auto-approve" in cmd

    def test_includes_var_file_with_lowercase_env(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "apply")(ctx, env="PROD")
        cmd = mock_sub.call_args.args[0]
        assert "prod.tfvars" in cmd

    def test_runs_init_via_context_before_apply(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run"):
            get_task(collection, "apply")(ctx, env="PROD")
        assert any("terraform init" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# destroy
# ─────────────────────────────────────────────────────────────


class TestDestroy:
    def test_includes_terraform_destroy_in_subprocess_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "destroy")(ctx, env="PROD")
        cmd = mock_sub.call_args.args[0]
        assert "terraform destroy" in cmd

    def test_without_auto_approve_has_no_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "destroy")(ctx, env="PROD", auto_approve=False)
        cmd = mock_sub.call_args.args[0]
        assert "-auto-approve" not in cmd

    def test_with_auto_approve_includes_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "destroy")(ctx, env="PROD", auto_approve=True)
        cmd = mock_sub.call_args.args[0]
        assert "-auto-approve" in cmd

    def test_includes_var_file_with_lowercase_env(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run") as mock_sub:
            get_task(collection, "destroy")(ctx, env="PROD")
        cmd = mock_sub.call_args.args[0]
        assert "prod.tfvars" in cmd

    def test_runs_init_via_context_before_destroy(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        with patch("subprocess.run"):
            get_task(collection, "destroy")(ctx, env="PROD")
        assert any("terraform init" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# output
# ─────────────────────────────────────────────────────────────


class TestOutput:
    def test_includes_terraform_output_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "output")(ctx, env="PROD")
        assert any("terraform output" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "output")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# raw_output
# ─────────────────────────────────────────────────────────────


class TestRawOutput:
    def test_includes_terraform_output_raw_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "raw-output")(ctx, env="PROD", output="website_url")
        assert any("terraform output -raw" in cmd for cmd in run_cmds(ctx))

    def test_includes_output_name_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "raw-output")(ctx, env="PROD", output="website_url")
        assert any("website_url" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "raw-output")(ctx, env="PROD", output="website_url")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# state_remove
# ─────────────────────────────────────────────────────────────


class TestStateRemove:
    def test_includes_terraform_state_rm_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "state-remove")(ctx, env="PROD", resource="aws_s3_bucket.website")
        assert any("terraform state rm" in cmd for cmd in run_cmds(ctx))

    def test_includes_resource_name_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "state-remove")(ctx, env="PROD", resource="aws_s3_bucket.website")
        assert any("aws_s3_bucket.website" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "state-remove")(ctx, env="PROD", resource="aws_s3_bucket.website")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# state_list
# ─────────────────────────────────────────────────────────────


class TestStateList:
    def test_includes_terraform_state_list_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "state-list")(ctx, env="PROD")
        assert any("terraform state list" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "state-list")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# show
# ─────────────────────────────────────────────────────────────


class TestShow:
    def test_includes_terraform_show_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD")
        assert any("terraform show" in cmd for cmd in run_cmds(ctx))

    def test_without_json_has_no_json_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD", json=False)
        assert "-json" not in run_cmds(ctx)[-1]

    def test_with_json_includes_json_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD", json=True)
        assert "-json" in run_cmds(ctx)[-1]

    def test_without_json_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD", json=False)
        assert ctx.run.call_args_list[-1].kwargs.get("pty") is True

    def test_with_json_disables_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD", json=True)
        assert ctx.run.call_args_list[-1].kwargs.get("pty") is False

    def test_json_defaults_to_false(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "show")(ctx, env="PROD")
        assert "-json" not in run_cmds(ctx)[-1]


# ─────────────────────────────────────────────────────────────
# fmt
# ─────────────────────────────────────────────────────────────


class TestFmt:
    def test_includes_terraform_fmt_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "fmt")(ctx)
        assert any("terraform fmt" in cmd for cmd in run_cmds(ctx))

    def test_uses_recursive_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = make_config(tmp_path)
        collection = build_infra_collection(config)
        get_task(collection, "fmt")(ctx)
        assert any("--recursive" in cmd for cmd in run_cmds(ctx))

    def test_runs_once_per_unique_infra_dir(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = InfraConfig(
            envs=[
                EnvConfig("DEV", "GCP", None, "proj", "infra"),
                EnvConfig("PROD", "GCP", None, "proj", "infra"),
            ],
            backend_buckets=[
                BackendBucket("DEV", "GCP", "dev-bucket", None),
                BackendBucket("PROD", "GCP", "prod-bucket", None),
            ],
            tfvars=[],
            project_root=tmp_path,
        )
        collection = build_infra_collection(config)
        get_task(collection, "fmt")(ctx)
        fmt_cmds = [cmd for cmd in run_cmds(ctx) if "terraform fmt" in cmd]
        assert len(fmt_cmds) == 1

    def test_runs_once_per_distinct_infra_dir(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        config = InfraConfig(
            envs=[
                EnvConfig("DEV", "GCP", None, "proj", "infra/dev"),
                EnvConfig("PROD", "GCP", None, "proj", "infra/prod"),
            ],
            backend_buckets=[
                BackendBucket("DEV", "GCP", "dev-bucket", None),
                BackendBucket("PROD", "GCP", "prod-bucket", None),
            ],
            tfvars=[],
            project_root=tmp_path,
        )
        collection = build_infra_collection(config)
        get_task(collection, "fmt")(ctx)
        fmt_cmds = [cmd for cmd in run_cmds(ctx) if "terraform fmt" in cmd]
        assert len(fmt_cmds) == 2


# ─────────────────────────────────────────────────────────────
# validate
# ─────────────────────────────────────────────────────────────


class TestValidate:
    def test_includes_terraform_validate_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "validate")(ctx, env="PROD")
        assert any("terraform validate" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "validate")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────


class TestImport:
    def test_includes_terraform_import_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "import")(ctx, env="PROD", address="aws_s3_bucket.site", resource_id="my-bucket")
        assert any("terraform import" in cmd for cmd in run_cmds(ctx))

    def test_includes_address_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "import")(ctx, env="PROD", address="aws_s3_bucket.site", resource_id="my-bucket")
        assert any("aws_s3_bucket.site" in cmd for cmd in run_cmds(ctx))

    def test_includes_resource_id_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "import")(ctx, env="PROD", address="aws_s3_bucket.site", resource_id="my-bucket")
        assert any("my-bucket" in cmd for cmd in run_cmds(ctx))

    def test_includes_var_file(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "import")(ctx, env="PROD", address="aws_s3_bucket.site", resource_id="my-bucket")
        assert any("prod.tfvars" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# state_show
# ─────────────────────────────────────────────────────────────


class TestStateShow:
    def test_includes_terraform_state_show_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-show")(ctx, env="PROD", resource="aws_s3_bucket.site")
        assert any("terraform state show" in cmd for cmd in run_cmds(ctx))

    def test_includes_resource_name(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-show")(ctx, env="PROD", resource="aws_s3_bucket.site")
        assert any("aws_s3_bucket.site" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-show")(ctx, env="PROD", resource="aws_s3_bucket.site")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# state_mv
# ─────────────────────────────────────────────────────────────


class TestStateMv:
    def test_includes_terraform_state_mv_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-mv")(ctx, env="PROD", source="aws_s3_bucket.old", destination="aws_s3_bucket.new")
        assert any("terraform state mv" in cmd for cmd in run_cmds(ctx))

    def test_includes_source_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-mv")(ctx, env="PROD", source="aws_s3_bucket.old", destination="aws_s3_bucket.new")
        assert any("aws_s3_bucket.old" in cmd for cmd in run_cmds(ctx))

    def test_includes_destination_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "state-mv")(ctx, env="PROD", source="aws_s3_bucket.old", destination="aws_s3_bucket.new")
        assert any("aws_s3_bucket.new" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# workspace_list
# ─────────────────────────────────────────────────────────────


class TestWorkspaceList:
    def test_includes_terraform_workspace_list_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-list")(ctx, env="PROD")
        assert any("terraform workspace list" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# workspace_new
# ─────────────────────────────────────────────────────────────


class TestWorkspaceNew:
    def test_includes_terraform_workspace_new_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-new")(ctx, env="PROD", name="staging")
        assert any("terraform workspace new" in cmd for cmd in run_cmds(ctx))

    def test_includes_workspace_name(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-new")(ctx, env="PROD", name="staging")
        assert any("staging" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# workspace_select
# ─────────────────────────────────────────────────────────────


class TestWorkspaceSelect:
    def test_includes_terraform_workspace_select_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-select")(ctx, env="PROD", name="staging")
        assert any("terraform workspace select" in cmd for cmd in run_cmds(ctx))

    def test_includes_workspace_name(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-select")(ctx, env="PROD", name="staging")
        assert any("staging" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# workspace_delete
# ─────────────────────────────────────────────────────────────


class TestWorkspaceDelete:
    def test_includes_terraform_workspace_delete_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-delete")(ctx, env="PROD", name="staging")
        assert any("terraform workspace delete" in cmd for cmd in run_cmds(ctx))

    def test_includes_workspace_name(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-delete")(ctx, env="PROD", name="staging")
        assert any("staging" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# workspace_show
# ─────────────────────────────────────────────────────────────


class TestWorkspaceShow:
    def test_includes_terraform_workspace_show_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "workspace-show")(ctx, env="PROD")
        assert any("terraform workspace show" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# providers
# ─────────────────────────────────────────────────────────────


class TestProviders:
    def test_includes_terraform_providers_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "providers")(ctx, env="PROD")
        assert any("terraform providers" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "providers")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# graph
# ─────────────────────────────────────────────────────────────


class TestGraph:
    def test_includes_terraform_graph_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "graph")(ctx, env="PROD")
        assert any("terraform graph" in cmd for cmd in run_cmds(ctx))

    def test_disables_pty_for_piping(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "graph")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is False


# ─────────────────────────────────────────────────────────────
# console
# ─────────────────────────────────────────────────────────────


class TestConsole:
    def test_includes_terraform_console_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "console")(ctx, env="PROD")
        assert any("terraform console" in cmd for cmd in run_cmds(ctx))

    def test_includes_var_file(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "console")(ctx, env="PROD")
        assert any("prod.tfvars" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "console")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# force_unlock
# ─────────────────────────────────────────────────────────────


class TestForceUnlock:
    def test_includes_terraform_force_unlock_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "force-unlock")(ctx, env="PROD", lock_id="abc-123")
        assert any("terraform force-unlock" in cmd for cmd in run_cmds(ctx))

    def test_includes_lock_id_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "force-unlock")(ctx, env="PROD", lock_id="abc-123")
        assert any("abc-123" in cmd for cmd in run_cmds(ctx))

    def test_includes_force_flag(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "force-unlock")(ctx, env="PROD", lock_id="abc-123")
        assert any("-force" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# get
# ─────────────────────────────────────────────────────────────


class TestGet:
    def test_includes_terraform_get_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "get")(ctx, env="PROD")
        assert any("terraform get" in cmd for cmd in run_cmds(ctx))

    def test_does_not_run_backend_init(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "get")(ctx, env="PROD")
        assert not any("terraform init" in cmd for cmd in run_cmds(ctx))


# ─────────────────────────────────────────────────────────────
# refresh
# ─────────────────────────────────────────────────────────────


class TestRefresh:
    def test_includes_terraform_refresh_in_command(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "refresh")(ctx, env="PROD")
        assert any("terraform refresh" in cmd for cmd in run_cmds(ctx))

    def test_includes_var_file(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "refresh")(ctx, env="PROD")
        assert any("prod.tfvars" in cmd for cmd in run_cmds(ctx))

    def test_uses_pty(self, tmp_path: Path) -> None:
        ctx = make_ctx()
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "refresh")(ctx, env="PROD")
        assert ctx.run.call_args.kwargs.get("pty") is True


# ─────────────────────────────────────────────────────────────
# validate_yaml_config
# ─────────────────────────────────────────────────────────────


def _write_infra_yaml(tmp_path: Path, data: dict) -> None:
    (tmp_path / "infra.yaml").write_text(yaml.dump(data))


VALID_INFRA_DATA = {
    "envs": {
        "PROD": {"hosted_on": "GCP", "gcp_project_id": "proj", "infra_dir": "infra"},
    },
    "backend_buckets": {
        "PROD": {"hosted_on": "GCP", "bucket_name": "my-state-bucket"},
    },
}


class TestValidateYamlConfig:
    def test_prints_valid_on_success(self, tmp_path: Path, capsys) -> None:
        _write_infra_yaml(tmp_path, VALID_INFRA_DATA)
        collection = build_infra_collection(make_config(tmp_path))
        get_task(collection, "validate-yaml-config")(make_ctx())
        assert "valid" in capsys.readouterr().out.lower()

    def test_exits_nonzero_when_env_missing_infra_dir(self, tmp_path: Path) -> None:
        _write_infra_yaml(tmp_path, {
            "envs": {"PROD": {"hosted_on": "GCP"}},
            "backend_buckets": {"PROD": {"hosted_on": "GCP", "bucket_name": "my-state-bucket"}},
        })
        collection = build_infra_collection(make_config(tmp_path))
        with pytest.raises(SystemExit):
            get_task(collection, "validate-yaml-config")(make_ctx())

    def test_prints_error_message_on_failure(self, tmp_path: Path, capsys) -> None:
        _write_infra_yaml(tmp_path, {
            "envs": {"PROD": {"hosted_on": "GCP"}},
            "backend_buckets": {"PROD": {"hosted_on": "GCP", "bucket_name": "my-state-bucket"}},
        })
        collection = build_infra_collection(make_config(tmp_path))
        with pytest.raises(SystemExit):
            get_task(collection, "validate-yaml-config")(make_ctx())
        assert "validation failed" in capsys.readouterr().out.lower()

    def test_exits_nonzero_when_yaml_file_missing(self, tmp_path: Path) -> None:
        collection = build_infra_collection(make_config(tmp_path))
        with pytest.raises(SystemExit):
            get_task(collection, "validate-yaml-config")(make_ctx())

    def test_exits_nonzero_when_tfvars_keys_mismatch(self, tmp_path: Path) -> None:
        _write_infra_yaml(tmp_path, {
            "envs": {"PROD": {"hosted_on": "GCP", "infra_dir": "infra"}},
            "backend_buckets": {"PROD": {"hosted_on": "GCP", "bucket_name": "my-state-bucket"}},
            "tfvars": {"DEV": {"region": "us-central1"}},
        })
        collection = build_infra_collection(make_config(tmp_path))
        with pytest.raises(SystemExit):
            get_task(collection, "validate-yaml-config")(make_ctx())
