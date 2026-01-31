"""
Pytest configuration for async tests.

This conftest.py configures pytest-asyncio to use auto mode,
which automatically handles async test functions marked with
@pytest.mark.asyncio decorator.
"""
import pytest


# Configure pytest-asyncio to use auto mode
# This ensures all async test functions are properly handled
pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an async test."
    )
