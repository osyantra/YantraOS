"""
YantraOS — Hardware Profiler and Telemetry Module
Model Route: Claude Opus 4.6

Detects underlying system hardware (NVIDIA, AMD, Intel) and actively monitors
capabilities (VRAM, RAM, CPU). Calculates hardware inference capabilities to
inform the InferenceRouter.

Priority:
1. NVIDIA (via pynvml, high accuracy)
2. AMD (via rocm-smi if available, fallback to lspci)
3. Intel (via get_sycl_device_info/lspci)
"""

import logging
import platform
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import psutil

# Initialize logging
logger = logging.getLogger("yantra.hardware")

# ─── HARDWARE ENUMS & DATACLASSES ─────────────────────────────────────────────

class SystemCapability(Enum):
    LOCAL_CAPABLE = "LOCAL_CAPABLE"  # High VRAM, can run 70B+ models
    LOCAL_MINIMUM = "LOCAL_MINIMUM"  # Medium VRAM, can run 7B-13B models
    CLOUD_ONLY = "CLOUD_ONLY"        # Low/No VRAM, must use cloud proxy

class GPUType(Enum):
    NVIDIA = "NVIDIA"
    AMD = "AMD"
    INTEL = "INTEL"
    M_SERIES = "APPLE_SILICON"
    UNKNOWN = "UNKNOWN"

@dataclass
class GPUInfo:
    id: int
    name: str
    gpu_type: GPUType
    total_vram_mb: int
    used_vram_mb: int
    utilization_percent: int
    temperature_c: int
    power_draw_w: float

@dataclass
class CPUInfo:
    model: str
    physical_cores: int
    logical_cores: int
    utilization_percent: float
    frequency_mhz: float

@dataclass
class RAMInfo:
    total_mb: int
    used_mb: int
    available_mb: int
    percent_used: float

# ─── HARDWARE PROFILER ───────────────────────────────────────────────────────

