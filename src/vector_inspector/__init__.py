"""Vector Inspector - A comprehensive desktop application for vector database visualization."""

__version__ = "0.3.9"  # Keep in sync with pyproject.toml for dev mode fallback


def get_version():
    try:
        from importlib.metadata import version, PackageNotFoundError

        return version("vector-inspector")
    except Exception:
        return __version__
