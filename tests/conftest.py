"""Pytest configuration: register the network marker."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "network: requires network access to the BSI source")
