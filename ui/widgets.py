"""
YantraOS — UI Widgets
Model Route: Claude Opus 4.6

Specific TUI components for the Yantra Shell.
Widgets:
- GPUHealth: Displays real-time hardware telemetry (VRAM, Util, Temps).
- ThoughtStream: Shows the real-time reasoning and Kriya Loop states of the daemon.
"""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll, Vertical
from textual.widget import Widget
from textual.widgets import Static, Label

class GPUHealth(Widget):
    """Displays critical GPU and hardware health metrics."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stats_container = Vertical()

    def compose(self) -> ComposeResult:
        yield Label("HARDWARE TELEMETRY", classes="pane-title")
        yield self.stats_container

    def update_stats(self, telemetry: dict) -> None:
        """Update the widget with fresh telemetry from the daemon."""
        # Clear existing
        self.stats_container.query(Static).remove()
        
        gpus = telemetry.get("gpus", {})
        if not gpus:
            self.stats_container.mount(Label("No GPU Data", classes="gpu-alert"))
            return

        for gpu_id, stat in gpus.items():
            if "error" in stat:
                self.stats_container.mount(Label(stat["error"], classes="gpu-alert"))
                continue

            name = stat.get("name", "Unknown GPU")
            vram_total = stat.get("vram_total_mb", 0)
            vram_used = stat.get("vram_used_mb", 0)
            util = stat.get("utilization", 0)
            temp = stat.get("temp_c", 0)
            power = stat.get("power_w", 0.0)

            pct = (vram_used / vram_total * 100) if vram_total else 0
            vram_color = "gpu-alert" if pct > 85 else "gpu-stat-value"
            
            self.stats_container.mount(Label(f"[{gpu_id}] {name}", classes="gpu-stat-label"))
            self.stats_container.mount(Static(
                Text.assemble(("Util: ", "gpu-stat-label"), (f"{util}%", "gpu-stat-value"),
                              (" | Temp: ", "gpu-stat-label"), (f"{temp}°C", "gpu-stat-value"))
            ))
            self.stats_container.mount(Static(
                Text.assemble(("VRAM: ", "gpu-stat-label"), 
                              (f"{vram_used} / {vram_total} MB", vram_color))
            ))
            self.stats_container.mount(Static(
                Text.assemble(("Pwr : ", "gpu-stat-label"), (f"{power:.1f}W", "gpu-stat-value"))
            ))
            self.stats_container.mount(Static("")) # Spacer

        # Add Engine status
        status = telemetry.get("daemon_status", "UNKNOWN")
        phase = telemetry.get("current_cycle", {}).get("phase", "NONE")
        
        self.stats_container.mount(Label("ENGINE STATUS", classes="pane-title"))
        status_color = "gpu-alert" if status == "ERROR" else "gpu-stat-value"
        self.stats_container.mount(Static(
            Text.assemble(("Daemon: ", "gpu-stat-label"), (status, status_color))
        ))
        self.stats_container.mount(Static(
            Text.assemble(("Phase : ", "gpu-stat-label"), (phase, "gpu-stat-value"))
        ))

class ThoughtStream(Widget):
    """Displays the daemon's internal log tail / thoughts in the main pane."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_container = VerticalScroll(id="thought-scroll")

    def compose(self) -> ComposeResult:
        yield Label("THOUGHT STREAM", classes="pane-title")
        yield self.log_container

    def push_log(self, text: str) -> None:
        """Push a new log entry to the bottom of the stream."""
        if "[ERROR]" in text:
            classes = "log-entry-error"
        elif "[YANTRA]" in text or ">" in text:
            classes = "log-entry-info"
        else:
            classes = "log-entry"
            
        self.log_container.mount(Static(text, classes=classes))
        self.log_container.scroll_end(animate=False)

    def update_logs(self, log_lines: list[str]) -> None:
        """Replace all logs (from telemetry sync)."""
        # Only add new lines to avoid flickering
        # For simplicity in this iteration, we clear if there's a big mismatch
        # but a proper diff is better. We will just rewrite them safely.
        self.log_container.query(Static).remove()
        for line in log_lines:
            self.push_log(line)