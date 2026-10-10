"""Package release version helpers."""

from importlib.metadata import PackageNotFoundError, version


def package_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"
