import platform
import shutil

from invoke.context import Context


def install_cloud_sql_proxy(c: Context) -> None:
    """Install cloud-sql-proxy based on the operating system.

    Supports:
    - macOS: Uses Homebrew
    - Linux: Uses gcloud components or direct download
    - Windows: Uses gcloud components or chocolatey
    """
    system = platform.system()

    print(f"Detected OS: {system}")

    # Try gcloud components first (works on all platforms)
    print("Attempting to install via gcloud components...")
    try:
        c.run("gcloud components install cloud-sql-proxy", warn=True)
    except Exception as e:
        print(f"gcloud installation failed: {e}")

    # Platform-specific installation
    if system == "Darwin":  # macOS
        print("Installing via Homebrew...")
        if shutil.which("brew"):
            c.run("brew install cloud-sql-proxy")
        else:
            print("Homebrew not found. Please install Homebrew first: https://brew.sh")

    elif system == "Linux":
        print("Installing via direct download...")
        arch = platform.machine()
        if arch == "x86_64":
            download_url = "https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64"
        elif arch in ("aarch64", "arm64"):
            download_url = "https://dl.google.com/cloudsql/cloud_sql_proxy.linux.arm64"
        else:
            print(f"Unsupported architecture: {arch}")
            return

        c.run(f"curl -o cloud-sql-proxy {download_url}")
        c.run("chmod +x cloud-sql-proxy")
        c.run("sudo mv cloud-sql-proxy /usr/local/bin/")
        print("cloud-sql-proxy installed to /usr/local/bin/")

    elif system == "Windows":
        print("For Windows, cloud-sql-proxy should be installed via gcloud components.")
        print("If that failed, you can:")
        print(
            "1. Download from: https://dl.google.com/cloudsql/cloud_sql_proxy_x64.exe",
        )
        print("2. Or use chocolatey: choco install cloud-sql-proxy")

    else:
        print(f"Unsupported operating system: {system}")
