"""Hardware info utilities for Vector Inspector."""

from vector_inspector.core.logging import log_warning


def get_hardware_info():
    """
    Returns a dictionary with CPU, RAM, and GPU info (if available).
    Uses psutil and GPUtil if installed, otherwise falls back to stdlib.
    """
    import os
    import platform

    info = {}

    # CPU info
    try:
        import psutil

        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["cpu_physical_cores"] = psutil.cpu_count(logical=False)
        info["cpu_freq_mhz"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
        info["cpu_model"] = platform.processor() or platform.uname().processor
    except ImportError:
        info["cpu_count"] = os.cpu_count()
        info["cpu_model"] = platform.processor() or platform.uname().processor

    # RAM info
    try:
        import psutil

        info["ram_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
    except ImportError:
        info["ram_total_gb"] = None

    # GPU info
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="GPUtil")

            import GPUtil

            gpus = GPUtil.getGPUs()
            if gpus:
                info["gpu"] = [
                    {
                        "name": gpu.name,
                        "memory_total_mb": gpu.memoryTotal,
                        "driver": gpu.driver,
                        "uuid": gpu.uuid,
                    }
                    for gpu in gpus
                ]
            else:
                info["gpu"] = []
    except ImportError:
        log_warning("GPUtil not installed; GPU info will be unavailable.")
        info["gpu"] = None
    except Exception:
        info["gpu"] = None

    return info
