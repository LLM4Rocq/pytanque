"""
Test for stdio communication with petanque subprocess.

These tests verify that the Pytanque client can communicate with petanque
via stdin/stdout subprocess communication using LSP message format as an
alternative to socket communication.

Note: These tests require the 'pet' command to be available in PATH.
Tests will be skipped if 'pet' is not found.
"""

import pytest
import subprocess
import shutil
import logging

from pytanque import Pytanque, PetanqueError, PytanqueMode

# Note: These tests communicate with pet subprocess via LSP protocol


class TestStdioMode:
    """Test stdio subprocess communication mode."""

    @pytest.fixture(autouse=True, scope="class")
    def setup_logging(self):
        """Set up logging for debugging."""
        logging.basicConfig()
        logging.getLogger("pytanque.client").setLevel(logging.INFO)

    @pytest.fixture(scope="class")
    def check_pet_available(self):
        """Check if the 'pet' command is available."""
        if shutil.which("pet") is None:
            pytest.skip("pet command not found - skipping stdio tests")

    def test_stdio_smoke_test(self, check_pet_available, example_files):
        """Quick smoke test to verify basic stdio functionality."""
        print("Creating stdio client...")
        client = Pytanque(mode=PytanqueMode.STDIO)
        print("Connecting to subprocess...")
        client.connect()

        print("Checking process status...")
        assert client.process is not None
        assert client.process.poll() is None  # Process should be running
        print(f"Pet process PID: {client.process.pid}")

        print("Testing set_workspace...")
        try:
            client.set_workspace(debug=False, dir="./examples/")
            print("set_workspace succeeded!")
        except Exception as e:
            print(f"set_workspace failed: {e}")
            # Check if process is still alive
            if client.process.poll() is not None:
                stdout, stderr = client.process.communicate()
                print(f"Process died. STDOUT: {stdout}")
                print(f"Process died. STDERR: {stderr}")
            raise
        finally:
            print("Closing client...")
            client.close()
            print("Smoke test completed")

    def test_stdio_basic_workflow(self, check_pet_available, example_files):
        """Test basic proof workflow in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            # Set workspace
            client.set_workspace(debug=False, dir="./examples/")

            # Get table of contents
            toc = client.toc("./examples/foo.v")
            assert isinstance(toc, list)
            assert len(toc) > 0
            print(f"TOC: {len(toc)} items")

            # Start proof
            state = client.start("./examples/foo.v", "addnC")
            assert state.st is not None
            print(f"Started proof, state: {state.st}")

            # Get initial goals
            goals = client.goals(state)
            assert isinstance(goals, list)
            print(f"Initial goals: {len(goals)}")

            # Execute a tactic
            state = client.run(state, "induction n.")
            assert state.st is not None
            print(f"After induction, state: {state.st}")

    def test_stdio_state_at_pos_operations(self, check_pet_available, example_files):
        """Test state-related operations in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            client.set_workspace(debug=False, dir="./examples/")

            # Test get_root_state
            root_state = client.get_root_state("./examples/foo.v")
            assert root_state.st is not None
            print(f"Root state: {root_state.st}")

            # Test get_state_at_pos
            pos_state = client.get_state_at_pos("./examples/foo.v", line=1, character=0)
            assert pos_state.st is not None
            print(f"Position state: {pos_state.st}")

            # Test start
            start_state = client.start("./examples/foo.v", "addnC")
            assert start_state.st is not None

            # Test state_hash
            hash_val = client.state_hash(start_state)
            assert isinstance(hash_val, int)
            print(f"State hash: {hash_val}")

    def test_stdio_ast_functionality(self, check_pet_available, example_files):
        """Test AST functionality in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            client.set_workspace(debug=False, dir="./examples/")
            state = client.start("./examples/foo.v", "addnC")

            # Test ast method
            ast = client.ast(state, "auto.")
            assert isinstance(ast, dict)
            print(f"AST result: {type(ast)}")

            # Test ast_at_pos method
            file_ast = client.ast_at_pos("./examples/foo.v", line=2, character=0)
            assert isinstance(file_ast, dict)
            print(f"File AST result: {type(file_ast)}")

    def test_stdio_vs_socket_comparison(
        self, check_pet_available, example_files, petanque_server
    ):
        """Compare stdio and socket modes to ensure they behave similarly."""
        # Test with stdio mode
        with Pytanque(mode=PytanqueMode.STDIO) as stdio_client:
            stdio_client.set_workspace(debug=False, dir="./examples/")
            stdio_toc = stdio_client.toc("./examples/foo.v")

        # Test with socket mode
        with Pytanque("127.0.0.1", 8765, mode=PytanqueMode.SOCKET) as socket_client:
            socket_client.set_workspace(debug=False, dir="./examples/")
            socket_toc = socket_client.toc("./examples/foo.v")

        # Compare results
        assert len(stdio_toc) == len(socket_toc)

        # Both should have the same theorem names
        stdio_names = [name for name, _ in stdio_toc]
        socket_names = [name for name, _ in socket_toc]
        assert set(stdio_names) == set(socket_names)

    def test_stdio_search_commands(self, check_pet_available, example_files):
        """Test search commands in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            client.set_workspace(debug=False, dir="./examples/")
            state = client.start("./examples/foo.v", "addnC")

            # Execute search command
            search_state = client.run(state, "Search nat.")
            assert isinstance(search_state.feedback, list)

            # Check that feedback contains search results
            search_feedback = [
                msg
                for level, msg in search_state.feedback
                if "nat" in msg.lower() or "search" in msg.lower()
            ]
            print(f"Search feedback entries: {len(search_feedback)}")

    def test_stdio_error_handling(self, check_pet_available, example_files):
        """Test error handling in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            client.set_workspace(debug=False, dir="./examples/")

            # Test with invalid theorem name
            with pytest.raises(PetanqueError):
                client.start("./examples/foo.v", "nonexistent_theorem")

    def test_stdio_premises(self, check_pet_available, example_files):
        """Test premises functionality in stdio mode."""
        with Pytanque(mode=PytanqueMode.STDIO) as client:
            client.set_workspace(debug=False, dir="./examples/")
            state = client.start("./examples/foo.v", "addnC")

            # Get premises
            premises = client.premises(state)
            assert isinstance(premises, list)
            print(f"Available premises: {len(premises)}")


class TestStdioConstructor:
    """Test constructor behavior for stdio mode."""

    def test_stdio_constructor_valid(self):
        """Test valid stdio constructor."""
        client = Pytanque(mode=PytanqueMode.STDIO)
        assert client.mode == "stdio"
        assert client.process is None  # Not connected yet
        assert client.host is None
        assert client.port is None
        assert client.socket is None

    def test_socket_constructor_valid(self):
        """Test valid socket constructor (ensure compatibility)."""
        client = Pytanque("127.0.0.1", 8765, mode=PytanqueMode.SOCKET)
        assert client.mode == "socket"
        assert client.host == "127.0.0.1"
        assert client.port == 8765
        assert client.process is None
        assert client.socket is not None

    def test_constructor_invalid_args(self):
        """Test invalid constructor arguments."""
        # No arguments should raise ValueError
        with pytest.raises(ValueError):
            Pytanque()

        # Partial socket args should raise ValueError
        with pytest.raises(ValueError):
            Pytanque(host="127.0.0.1")

        with pytest.raises(ValueError):
            Pytanque(port=8765)


if __name__ == "__main__":
    # Allow running the test file directly
    pytest.main([__file__, "-v", "--tb=short"])
