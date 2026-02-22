"""
YantraOS — Docker Sandboxed Execution Module
Model Route: Claude Opus 4.6

Manages ephemeral Alpine Linux containers for executing AI-generated scripts
in complete isolation. All containers run with --cap-drop=ALL, read-only
rootfs, seccomp defaults, and are destroyed immediately after execution.

Usage:
    from deploy.sandbox import Sandbox, SandboxResult
    sandbox = Sandbox()
    result = sandbox.execute("echo 'Hello from the sandbox'")
    print(result.stdout)
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import docker
from docker.errors import BuildError, ContainerError, DockerException, ImageNotFound

logger = logging.getLogger("yantra.sandbox")

# ─── CONSTANTS ───────────────────────────────────────────────────────────────
SANDBOX_IMAGE_NAME = "yantra-sandbox:latest"
DOCKERFILE_PATH = Path(__file__).parent / "Dockerfile.agent"
DEFAULT_TIMEOUT = 30       # seconds
MAX_OUTPUT_BYTES = 1048576  # 1MB max stdout/stderr capture
MEMORY_LIMIT = "256m"
CPU_PERIOD = 100000
CPU_QUOTA = 50000          # 50% of one CPU core


@dataclass
class SandboxResult:
    """Result of a sandboxed script execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    error: Optional[str] = None


