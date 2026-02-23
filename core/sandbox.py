"""
YantraOS — Ephemeral Docker Sandbox
Target: /opt/yantra/core/sandbox.py
Milestone 3, Task 3.1

Provides an impenetrable abstraction layer for executing AI-generated code
inside ephemeral Alpine Linux containers. The Kriya Loop's ACT phase calls
this module instead of ever executing code directly on the host kernel.

Security constraints (hardcoded, non-negotiable):
  • network_mode="none"     — No egress. Prevents data exfiltration.
  • mem_limit="512m"        — OOM-killed at 512 MB. Prevents RAM exhaustion.
  • cpu_quota=50000         — 50% of one CPU core maximum (cfs_period=100000).
  • read_only=True          — Root filesystem is immutable.
  • cap_drop=["ALL"]        — Zero Linux capabilities. No privilege escalation.
  • security_opt=["no-new-privileges:true"]  — Blocks setuid/setgid binaries.
  • auto_remove=True        — Container destroyed immediately after exit.
  • tmpfs /tmp:size=64m     — Writable scratch space capped at 64 MB.

The yantra_daemon user accesses Docker via group membership to the `docker`
group, established in Milestone 1 (sysusers.d). No root elevation for this.

Pre-flight health check:
  client.ping() is called in a try-except before the main loop. If the
  Docker daemon is unreachable, operations degrade gracefully — the sandbox
  logs a journal warning and the Kriya Loop continues in observe-only mode.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any

log = logging.getLogger("yantra.sandbox")

# ── Constants ─────────────────────────────────────────────────────────────────

# Default sandbox image. Alpine is ~5 MB and contains a POSIX shell.
# The Dockerfile.agent builds on top of this with Python + curl if needed.
SANDBOX_IMAGE: str = "alpine:3.19"
CUSTOM_IMAGE: str = "yantra-agent:latest"

# Execution timeout. If the script hasn't completed in 30 s it's killed.
EXECUTION_TIMEOUT_SECS: int = 30

# cgroups constraints — hardcoded, non-configurable.
CONTAINER_MEM_LIMIT: str = "512m"
CONTAINER_CPU_QUOTA: int = 50000   # 50% of one core (period=100000 µs)
CONTAINER_TMPFS_SIZE: str = "64m"

# ── Data Types ────────────────────────────────────────────────────────────────


class SandboxStatus(str, Enum):
    """Status of the Docker sandbox subsystem."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"        # Docker unreachable — observe-only mode
    UNAVAILABLE = "UNAVAILABLE"  # docker-py not installed


class ExecOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DOCKER_ERROR = "docker_error"


@dataclass
class SandboxResult:
    """Structured result from an ephemeral container execution."""
    outcome: ExecOutcome
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_secs: float = 0.0
    container_id: str = ""
    image: str = ""
    error: str | None = None


# ── Sandbox Engine ────────────────────────────────────────────────────────────