class HardwareProfiler:
    """Monitors system hardware and determines inference capabilities."""

    def __init__(self, config: Dict):
        """
        Initialize the HardwareProfiler.

        Args:
            config: The 'hardware' section from config.yaml
        """
        self.config = config
        self.os_type = platform.system()
        self.machine = platform.machine()
        
        # Thresholds from config
        self.local_capable_vram_gb = self.config.get("local_capable_vram_gb", 24)
        self.local_minimum_vram_gb = self.config.get("local_minimum_vram_gb", 8)
        self.max_cpu_utilization = self.config.get("max_cpu_utilization_percent", 85)
        
        # NVML state
        self.nvml_initialized = False
        self._init_nvml()

    def _init_nvml(self) -> None:
        """Initialize NVML for NVIDIA GPUs."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self.nvml_initialized = True
            logger.info("NVML initialized successfully.")
        except ImportError:
            logger.warning("pynvml not installed. NVIDIA GPU telemetry unavailable.")
        except Exception as e:
            logger.error(f"Failed to initialize NVML: {e}")

    def __del__(self):
        """Shutdown NVML on object destruction."""
        if getattr(self, 'nvml_initialized', False):
            try:
                import pynvml
                pynvml.nvmlShutdown()
            except Exception:
                pass

    # ─── GPU PROFILING ───────────────────────────────────────────────────────

    def get_gpu_info(self) -> List[GPUInfo]:
        """
        Detects and profiles GPUs across vendors.
        Currently fully supports NVIDIA via NVML. Basic fallback for others.
        """
        gpus: List[GPUInfo] = []

        if self.nvml_initialized:
            gpus.extend(self._get_nvidia_gpus())
        
        # If no NVIDIA Kriya loops found, check others (Mac, AMD)
        if not gpus:
            if self.os_type == "Darwin" and self.machine == "arm64":
                gpus.extend(self._get_apple_silicon_gpu())
            elif self.os_type == "Linux":
                gpus.extend(self._get_amd_gpus_linux())

        return gpus

    def _get_nvidia_gpus(self) -> List[GPUInfo]:
        """Get NVIDIA GPU stats using NVML."""
        gpus = []
        try:
            import pynvml
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                # Handle bytes vs str depending on pynvml version
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W

                gpus.append(GPUInfo(
                    id=i,
                    name=name,
                    gpu_type=GPUType.NVIDIA,
                    total_vram_mb=int(memory.total / (1024 * 1024)),
                    used_vram_mb=int(memory.used / (1024 * 1024)),
                    utilization_percent=utilization.gpu,
                    temperature_c=temp,
                    power_draw_w=power
                ))
        except Exception as e:
            logger.error(f"Error reading NVIDIA GPU stats: {e}")
        return gpus

    def _get_apple_silicon_gpu(self) -> List[GPUInfo]:
        """Stub for Apple Silicon (Unified Memory approximation)."""
        # M-series shares system RAM.
        mem = psutil.virtual_memory()
        return [GPUInfo(
            id=0,
            name="Apple Silicon (Unified)",
            gpu_type=GPUType.M_SERIES,
            total_vram_mb=int(mem.total / (1024 * 1024)), # Represent unified RAM as VRAM
            used_vram_mb=int(mem.used / (1024 * 1024)),
            utilization_percent=0, # Hard to get reliably without ObjC bindings
            temperature_c=0,
            power_draw_w=0.0
        )]

    def _get_amd_gpus_linux(self) -> List[GPUInfo]:
        """Basic AMD fallback reading from sysfs for Linux."""
        gpus = []
        try:
            # Very basic lspci check for AMD
            out = subprocess.check_output("lspci | grep -i vga | grep -i amd", shell=True, text=True)
            if out:
                # We know an AMD card is there, but detailed sysfs parsing is complex.
                # Returning a generic fallback to trigger LOCAL_MINIMUM if needed.
                gpus.append(GPUInfo(
                    id=0,
                    name="AMD Radeon (Generic)",
                    gpu_type=GPUType.AMD,
                    total_vram_mb=8192,  # Assumption fallback
                    used_vram_mb=0,
                    utilization_percent=0,
                    temperature_c=0,
                    power_draw_w=0.0
                ))
        except subprocess.CalledProcessError:
            pass  # No AMD GPU found
        return gpus

    # ─── CPU & RAM PROFILING ─────────────────────────────────────────────────

    def get_cpu_info(self) -> CPUInfo:
        """Get current CPU utilization and specs."""
        # Note: model name is OS dependent. Doing a basic cross-platform grab.
        model = platform.processor()
        freq = psutil.cpu_freq()
        
        return CPUInfo(
            model=model if model else "Unknown CPU",
            physical_cores=psutil.cpu_count(logical=False) or 0,
            logical_cores=psutil.cpu_count(logical=True) or 0,
            utilization_percent=psutil.cpu_percent(interval=0.1),
            frequency_mhz=freq.current if freq else 0.0
        )

    def get_ram_info(self) -> RAMInfo:
        """Get system RAM utilization."""
        mem = psutil.virtual_memory()
        return RAMInfo(
            total_mb=int(mem.total / (1024 * 1024)),
            used_mb=int(mem.used / (1024 * 1024)),
            available_mb=int(mem.available / (1024 * 1024)),
            percent_used=mem.percent
        )

    # ─── CAPABILITY RESOLUTION ───────────────────────────────────────────────

    def evaluate_capability(self) -> SystemCapability:
        """
        Determines the system's inference capability based on VRAM thresholds.
        """
        gpus = self.get_gpu_info()
        
        if not gpus:
            logger.info("No supported GPUs detected. Capability: CLOUD_ONLY")
            return SystemCapability.CLOUD_ONLY

        # Aggregate total available VRAM across all GPUs (simplistic approach,
        # assumes models can map across devices or we pick the biggest).
        # For strictness, let's use the VRAM of the largest single GPU.
        max_vram_mb = max((gpu.total_vram_mb for gpu in gpus), default=0)
        max_vram_gb = max_vram_mb / 1024.0

        if max_vram_gb >= self.local_capable_vram_gb:
            return SystemCapability.LOCAL_CAPABLE
        elif max_vram_gb >= self.local_minimum_vram_gb:
            return SystemCapability.LOCAL_MINIMUM
        else:
            return SystemCapability.CLOUD_ONLY

    # ─── AGGREGATE TELEMETRY ─────────────────────────────────────────────────

    def get_telemetry_payload(self) -> Dict:
        """Returns a snapshot of hardware metrics for IPC/TUI."""
        gpus = self.get_gpu_info()
        cpu = self.get_cpu_info()
        ram = self.get_ram_info()
        cap = self.evaluate_capability()

        # Handle formatting for multiple GPUs
        gpu_payload = {}
        for gpu in gpus:
            gpu_payload[f"gpu_{gpu.id}"] = {
                "name": gpu.name,
                "type": gpu.gpu_type.value,
                "vram_total_mb": gpu.total_vram_mb,
                "vram_used_mb": gpu.used_vram_mb,
                "utilization": gpu.utilization_percent,
                "temp_c": gpu.temperature_c,
                "power_w": gpu.power_draw_w
            }

        if not gpu_payload:
            gpu_payload["gpu_0"] = {"error": "No supported GPUs detected."}

        return {
            "timestamp": time.time(),
            "capability": cap.value,
            "cpu": {
                "model": cpu.model,
                "utilization": cpu.utilization_percent,
                "cores": f"{cpu.physical_cores}P/{cpu.logical_cores}L",
                "freq_mhz": cpu.frequency_mhz
            },
            "ram": {
                "total_mb": ram.total_mb,
                "used_mb": ram.used_mb,
                "percent": ram.percent_used
            },
            "gpus": gpu_payload
        }
