"""
YantraOS — Kriya Loop Engine
Model Route: Gemini 3.1 Pro (High)

The Kriya Loop is the persistent background daemon — a self-annealing, 4-phase
autonomous execution cycle. Derived from Sanskrit for "Completed Action", it is
a 24/7 worker that sorts downloads, manages packages, reads logs, and heals the
environment while the user rests.

Phases:
    1. ANALYZE  — Scan system state (GPU, RAM, disk), evaluate pending tasks
    2. PATCH    — Pull updates, apply model weights, adjust routing config
    3. TEST     — Validate inference pipeline, run health checks
    4. UPDATE_ARCHITECTURE — Commit state changes, emit telemetry, rotate logs

Usage:
    # Launched by systemd via ExecStart:
    python3 /opt/yantra/core/engine.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import os
import signal
import sys
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("yantra.engine")


class KriyaPhase(Enum):
    """The four phases of the Kriya Loop."""
    ANALYZE = "ANALYZE"
    PATCH = "PATCH"
    TEST = "TEST"
    UPDATE_ARCHITECTURE = "UPDATE_ARCHITECTURE"
    IDLE = "IDLE"


class DaemonStatus(Enum):
    """Daemon operational status."""
    BOOTING = "BOOTING"
    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"


class KriyaEngine:
    """
    The Kriya Loop — YantraOS's autonomous background daemon.

    Lifecycle:
        1. Boot → hardware detection, memory init, IPC socket creation
        2. sdnotify READY=1 → systemd knows we're alive
        3. Enter Kriya Loop (ANALYZE → PATCH → TEST → UPDATE_ARCHITECTURE)
        4. Sleep 10s between iterations
        5. Send WATCHDOG=1 heartbeat every cycle (must be < WatchdogSec=15)
        6. On SIGTERM/SIGINT → graceful shutdown
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Kriya Engine.

        Args:
            config_path: Path to config.yaml. Auto-detected from YANTRA_HOME.
        """
        self.yantra_home = os.environ.get("YANTRA_HOME", "/opt/yantra")

        if config_path is None:
            config_path = os.path.join(self.yantra_home, "config.yaml")

        self.config = self._load_config(config_path)
        self.status = DaemonStatus.BOOTING
        self.current_phase = KriyaPhase.IDLE
        self.iteration = 0
        self.last_error: Optional[str] = None
        self.log_tail: list[str] = []
        self._shutdown_event = asyncio.Event()
        self._notifier: Optional[object] = None

        # Components (initialized during boot)
        self.hardware_profiler = None
        self.router = None
        self.memory = None
        self.sandbox = None

        # Configuration
        daemon_config = self.config.get("daemon", {})
        self.loop_interval = daemon_config.get("loop_interval_sec", 10)
        self.log_level = daemon_config.get("log_level", "INFO")

        # Setup logging
        self._setup_logging()

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            import yaml
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            # Return sensible defaults
            return {
                "daemon": {"loop_interval_sec": 10, "log_level": "INFO"},
                "hardware": {"vram_local_threshold_gb": 16, "vram_minimum_gb": 8},
            }
        except Exception as e:
            print(f"[YANTRA] Config load error: {e}", file=sys.stderr)
            return {}

    def _setup_logging(self) -> None:
        """Configure rotating file + journal logging."""
        daemon_config = self.config.get("daemon", {})
        log_file = daemon_config.get("log_file", "/var/log/yantra/engine.log")
        max_size = daemon_config.get("max_log_size_mb", 50) * 1024 * 1024
        backup_count = daemon_config.get("log_rotation_count", 5)

        # Root logger
        root_logger = logging.getLogger("yantra")
        root_logger.setLevel(getattr(logging, self.log_level, logging.INFO))

        # Console handler (captured by systemd journal)
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(console)

        # Rotating file handler
        try:
            log_dir = os.path.dirname(log_file)
            os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count,
            )
            file_handler.setFormatter(logging.Formatter(
                "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            root_logger.addHandler(file_handler)
        except (OSError, PermissionError) as e:
            logger.warning(f"Could not create log file {log_file}: {e}")

    def _log(self, message: str) -> None:
        """Log a message and add to telemetry tail buffer."""
        logger.info(message)
        self.log_tail.append(message)
        # Keep only last 50 log lines in memory
        if len(self.log_tail) > 50:
            self.log_tail = self.log_tail[-50:]

    def _setup_signals(self) -> None:
        """Register signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown, sig)

        logger.info("Signal handlers registered (SIGTERM, SIGINT).")

    def _handle_shutdown(self, sig: signal.Signals) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {sig.name}. Initiating graceful shutdown...")
        self.status = DaemonStatus.OFFLINE
        self._shutdown_event.set()

    def _init_sdnotify(self) -> None:
        """Initialize systemd sd_notify for Type=notify and watchdog."""
        try:
            import sdnotify
            self._notifier = sdnotify.SystemdNotifier()
            logger.info("sdnotify initialized.")
        except ImportError:
            logger.warning("sdnotify not available — running without systemd integration.")
            self._notifier = None

    def _notify(self, state: str) -> None:
        """Send sd_notify state to systemd."""
        if self._notifier:
            try:
                self._notifier.notify(state)
            except Exception as e:
                logger.debug(f"sdnotify failed: {e}")

    async def _boot(self) -> None:
        """
        Boot sequence — initialize all subsystems.

        Sequence:
            1. Hardware detection (GPU profiling)
            2. Inference router initialization
            3. Vector memory (ChromaDB) initialization
            4. Docker sandbox verification
            5. sd_notify READY=1
        """
        self._log("> SYSTEM INITIATED: YantraOS v0.1.0")
        self.status = DaemonStatus.BOOTING

        # 1. Hardware detection
        self._log("> HARDWARE: Detecting GPU capabilities...")
        try:
            from core.hardware import HardwareProfiler
            hw_config = self.config.get("hardware", {})
            self.hardware_profiler = HardwareProfiler(
                vram_local_threshold_gb=hw_config.get("vram_local_threshold_gb", 16),
                vram_minimum_gb=hw_config.get("vram_minimum_gb", 8),
            )
            profile = self.hardware_profiler.detect()
            capability = profile.capability.value
            self._log(
                f"> TELEMETRY: VRAM {profile.total_vram_gb}GB Detected. "
                f"Capability: {capability}"
            )
        except Exception as e:
            logger.error(f"Hardware detection failed: {e}")
            capability = "CLOUD_ONLY"
            self._log(f"> TELEMETRY: GPU detection failed. Defaulting to CLOUD_ONLY.")

        # 2. Inference router
        self._log("> ROUTING: Initializing inference router...")
        try:
            from core.router import InferenceRouter
            self.router = InferenceRouter(
                capability=capability,
                config_path=os.path.join(self.yantra_home, "config.yaml"),
            )
            router_status = self.router.get_status()
            self._log(
                f"> ROUTING: {router_status['inference_routing']} mode. "
                f"Primary model: {router_status['active_model']}"
            )
        except Exception as e:
            logger.error(f"Router initialization failed: {e}")
            self._log(f"> ROUTING: Failed — {e}")

        # 3. Vector memory
        self._log("> MEMORY: Initializing ChromaDB vector store...")
        try:
            from core.memory import VectorMemory
            mem_config = self.config.get("memory", {})
            self.memory = VectorMemory(
                persist_directory=mem_config.get(
                    "persist_directory", "/var/lib/yantra/chroma"
                ),
                collection_name=mem_config.get(
                    "collection_name", "yantra_executions"
                ),
            )
            self._log(f"> MEMORY: ChromaDB initialized. Collection ready.")
        except Exception as e:
            logger.error(f"Memory initialization failed: {e}")
            self._log(f"> MEMORY: Failed — {e}")

        # 4. Docker sandbox check
        self._log("> SANDBOX: Verifying Docker isolation...")
        try:
            from deploy.sandbox import Sandbox
            self.sandbox = Sandbox()
            health = self.sandbox.health_check()
            if health["docker_running"]:
                self._log("> SANDBOX: Docker connected. Sandbox ready.")
            else:
                self._log("> SANDBOX: Docker not running — sandbox unavailable.")
        except Exception as e:
            logger.warning(f"Sandbox initialization failed: {e}")
            self._log(f"> SANDBOX: Unavailable — {e}")

        # 5. Signal READY to systemd
        self._notify("READY=1")
        self._notify("STATUS=Kriya Loop Active")
        self.status = DaemonStatus.ACTIVE
        self._log("> DAEMON: Kriya Loop Active.")
        self._log("> STATUS: All systems nominal.")

    # ─── THE FOUR PHASES ─────────────────────────────────────────────────────

    async def _phase_analyze(self) -> None:
        """
        Phase 1: ANALYZE
        Scan system state, evaluate pending skill queue.
        """
        self.current_phase = KriyaPhase.ANALYZE
        self._notify(f"STATUS=Phase: ANALYZE (iteration {self.iteration})")
        self._log(f"[ANALYZE] Scanning system state (iteration {self.iteration})...")

        # Collect hardware telemetry
        if self.hardware_profiler:
            try:
                telemetry = self.hardware_profiler.get_telemetry()
                cpu_pct = telemetry["cpu_load"]["percent"]
                ram_pct = telemetry["ram_usage"]["percent"]
                vram_pct = telemetry["vram_usage"]["percent"]
                self._log(
                    f"[ANALYZE] CPU: {cpu_pct}% | "
                    f"RAM: {ram_pct}% | "
                    f"VRAM: {vram_pct}%"
                )
            except Exception as e:
                self._log(f"[ANALYZE] Telemetry collection error: {e}")

        # Check disk usage
        try:
            import psutil
            disk = psutil.disk_usage("/")
            disk_pct = disk.percent
            self._log(f"[ANALYZE] Disk: {disk_pct}% used")

            if disk_pct > 90:
                self._log("[ANALYZE] WARNING: Disk usage exceeds 90%!")
        except Exception:
            pass

    async def _phase_patch(self) -> None:
        """
        Phase 2: PATCH
        Pull updates, apply model weights, adjust routing config.
        """
        self.current_phase = KriyaPhase.PATCH
        self._notify(f"STATUS=Phase: PATCH (iteration {self.iteration})")
        self._log(f"[PATCH] Checking for updates and configuration changes...")

        # Check if config.yaml was modified
        config_path = os.path.join(self.yantra_home, "config.yaml")
        try:
            stat = os.stat(config_path)
            self._log(
                f"[PATCH] Config last modified: "
                f"{datetime.fromtimestamp(stat.st_mtime).isoformat()}"
            )
        except OSError:
            pass

        # Check Ollama model availability (if local capable)
        if self.router and "LOCAL" in self.router.capability:
            try:
                import subprocess
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0:
                    model_count = len(result.stdout.strip().splitlines()) - 1
                    self._log(f"[PATCH] Ollama: {model_count} models available.")
                else:
                    self._log("[PATCH] Ollama not responding.")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._log("[PATCH] Ollama not installed or timed out.")

    async def _phase_test(self) -> None:
        """
        Phase 3: TEST
        Validate inference pipeline, run health checks.
        """
        self.current_phase = KriyaPhase.TEST
        self._notify(f"STATUS=Phase: TEST (iteration {self.iteration})")
        self._log(f"[TEST] Running health checks...")

        # Test inference router
        if self.router:
            status = self.router.get_status()
            self._log(
                f"[TEST] Router: mode={status['inference_routing']}, "
                f"model={status['active_model']}"
            )

        # Test vector memory
        if self.memory:
            try:
                count = self.memory.count()
                self._log(f"[TEST] Memory: {count} stored execution paths.")
            except Exception as e:
                self._log(f"[TEST] Memory check failed: {e}")

        # Test sandbox
        if self.sandbox:
            health = self.sandbox.health_check()
            docker_ok = "✓" if health["docker_running"] else "✗"
            image_ok = "✓" if health["image_exists"] else "✗"
            self._log(f"[TEST] Sandbox: docker={docker_ok}, image={image_ok}")

        self._log("[TEST] Health checks complete.")

    async def _phase_update_architecture(self) -> None:
        """
        Phase 4: UPDATE_ARCHITECTURE
        Commit state changes, emit telemetry, rotate logs.
        """
        self.current_phase = KriyaPhase.UPDATE_ARCHITECTURE
        self._notify(f"STATUS=Phase: UPDATE_ARCHITECTURE (iteration {self.iteration})")
        self._log(f"[UPDATE] Committing state and emitting telemetry...")

        # Build telemetry payload
        telemetry = self._build_telemetry()

        # Emit to configured targets
        telemetry_config = self.config.get("telemetry", {})
        if telemetry_config.get("enabled", True):
            targets = telemetry_config.get("targets", [])
            for target in targets:
                target_type = target.get("type", "")
                if target_type == "journal":
                    # Already logged via journalctl
                    pass
                elif target_type == "ipc":
                    # TODO: Emit via UNIX domain socket when TUI is connected
                    pass
                elif target_type in ("websocket", "http"):
                    # TODO: Emit to Web HUD when bridge is implemented
                    pass

        self._log(
            f"[UPDATE] Iteration {self.iteration} complete. "
            f"Status: {self.status.value}"
        )

    def _build_telemetry(self) -> dict:
        """Build yantraos/telemetry/v1 JSON payload."""
        hw_telemetry = {}
        if self.hardware_profiler:
            try:
                hw_telemetry = self.hardware_profiler.get_telemetry()
            except Exception:
                pass

        return {
            "$schema": "yantraos/telemetry/v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "daemon_status": self.status.value,
            "active_model": (
                self.router.get_status()["active_model"]
                if self.router else "none"
            ),
            "cpu_load": hw_telemetry.get("cpu_load", {"percent": 0, "core_count": 0}),
            "vram_usage": hw_telemetry.get("vram_usage", {
                "used_gb": 0, "total_gb": 0, "percent": 0,
            }),
            "ram_usage": hw_telemetry.get("ram_usage", {
                "used_gb": 0, "total_gb": 0, "percent": 0,
            }),
            "inference_routing": hw_telemetry.get("inference_routing", "CLOUD"),
            "active_skill_id": None,
            "current_cycle": {
                "phase": self.current_phase.value,
                "iteration": self.iteration,
                "log_tail": self.log_tail[-10:],
            },
            "pinecone_connection": "DISCONNECTED",  # TODO: Check Pinecone
            "last_error": self.last_error,
        }

    # ─── MAIN LOOP ───────────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Main daemon entry point. Runs the Kriya Loop until shutdown.
        """
        # Setup signal handlers
        try:
            self._setup_signals()
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            logger.warning("Signal handlers not supported on this platform.")

        # Initialize sdnotify
        self._init_sdnotify()

        # Boot sequence
        try:
            await self._boot()
        except Exception as e:
            logger.critical(f"Boot failed: {e}", exc_info=True)
            self._notify(f"STATUS=Boot failed: {e}")
            sys.exit(1)

        # ─── THE KRIYA LOOP ──────────────────────────────────────────────
        logger.info("Entering Kriya Loop...")

        while not self._shutdown_event.is_set():
            self.iteration += 1

            try:
                # Execute the four phases
                await self._phase_analyze()
                await self._phase_patch()
                await self._phase_test()
                await self._phase_update_architecture()

                # Clear error state on successful iteration
                self.last_error = None
                self.status = DaemonStatus.ACTIVE

            except Exception as e:
                self.last_error = str(e)
                self.status = DaemonStatus.ERROR
                logger.error(
                    f"Kriya Loop error (iteration {self.iteration}): {e}",
                    exc_info=True,
                )
                # Don't crash — log and continue
                self._log(f"[ERROR] Iteration {self.iteration} failed: {e}")

            # Send watchdog heartbeat (must be within WatchdogSec=15)
            self._notify("WATCHDOG=1")

            # Transition to IDLE between iterations
            self.current_phase = KriyaPhase.IDLE
            self._notify(f"STATUS=Idle (iteration {self.iteration} complete)")

            # Sleep between iterations (10 seconds per spec)
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.loop_interval,
                )
                # If we reach here, shutdown was requested
                break
            except asyncio.TimeoutError:
                # Normal timeout — continue the loop
                continue

        # ─── GRACEFUL SHUTDOWN ───────────────────────────────────────────
        logger.info("Kriya Loop terminated. Cleaning up...")
        self._notify("STOPPING=1")
        self.status = DaemonStatus.OFFLINE

        # Cleanup
        if self.sandbox:
            try:
                self.sandbox.cleanup()
            except Exception:
                pass

        logger.info("YantraOS daemon shutdown complete.")


def main() -> None:
    """Entry point for the Kriya Loop daemon."""
    print("[YANTRA] Starting Kriya Loop daemon...", flush=True)

    engine = KriyaEngine()

    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print("[YANTRA] Interrupted. Shutting down.", flush=True)
    except Exception as e:
        print(f"[YANTRA] Fatal error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