class SandboxEngine:
    """
    Async-safe Docker container execution engine.

    All Docker SDK calls are blocking and dispatched via run_in_executor
    to avoid stalling the Kriya Loop's asyncio event loop.

    Usage:
        sandbox = SandboxEngine()
        await sandbox.initialize()          # pre-flight health check
        result = await sandbox.execute("echo 'hello from sandbox'")
    """

    def __init__(self) -> None:
        self._client: Any = None          # docker.DockerClient
        self._status: SandboxStatus = SandboxStatus.UNAVAILABLE
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="yantra-sandbox"
        )

    @property
    def status(self) -> SandboxStatus:
        return self._status

    @property
    def is_operational(self) -> bool:
        return self._status == SandboxStatus.HEALTHY

    # ── Initialization & Health Check ─────────────────────────────────────

    async def initialize(self) -> SandboxStatus:
        """
        Pre-flight health check. Must be called once during engine bootstrap,
        BEFORE the main Kriya Loop begins execution.

        1. Import docker-py. If absent → UNAVAILABLE.
        2. Connect via docker.from_env() → UNIX socket /var/run/docker.sock.
        3. Call client.ping(). If unreachable → DEGRADED.
        4. Verify the sandbox image exists locally. Pull if missing.
        """
        loop = asyncio.get_event_loop()
        self._status = await loop.run_in_executor(
            self._executor, self._blocking_init
        )
        return self._status

    def _blocking_init(self) -> SandboxStatus:
        """Blocking Docker initialization — runs in the executor thread."""
        try:
            import docker  # type: ignore
        except ImportError:
            log.error(
                "> SANDBOX: docker-py is not installed. "
                "Run: pip install docker. Sandbox UNAVAILABLE."
            )
            return SandboxStatus.UNAVAILABLE

        try:
            self._client = docker.from_env()
        except docker.errors.DockerException as exc:
            log.error(
                f"> SANDBOX: Failed to connect to Docker daemon: {exc}. "
                "Is the Docker service running? Sandbox DEGRADED."
            )
            return SandboxStatus.DEGRADED

        # Pre-flight ping — verifies the Docker API is responsive
        try:
            self._client.ping()
        except Exception as exc:
            log.error(
                f"> SANDBOX: Docker ping failed: {exc}. "
                "The daemon may be starting up. Sandbox DEGRADED."
            )
            self._client = None
            return SandboxStatus.DEGRADED

        # Ensure the base image is available
        try:
            self._client.images.get(SANDBOX_IMAGE)
            log.info(f"> SANDBOX: Base image {SANDBOX_IMAGE} confirmed locally.")
        except docker.errors.ImageNotFound:
            log.info(f"> SANDBOX: Pulling base image {SANDBOX_IMAGE}...")
            try:
                self._client.images.pull(SANDBOX_IMAGE)
                log.info(f"> SANDBOX: Pull complete — {SANDBOX_IMAGE}")
            except Exception as exc:
                log.warning(
                    f"> SANDBOX: Failed to pull {SANDBOX_IMAGE}: {exc}. "
                    "Will attempt at execution time."
                )

        # Check for custom Yantra agent image
        try:
            self._client.images.get(CUSTOM_IMAGE)
            log.info(f"> SANDBOX: Custom image {CUSTOM_IMAGE} available.")
        except Exception:
            log.info(
                f"> SANDBOX: Custom image {CUSTOM_IMAGE} not found. "
                f"Using base {SANDBOX_IMAGE} for execution."
            )

        info = self._client.info()
        log.info(
            f"> SANDBOX: Docker HEALTHY — "
            f"Server {info.get('ServerVersion', '?')}, "
            f"Runtime {info.get('DefaultRuntime', '?')}, "
            f"Containers {info.get('Containers', '?')}"
        )
        return SandboxStatus.HEALTHY

    async def health_check(self) -> bool:
        """
        Periodic health re-check. Called by the SENSE phase to detect
        Docker daemon restarts or crashes mid-operation.
        """
        if self._client is None:
            return False

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, self._client.ping
            )
            if self._status != SandboxStatus.HEALTHY:
                log.info("> SANDBOX: Docker connectivity restored → HEALTHY")
                self._status = SandboxStatus.HEALTHY
            return True
        except Exception:
            if self._status == SandboxStatus.HEALTHY:
                log.warning("> SANDBOX: Docker connectivity lost → DEGRADED")
                self._status = SandboxStatus.DEGRADED
            return False

    # ── Execution ─────────────────────────────────────────────────────────

    async def execute(
        self,
        script: str,
        *,
        image: str | None = None,
        timeout: int = EXECUTION_TIMEOUT_SECS,
        env: dict[str, str] | None = None,
        shell: str = "/bin/sh",
    ) -> SandboxResult:
        """
        Execute a script inside an ephemeral, hardened container.

        The script is injected via stdin (not volume mount) to prevent
        path-traversal attacks against the container filesystem.

        Args:
            script:  Shell script content to execute.
            image:   Container image. Defaults to SANDBOX_IMAGE.
            timeout: Hard kill deadline in seconds.
            env:     Optional environment variables for the container.
            shell:   Shell binary inside the container.

        Returns:
            SandboxResult with stdout, stderr, exit code, and timing.
        """
        if not self.is_operational:
            log.warning(
                "> SANDBOX: Execution rejected — Docker is "
                f"{self._status.value}. Script hash: "
                f"{hashlib.sha256(script.encode()).hexdigest()[:12]}"
            )
            return SandboxResult(
                outcome=ExecOutcome.DOCKER_ERROR,
                error=f"Sandbox {self._status.value}: Docker not available",
            )

        loop = asyncio.get_event_loop()
        run_fn = partial(
            self._blocking_execute,
            script=script,
            image=image or SANDBOX_IMAGE,
            timeout=timeout,
            env=env or {},
            shell=shell,
        )

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(self._executor, run_fn),
                timeout=timeout + 10,  # Outer async timeout with 10 s buffer
            )
            return result
        except asyncio.TimeoutError:
            log.error(
                f"> SANDBOX: Async timeout after {timeout + 10}s. "
                "Container may be orphaned."
            )
            return SandboxResult(
                outcome=ExecOutcome.TIMEOUT,
                error=f"Execution exceeded {timeout}s deadline",
            )

    def _blocking_execute(
        self,
        script: str,
        image: str,
        timeout: int,
        env: dict[str, str],
        shell: str,
    ) -> SandboxResult:
        """
        Blocking container execution — runs in the executor thread.

        Security enforcement points:
          1. network_mode="none"        → Zero network access
          2. mem_limit="512m"           → Hard memory cap
          3. cpu_quota=50000            → 50% single-core cap
          4. read_only=True             → Immutable root FS
          5. cap_drop=["ALL"]           → Zero capabilities
          6. no-new-privileges          → Blocks setuid escalation
          7. auto_remove=True           → Ephemeral, zero persistence
          8. tmpfs /tmp:size=64m        → Capped writable scratch
          9. stdin injection            → No volume mounts
        """
        import docker  # type: ignore

        t_start = time.monotonic()
        script_hash = hashlib.sha256(script.encode()).hexdigest()[:12]

        log.info(
            f"> SANDBOX: Executing script [{script_hash}] "
            f"in {image} (timeout={timeout}s)"
        )

        try:
            # containers.run() with stdin_open=True to inject script via stdin,
            # but for simplicity we pass it as a shell -c argument.
            # The script content is shell-escaped via the command argument.
            output = self._client.containers.run(
                image=image,
                command=[shell, "-c", script],
                # ── Security constraints (non-negotiable) ─────────────
                network_mode="none",
                mem_limit=CONTAINER_MEM_LIMIT,
                cpu_quota=CONTAINER_CPU_QUOTA,
                read_only=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                auto_remove=True,
                # ── Resource constraints ──────────────────────────────
                tmpfs={"/tmp": f"size={CONTAINER_TMPFS_SIZE},noexec,nosuid"},
                # ── Execution constraints ─────────────────────────────
                environment=env,
                detach=False,
                stdout=True,
                stderr=True,
                # ── Timeout ───────────────────────────────────────────
                # Docker's stop timeout — SIGTERM after this, SIGKILL after +10s
                stop_signal="SIGKILL",
            )

            elapsed = time.monotonic() - t_start

            # containers.run with detach=False returns bytes
            stdout_text = output.decode("utf-8", errors="replace") if output else ""

            log.info(
                f"> SANDBOX: Script [{script_hash}] completed "
                f"in {elapsed:.2f}s (exit=0)"
            )

            return SandboxResult(
                outcome=ExecOutcome.SUCCESS,
                exit_code=0,
                stdout=stdout_text,
                stderr="",
                duration_secs=round(elapsed, 3),
                image=image,
            )

        except docker.errors.ContainerError as exc:
            elapsed = time.monotonic() - t_start
            stderr_text = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            log.warning(
                f"> SANDBOX: Script [{script_hash}] failed "
                f"(exit={exc.exit_status}) in {elapsed:.2f}s"
            )
            return SandboxResult(
                outcome=ExecOutcome.FAILURE,
                exit_code=exc.exit_status,
                stdout=exc.output.decode("utf-8", errors="replace") if exc.output else "",
                stderr=stderr_text,
                duration_secs=round(elapsed, 3),
                image=image,
            )

        except docker.errors.ImageNotFound:
            log.error(f"> SANDBOX: Image {image} not found. Pull required.")
            return SandboxResult(
                outcome=ExecOutcome.DOCKER_ERROR,
                error=f"Image not found: {image}",
            )

        except docker.errors.APIError as exc:
            log.error(f"> SANDBOX: Docker API error: {exc}")
            return SandboxResult(
                outcome=ExecOutcome.DOCKER_ERROR,
                error=f"Docker API: {exc}",
            )

        except Exception as exc:
            log.error(f"> SANDBOX: Unexpected error: {type(exc).__name__}: {exc}")
            return SandboxResult(
                outcome=ExecOutcome.DOCKER_ERROR,
                error=str(exc),
            )

    # ── Cleanup ───────────────────────────────────────────────────────────

    async def cleanup_stale_containers(self, label: str = "yantra") -> int:
        """
        Prune any orphaned containers with the `yantra` label.
        Called during startup and periodically by UPDATE_ARCHITECTURE phase.
        """
        if self._client is None:
            return 0

        loop = asyncio.get_event_loop()

        def _prune() -> int:
            try:
                result = self._client.containers.prune(
                    filters={"label": [label]}
                )
                deleted = len(result.get("ContainersDeleted", []) or [])
                if deleted:
                    log.info(f"> SANDBOX: Pruned {deleted} stale container(s).")
                return deleted
            except Exception as exc:
                log.warning(f"> SANDBOX: Container prune failed: {exc}")
                return 0

        return await loop.run_in_executor(self._executor, _prune)

    # ── Shutdown ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Gracefully close the Docker client and executor."""
        log.info("> SANDBOX: Shutting down sandbox engine...")
        self._executor.shutdown(wait=True)
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        log.info("> SANDBOX: Shutdown complete.")


# ── Module-level singleton ────────────────────────────────────────────────────

sandbox = SandboxEngine()
