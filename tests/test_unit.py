"""
Unit tests for Pytanque - testing individual methods with server connection.

These tests focus on testing individual API methods and components.
"""

import pytest
from pathlib import Path

from pytanque import Pytanque, PetanqueError, InspectPhysical, InspectGoals
from pytanque.protocol import StartParams
from pytanque.response import GoalsResponse
from pytanque.routes import RouteName

class TestPytanqueConstructor:
    """Test constructor examples from docstrings."""

    def test_constructor_example(self, server_config, petanque_server):
        """Test basic constructor example."""
        client = Pytanque("127.0.0.1", 8765)
        assert client.host == "127.0.0.1"
        assert client.port == 8765
        assert client.id == 0


class TestConnectionMethods:
    """Test connection method examples."""

    def test_connect_close_example(self, server_config, petanque_server):
        """Test connect and close example."""
        client = Pytanque("127.0.0.1", 8765)
        client.connect()
        # Connection should be established
        assert client.socket is not None
        client.close()

    def test_context_manager_example(
        self, server_config, example_files, petanque_server
    ):
        """Test context manager example from class docstring."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Connection should be automatic
            assert client.socket is not None
            # Try basic operation
            state = client.start(example_files["foo_v"], "addnC")
            assert state.st is not None
            assert isinstance(state.proof_finished, bool)


class TestQueryMethod:
    """Test query method examples."""

    def test_query_example(self, server_config, petanque_server):
        """Test low-level query example."""
        client = Pytanque("127.0.0.1", 8765)
        client.connect()
        try:
            # Use StartParams as in the example
            uri = Path("./examples/foo.v").resolve().as_uri()
            params = StartParams(uri, "addnC")
            response = client.query(RouteName.START, params)
            assert response.id is not None
            assert response.result is not None
        finally:
            client.close()


class TestStartMethod:
    """Test start method examples."""

    def test_start_basic_example(self, server_config, example_files, petanque_server):
        """Test basic start example."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")
            print(f"Initial state: {state.st}, finished: {state.proof_finished}")
            assert state.st is not None
            assert isinstance(state.proof_finished, bool)

    def test_start_with_workspace_setup(
        self, server_config, example_files, petanque_server
    ):
        """Test start with workspace setup."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Setup workspace first
            client.set_workspace(debug=False, dir="./examples/")
            state = client.start("./examples/foo.v", "addnC")
            assert state.st is not None


class TestRunMethod:
    """Test run method examples."""

    def test_run_tactic_examples(self, server_config, example_files, petanque_server):
        """Test run method with tactics."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Execute tactic
            state = client.run(state, "induction n.", verbose=True)
            assert state.st is not None

            # Execute with timeout
            state = client.run(state, "auto.", timeout=5)
            assert state.st is not None

    def test_run_search_commands(self, server_config, example_files, petanque_server):
        """Test run method with search commands."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Execute search command and check feedback
            state = client.run(state, "Search nat.")
            assert state.st is not None
            assert hasattr(state, "feedback")
            assert isinstance(state.feedback, list)

            # Check feedback contains search results
            for level, msg in state.feedback:
                print(f"Level {level}: {msg}")
                assert isinstance(level, int)
                assert isinstance(msg, str)

    def test_run_print_commands(self, server_config, example_files, petanque_server):
        """Test run method with print commands."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Execute print command
            state = client.run(state, "Print list.")
            assert state.st is not None
            print("Print output in feedback:", state.feedback)
            assert isinstance(state.feedback, list)

    def test_run_check_commands(self, server_config, example_files, petanque_server):
        """Test run method with check commands."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Execute check command
            state = client.run(state, "Check (1 + 1).")
            assert state.st is not None
            print("Print output in feedback:", state.feedback)
            assert isinstance(state.feedback, list)


class TestGoalsMethod:
    """Test goals method examples."""

    def test_goals_example(self, server_config, example_files, petanque_server):
        """Test goals method example."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")
            goals = client.goals(state)
            assert isinstance(goals, list)
            assert hasattr(goals[0], "pp")
            assert hasattr(goals[0], "ty")
            assert hasattr(goals[0], "hyps")

            print(f"Number of goals: {len(goals)}")
            for i, goal in enumerate(goals):
                print(f"Goal {i}: {goal.pp}")


class TestPremisesMethod:
    """Test premises method examples."""

    def test_premises_example(self, server_config, example_files, petanque_server):
        """Test premises method example."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")
            premises = client.premises(state)
            print(f"Available premises: {len(premises)}")

            assert premises is not None
            assert isinstance(premises, list)


class TestStateEqualMethod:
    """Test state_equal method examples."""

    def test_state_equal_example(self, server_config, example_files, petanque_server):
        """Test state_equal method example."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Create initial state
            state1 = client.start("./examples/foo.v", "addnC")

            # Create another state from the same starting point
            state2 = client.start("./examples/foo.v", "addnC")

            # States should be equal both physically and in terms of goals
            physical_equal = client.state_equal(state1, state2, InspectPhysical)
            goals_equal = client.state_equal(state1, state2, InspectGoals)

            assert physical_equal == True
            assert goals_equal == True
            print(f"Physical equal: {physical_equal}, Goals equal: {goals_equal}")

            # Run a tactic on one state
            state3 = client.run(state1, "induction n.")

            # States should no longer be equal
            physical_equal_after = client.state_equal(state1, state3, InspectPhysical)
            goals_equal_after = client.state_equal(state1, state3, InspectGoals)

            assert physical_equal_after == False
            assert goals_equal_after == False
            print(
                f"After tactic - Physical equal: {physical_equal_after}, Goals equal: {goals_equal_after}"
            )


