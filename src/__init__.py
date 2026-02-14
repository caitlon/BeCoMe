"""BeCoMe (Best Compromise Mean) method for group decision-making."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("become")
except PackageNotFoundError:
    __version__ = "0.0.0"
