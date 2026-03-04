# Quickstart — installing llama-cpp-python

This page explains how to install the `llama-cpp-python` bindings used by
`LlamaCppProvider`. It covers common platforms and both CPU-only and GPU setups.

This project exposes an optional dependency group which includes LLM dependencies.

If you are working inside a local clone of this repository (developer):

    pdm install -G llm

If you are installing from PyPI into another project:

    pip install "vector-inspector[llm]"

If you prefer to manage `llama-cpp-python` yourself (recommended for advanced
users), follow the guidelines below.

Prerequisites
 - Python 3.11 or later (the project targets py312; check your virtualenv)
 - Up-to-date `pip`, `setuptools`, and `wheel`:

    python -m pip install --upgrade pip setuptools wheel

If installation fails while building native wheels, install the platform build
tools (see each OS section).

CPU-only installation (recommended for quick start)
 - This is the simplest path. On most platforms `pip install llama-cpp-python`
   will install a prebuilt wheel.

    python -m pip install llama-cpp-python

 - Verify the installation:

    python -c "import llama_cpp; print('llama-cpp-python', llama_cpp.__version__)"

macOS
 - Install Xcode command line tools if not present:

    xcode-select --install

 - Install `libomp` which is commonly required by native wheels:

    brew install libomp

 - Then install via pip (see CPU-only notes above).

Windows
 - Most users can install the prebuilt wheel with `pip`.
 - If pip attempts to build from source you will need the Visual C++ Build
   Tools / MSVC toolchain. Install the "Build Tools for Visual Studio" and
   include the C++ build tools workload.

    https://visualstudio.microsoft.com/downloads/

 - Then run the CPU install command.

Linux
 - Install standard build essentials (if pip needs to build):

    # Debian/Ubuntu
    sudo apt update && sudo apt install -y build-essential cmake libomp-dev

    # Fedora
    sudo dnf install -y @development-tools cmake libgomp

 - Then run the CPU install command.

GPU (NVIDIA/CUDA) installations
 - GPU support requires an NVIDIA GPU, matching drivers, and CUDA toolkit
   installed on the system. The exact CUDA version required depends on the
   `llama-cpp` native build and the prebuilt wheel availability.

 - Common steps:
   1. Install NVIDIA driver for your GPU (from NVIDIA).
   2. Install CUDA toolkit that matches the wheel or your intended build.
   3. Ensure `nvcc` and CUDA libraries are on `PATH`/`LD_LIBRARY_PATH`.
   4. Install `llama-cpp-python` — if a CUDA-enabled wheel exists for your
      platform the regular `pip install` will pick it up; otherwise you may
      need to build from source per the library README.

 - Building with CUDA may require additional dependencies (CUDA SDK, cuBLAS,
   etc.). Consult the `llama-cpp-python` README for exact build flags and
   supported CUDA versions.

Troubleshooting
 - If you see errors about missing compilers, install the platform build
   tools listed above (Xcode CLT, Visual C++ Build Tools, build-essential).
 - If pip fails to find a wheel and building from source fails, check the
   project's releases for prebuilt wheels that match your platform/CUDA
   version.

Downloading a GGUF model
 - `LlamaCppProvider` looks for GGUF models in the LLM cache (see
   `get_llm_cache_dir()` in `llama_cpp_provider.py`). You can download a
   model manually into that directory or use the application's helper that
   downloads the default model URL used by this project.

Verify everything from Python

    python -c "import llama_cpp; print('llama-cpp-python', llama_cpp.__version__)"

If `import llama_cpp` fails but you installed via the project extras,
re-run the installation command in the same virtual environment used to run
the application.

More information
 - The authoritative instructions and platform-specific notes are maintained
   in the `llama-cpp-python` repository and its README — consult that
   resource for advanced build options and CUDA-specific guidance.
 - GitHub repository: https://github.com/abetlen/llama-cpp-python
