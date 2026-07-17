from src.orchestrator.master_orchestrator import MasterOrchestrator


def test_master_orchestrator_status_exposes_current_targets() -> None:
    status = MasterOrchestrator().get_system_status()

    assert status["version"] == "2.0"
    assert status["available_subsystems"]["complete_runner"] is True
    assert status["available_subsystems"]["dashboard"] is True


def test_master_orchestrator_data_only_command_uses_current_runner() -> None:
    orchestrator = MasterOrchestrator()
    command = orchestrator._complete_runner_command(quick=True, data_only=True, proof_level="none")

    assert command[:2][-1] == "scripts/run_complete_v3_system.py"
    assert "--quick" in command
    assert "--data-only" in command
    assert "--proof-level" in command