class TestStateHashMethod:
    """Test state_hash method examples."""

    def test_state_hash_example(self, server_config, example_files, petanque_server):
        """Test state_hash method example."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")
            hash_value = client.state_hash(state)
            print(f"State hash: {hash_value}")

            assert isinstance(hash_value, int)


class TestTocMethod:
    """Test toc method examples."""

    def test_toc_example(self, server_config, petanque_server):
        """Test toc method example."""
        with Pytanque("127.0.0.1", 8765) as client:
            toc = client.toc("./examples/foo.v")
            assert isinstance(toc, list)
            assert all(isinstance(item, tuple) and len(item) == 2 for item in toc)

            print("Available definitions:")
            for name, definitions in toc:
                for definition in definitions:
                    print(f"  {name}: {definition.detail}")


class TestPetanqueErrorHandling:
    """Test PetanqueError examples."""

    def test_petanque_error_example(self, server_config, petanque_server):
        """Test PetanqueError handling example."""
        try:
            with Pytanque("127.0.0.1", 8765) as client:
                # Try to start with non-existent file - should raise PetanqueError
                state = client.start("./nonexistent.v", "theorem")
        except PetanqueError as e:
            print(f"Petanque error {e.code}: {e.message}")
            assert hasattr(e, "code")
            assert hasattr(e, "message")
            assert isinstance(e.code, int)
            assert isinstance(e.message, str)
        except FileNotFoundError:
            # This is also acceptable - the file doesn't exist
            pass


class TestASTMethods:
    """Test AST parsing methods."""

    def test_ast_method_tactics(self, server_config, example_files, petanque_server):
        """Test ast method with tactics."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Get AST for a tactic
            ast = client.ast(state, "induction n.")
            print("Tactic AST:", ast)
            assert isinstance(ast, dict)

    def test_ast_method_search(self, server_config, example_files, petanque_server):
        """Test ast method with search commands."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Get AST for a search command
            ast = client.ast(state, "Search nat.")
            print("Search AST:", ast)
            assert isinstance(ast, dict)

    def test_ast_method_expressions(
        self, server_config, example_files, petanque_server
    ):
        """Test ast method with expressions."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Get AST for a complex expression
            ast = client.ast(state, "fun x => x + 1.")
            print("Expression AST:", ast)
            assert isinstance(ast, dict)

    def test_ast_at_pos_examples(self, server_config, example_files, petanque_server):
        """Test ast_at_pos method."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Get AST at theorem declaration
            ast = client.ast_at_pos("./examples/foo.v", line=3, character=28)
            print("Theorem declaration AST:", ast)
            assert isinstance(ast, dict)

            # Get AST at proof step
            ast = client.ast_at_pos("./examples/foo.v", line=3, character=5)
            print("Proof step AST:", ast)
            assert isinstance(ast, dict)


class TestPositionBasedMethods:
    """Test position-based state retrieval methods."""

    def test_get_state_at_pos_examples(
        self, server_config, example_files, petanque_server
    ):
        """Test get_state_at_pos method."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Get state at beginning of proof
            state = client.get_state_at_pos("./examples/foo.v", line=4, character=0)
            print(f"State at start: {state.st}, finished: {state.proof_finished}")
            assert state.st is not None
            assert not state.proof_finished
            assert hasattr(state, "feedback")

            # Get state in middle of proof and check goals
            state = client.get_state_at_pos("./examples/foo.v", line=5, character=2)
            goals = client.goals(state)
            print(f"Goals at position: {goals}")
            assert goals

            # Get state at end of proof
            state = client.get_state_at_pos("./examples/foo.v", line=7, character=0)
            print(f"Proof finished: {state.proof_finished}")
            assert state.proof_finished

    def test_get_root_state_examples(
        self, server_config, example_files, petanque_server
    ):
        """Test get_root_state method."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Get the root state of a file
            root_state = client.get_root_state("./examples/foo.v")
            print(f"Root state: {root_state.st}")
            assert root_state.st is not None

class TestCompleteGoals:
    """Test complete_goals functionality."""

    def test_complete_goals_start(self, server_config, example_files, petanque_server):
        """Test complete goals at the beginning of a proof."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnAC")
            complete_goals = client.complete_goals(state, pretty=True)
            GoalsResponse.from_json(complete_goals.to_json())

    def test_complete_goals_end(self, server_config, example_files, petanque_server):
        """Test complete goals at the end of a proof."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")
            state = client.run(state, "by elim: n => //= ? ->.")
            complete_goals = client.complete_goals(state, pretty=True)
            GoalsResponse.from_json(complete_goals.to_json())
  
if __name__ == "__main__":
    # Allow running the test file directly
    pytest.main([__file__, "-v", "--tb=short"])
