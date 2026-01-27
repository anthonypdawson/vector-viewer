def get_app_version():
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:
        try:
            from importlib_metadata import version, PackageNotFoundError  # type: ignore
        except ImportError:
            return "?"
    try:
        return version("vector-inspector")
    except PackageNotFoundError:
        return "?"
