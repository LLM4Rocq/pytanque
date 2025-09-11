"""
Integration tests for Pytanque - testing complete workflows and feedback integration.

These tests focus on testing complete workflows and cross-method integration.
"""

import pytest
import logging

from pytanque import Pytanque, PetanqueError, InspectPhysical, InspectGoals


class TestFeedbackIntegration:
    """Test feedback field integration across methods."""

    def test_feedback_command_outputs(
        self, server_config, example_files, petanque_server
    ):
        """Test that feedback captures command outputs correctly."""
        with Pytanque("127.0.0.1", 8765) as client:
            state = client.start("./examples/foo.v", "addnC")

            # Execute various commands and check feedback
            commands = ["Search nat.", "Print nat.", "Check nat.", "induction n."]

            for cmd in commands:
                state = client.run(state, cmd)
                print(f"Command '{cmd}' feedback:")
                for level, msg in state.feedback:
                    print(f"  Level {level}: {msg[:100]}...")  # Truncate long messages
                    assert isinstance(level, int)
                    assert isinstance(msg, str)
                    assert len(msg) > 0  # Should have non-empty messages


class TestIntegratedWorkflow:
    """Test complete workflow examples."""

    def test_complete_workflow(self, server_config, petanque_server):
        """Test a complete proof workflow."""
        # Enable logging as shown in examples
        logging.basicConfig()
        logging.getLogger("pytanque.client").setLevel(logging.INFO)

        try:
            with Pytanque("127.0.0.1", 8765) as client:
                # Set workspace
                client.set_workspace(debug=False, dir="./examples/")

                # Get file contents
                toc = client.toc("./examples/foo.v")
                print(f"File contains: {[name for name, _ in toc]}")

                # Start proof
                state = client.start("./examples/foo.v", "addnC")
                print(f"Started proof, state: {state.st}")

                # Get initial goals
                goals = client.goals(state)
                print(f"Initial goals: {len(goals)}")

                # Execute tactics step by step
                state = client.run(state, "induction n.", verbose=True)
                state = client.run(state, "simpl.", verbose=True)

                # Check if proof is complete
                if state.proof_finished:
                    print("Proof completed!")
                else:
                    remaining_goals = client.goals(state)
                    print(f"Proof in progress, {len(remaining_goals)} goals remaining")

                # Get premises
                premises = client.premises(state)
                print(f"Available premises: {len(premises)}")

                # Skip state comparison due to serialization issues
                state2 = client.run(state, "simpl.")
                state3 = client.run(state2, "idtac.")
                p_equal = client.state_equal(state2, state3, InspectPhysical)
                g_equal = client.state_equal(state2, state3, InspectGoals)
                print(f"States equal: Physical: {p_equal}, Goals: {g_equal}")

                # Get state hash
                hash_val = client.state_hash(state)
                print(f"State hash: {hash_val}")

                # All assertions
                assert isinstance(toc, list)
                assert state.st is not None
                assert isinstance(goals, list)
                assert isinstance(state.proof_finished, bool)
                assert isinstance(premises, list)
                assert (p_equal == False)
                assert (g_equal == True)
                assert isinstance(hash_val, int)

        except PetanqueError as e:
            print(f"Petanque error: {e.message} (code: {e.code})")
            # Re-raise to fail the test if this is unexpected
            raise
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

    def test_complete_workflow_with_ast_and_feedback(
        self, server_config, example_files, petanque_server
    ):
        """Test complete workflow using all new features."""
        with Pytanque("127.0.0.1", 8765) as client:
            # Get root state with feedback
            root_state = client.get_root_state("./examples/foo.v")
            print(f"Root state: {root_state.st}")
            print(f"Root feedback messages: {len(root_state.feedback)}")

            # Get state at specific position
            pos_state = client.get_state_at_pos("./examples/foo.v", line=1, character=0)
            print(f"Position state: {pos_state.st}")

            # Start proof and use run method with feedback
            state = client.start("./examples/foo.v", "addnC")
            print(f"Initial proof state feedback: {len(state.feedback)}")

            # Execute command with run method
            state = client.run(state, "induction n.", verbose=True)
            print(f"After induction feedback: {len(state.feedback)}")

            # Get AST of next command
            ast = client.ast(state, "auto.")
            print(f"AST structure: {type(ast)}")

            # Get AST at file position
            file_ast = client.ast_at_pos("./examples/foo.v", line=2, character=0)
            print(f"File AST: {type(file_ast)}")

            # Execute search with run method and inspect feedback
            search_state = client.run(state, "Search (_ + _).")
            search_feedback = [
                msg
                for level, msg in search_state.feedback
                if "Search" in msg or "+" in msg
            ]
            print(f"Search feedback entries: {len(search_feedback)}")

            # Verify all operations returned valid results
            assert root_state.st is not None
            assert pos_state.st is not None
            assert state.st is not None
            assert isinstance(ast, dict)
            assert isinstance(file_ast, dict)
            assert isinstance(search_state.feedback, list)


if __name__ == "__main__":
    # Allow running the test file directly
    pytest.main([__file__, "-v", "--tb=short"])
