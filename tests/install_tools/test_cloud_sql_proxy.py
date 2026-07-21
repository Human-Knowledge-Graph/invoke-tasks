"""Tests for install_tools.cloud_sql_proxy module."""
from unittest.mock import MagicMock, patch

import pytest
from invoke.context import Context

from invoke_tasks.install_tools import install_cloud_sql_proxy


def make_ctx() -> MagicMock:
    ctx = MagicMock(spec=Context)
    ctx.run.return_value = MagicMock(exited=0)
    return ctx


class TestInstallCloudSqlProxy:
    def test_darwin_with_brew(self) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Darwin"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.shutil.which", return_value="/usr/local/bin/brew"),
        ):
            install_cloud_sql_proxy(ctx)
        cmds = [call.args[0] for call in ctx.run.call_args_list]
        assert any("gcloud components install" in c for c in cmds)
        assert any("brew install cloud-sql-proxy" in c for c in cmds)

    def test_darwin_without_brew(self, capsys) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Darwin"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.shutil.which", return_value=None),
        ):
            install_cloud_sql_proxy(ctx)
        assert "Homebrew not found" in capsys.readouterr().out

    def test_linux_x86_64(self) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Linux"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.machine", return_value="x86_64"),
        ):
            install_cloud_sql_proxy(ctx)
        cmds = [call.args[0] for call in ctx.run.call_args_list]
        assert any("amd64" in c for c in cmds)

    def test_linux_arm64(self) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Linux"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.machine", return_value="arm64"),
        ):
            install_cloud_sql_proxy(ctx)
        cmds = [call.args[0] for call in ctx.run.call_args_list]
        assert any("arm64" in c for c in cmds)

    def test_linux_aarch64(self) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Linux"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.machine", return_value="aarch64"),
        ):
            install_cloud_sql_proxy(ctx)
        cmds = [call.args[0] for call in ctx.run.call_args_list]
        assert any("arm64" in c for c in cmds)

    def test_linux_unsupported_arch(self, capsys) -> None:
        ctx = make_ctx()
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Linux"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.machine", return_value="mips"),
        ):
            install_cloud_sql_proxy(ctx)
        assert "Unsupported architecture" in capsys.readouterr().out

    def test_windows(self, capsys) -> None:
        ctx = make_ctx()
        with patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Windows"):
            install_cloud_sql_proxy(ctx)
        out = capsys.readouterr().out
        assert "Windows" in out

    def test_unsupported_os(self, capsys) -> None:
        ctx = make_ctx()
        with patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="FreeBSD"):
            install_cloud_sql_proxy(ctx)
        assert "Unsupported operating system" in capsys.readouterr().out

    def test_gcloud_exception_is_caught(self, capsys) -> None:
        ctx = make_ctx()
        ctx.run.side_effect = [Exception("gcloud not found"), MagicMock(exited=0)]
        with (
            patch("invoke_tasks.install_tools.cloud_sql_proxy.platform.system", return_value="Darwin"),
            patch("invoke_tasks.install_tools.cloud_sql_proxy.shutil.which", return_value="/usr/local/bin/brew"),
        ):
            install_cloud_sql_proxy(ctx)
        assert "gcloud installation failed" in capsys.readouterr().out