class Sandbox:
    """
    Manages ephemeral Docker containers for isolated script execution.

    Security guarantees:
        - --cap-drop=ALL (no Linux capabilities)
        - Read-only root filesystem
        - --network=none (no network access)
        - --rm (container destroyed after execution)
        - Non-root user inside container
        - Memory and CPU limits enforced
        - Strict timeout enforcement
    """

    def __init__(self, docker_base_url: Optional[str] = None):
        """
        Initialize the sandbox manager.

        Args:
            docker_base_url: Docker daemon URL. Defaults to unix:///var/run/docker.sock
        """
        try:
            if docker_base_url:
                self.client = docker.DockerClient(base_url=docker_base_url)
            else:
                self.client = docker.from_env()
            self.client.ping()
            logger.info("Docker connection established.")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise RuntimeError(
                "Docker daemon is not running or not accessible. "
                "Ensure yantra_daemon is in the docker group."
            ) from e

        self._ensure_image()

    def _ensure_image(self) -> None:
        """Build the sandbox image if it doesn't exist."""
        try:
            self.client.images.get(SANDBOX_IMAGE_NAME)
            logger.debug(f"Sandbox image '{SANDBOX_IMAGE_NAME}' found.")
        except ImageNotFound:
            logger.info(f"Building sandbox image from {DOCKERFILE_PATH}...")
            if not DOCKERFILE_PATH.exists():
                raise FileNotFoundError(
                    f"Dockerfile not found: {DOCKERFILE_PATH}"
                )
            try:
                self.client.images.build(
                    path=str(DOCKERFILE_PATH.parent),
                    dockerfile=DOCKERFILE_PATH.name,
                    tag=SANDBOX_IMAGE_NAME,
                    rm=True,
                    forcerm=True,
                )
                logger.info(f"Sandbox image '{SANDBOX_IMAGE_NAME}' built.")
            except BuildError as e:
                logger.error(f"Failed to build sandbox image: {e}")
                raise

    def execute(
        self,
        script: str,
        timeout: int = DEFAULT_TIMEOUT,
        env: Optional[dict[str, str]] = None,
    ) -> SandboxResult:
        """
        Execute a script inside an ephemeral sandbox container.

        Args:
            script: The bash script content to execute.
            timeout: Maximum execution time in seconds.
            env: Optional environment variables to pass to the container.

        Returns:
            SandboxResult with exit_code, stdout, stderr, and timing.
        """
        start_time = time.monotonic()

        # Write script to a temp file that will be mounted into the container
        tmp_dir = tempfile.mkdtemp(prefix="yantra_sandbox_")
        script_path = os.path.join(tmp_dir, "script.sh")

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nset -euo pipefail\n")
                f.write(script)
            os.chmod(script_path, 0o755)

            # Container configuration — maximum isolation
            container = self.client.containers.run(
                image=SANDBOX_IMAGE_NAME,
                command=f"bash /workspace/script.sh",
                detach=True,
                remove=False,  # We remove manually after capturing logs
                # ─── SECURITY FLAGS ──────────────────────────────
                cap_drop=["ALL"],
                read_only=True,
                network_mode="none",
                security_opt=["no-new-privileges:true"],
                user="sandbox_user",
                # ─── RESOURCE LIMITS ─────────────────────────────
                mem_limit=MEMORY_LIMIT,
                cpu_period=CPU_PERIOD,
                cpu_quota=CPU_QUOTA,
                pids_limit=64,
                # ─── FILESYSTEM ──────────────────────────────────
                volumes={
                    tmp_dir: {"bind": "/workspace", "mode": "ro"},
                },
                tmpfs={"/tmp": "size=64m,noexec,nosuid"},
                working_dir="/workspace",
                # ─── ENVIRONMENT ─────────────────────────────────
                environment=env or {},
            )

            logger.info(f"Container {container.short_id} started.")

            # Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
                exit_code = result.get("StatusCode", -1)
                timed_out = False
            except Exception:
                logger.warning(
                    f"Container {container.short_id} timed out after {timeout}s. Killing."
                )
                try:
                    container.kill()
                except Exception:
                    pass
                exit_code = 137  # SIGKILL
                timed_out = True

            # Capture output
            try:
                stdout = container.logs(
                    stdout=True, stderr=False, tail=1000
                ).decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
            except Exception:
                stdout = ""

            try:
                stderr = container.logs(
                    stdout=False, stderr=True, tail=1000
                ).decode("utf-8", errors="replace")[:MAX_OUTPUT_BYTES]
            except Exception:
                stderr = ""

            # Cleanup container
            try:
                container.remove(force=True)
            except Exception:
                pass

            duration_ms = int((time.monotonic() - start_time) * 1000)

            sandbox_result = SandboxResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
                timed_out=timed_out,
            )

            logger.info(
                f"Sandbox execution complete: exit={exit_code}, "
                f"duration={duration_ms}ms, timed_out={timed_out}"
            )

            return sandbox_result

        except ContainerError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Container execution error: {e}")
            return SandboxResult(
                exit_code=e.exit_status or -1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                error=str(e),
            )
        except DockerException as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Docker error: {e}")
            return SandboxResult(
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=duration_ms,
                error=f"Docker error: {e}",
            )
        finally:
            # Cleanup temp directory
            try:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def cleanup(self) -> None:
        """Remove the sandbox image and prune dangling containers."""
        try:
            self.client.images.remove(SANDBOX_IMAGE_NAME, force=True)
            logger.info(f"Removed sandbox image: {SANDBOX_IMAGE_NAME}")
        except ImageNotFound:
            pass
        except DockerException as e:
            logger.warning(f"Failed to remove sandbox image: {e}")

        # Prune any leftover yantra containers
        try:
            self.client.containers.prune(
                filters={"label": "yantra-sandbox"}
            )
        except DockerException:
            pass

    def health_check(self) -> dict:
        """
        Check sandbox system health.

        Returns:
            Dict with docker_running, image_exists, and disk_usage keys.
        """
        status = {
            "docker_running": False,
            "image_exists": False,
            "disk_usage": None,
        }

        try:
            self.client.ping()
            status["docker_running"] = True
        except DockerException:
            return status

        try:
            self.client.images.get(SANDBOX_IMAGE_NAME)
            status["image_exists"] = True
        except ImageNotFound:
            pass

        try:
            df = self.client.df()
            status["disk_usage"] = {
                "images": len(df.get("Images", [])),
                "containers": len(df.get("Containers", [])),
            }
        except DockerException:
            pass

        return status
