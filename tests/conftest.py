"""
Shared fixtures and utilities for Pytanque tests.

This module contains common fixtures and helper functions used across
both unit tests and integration tests.
"""

import pytest
import logging
import subprocess
import time
import socket
import os
from typing import Generator

from pytanque import Pytanque


# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_shared")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open and accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, ConnectionRefusedError, OSError):
        return False


@pytest.fixture(scope="session")
def server_config():
    """Server configuration for tests."""
    return {"host": "127.0.0.1", "port": 8765}


@pytest.fixture(scope="session")
def petanque_server(server_config) -> Generator[subprocess.Popen, None, None]:
    """
    Start and manage the Petanque server process for the test session.

    This fixture will:
    1. Check if server is already running
    2. Start pet-server if needed
    3. Wait for server to be ready
    4. Yield the process
    5. Clean up the server process after tests
    """
    host = server_config["host"]
    port = server_config["port"]

    # Check if server is already running
    if is_port_open(host, port):
        logger.info(f"Server already running on {host}:{port}")
        yield None
        return

    # Start the server
    logger.info(f"Starting pet-server on port {port}")
    try:
        # Start pet-server with the specified port
        process = subprocess.Popen(
            ["pet-server", "-p", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=(
                os.setsid if os.name != "nt" else None
            ),  # Create process group on Unix
        )

        # Wait for server to be ready
        time.sleep(5)
        if not is_port_open(host, port):
            # Server didn't start properly
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            pytest.fail(
                f"Pet-server failed to start within 5 seconds.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        logger.info("Pet-server started successfully")
        yield process

    except FileNotFoundError:
        pytest.skip(
            "pet-server executable not found in PATH. Please ensure pet-server is installed and available."
        )

    except Exception as e:
        pytest.fail(f"Failed to start pet-server: {e}")

    finally:
        # Clean up the server process
        if "process" in locals() and process.poll() is None:
            logger.info("Shutting down pet-server")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Pet-server didn't shut down gracefully, forcing kill")
                process.kill()
                process.wait()
            logger.info("Pet-server shut down")


@pytest.fixture(scope="session")
def example_files():
    """Paths to example files."""
    return {"foo_v": "./examples/foo.v", "examples_dir": "./examples/"}


@pytest.fixture(scope="function")
def client(server_config, petanque_server):
    """Create a Pytanque client for each test."""
    # petanque_server fixture ensures server is running
    return Pytanque(server_config["host"], server_config["port"])


@pytest.fixture(scope="function")
def connected_client(server_config, petanque_server):
    """Create and connect a Pytanque client for each test."""
    # petanque_server fixture ensures server is running
    client = Pytanque(server_config["host"], server_config["port"])
    try:
        client.connect()
        yield client
    finally:
        client.close()
