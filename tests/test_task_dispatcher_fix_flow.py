# -*- coding: utf-8 -*-
"""
Tests fuer den Fix-Flow im TaskDispatcher.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.task_dispatcher import TaskDispatcher
from backend.task_models import DerivedTask, TaskCategory, TaskPriority, TargetAgent


def _make_dispatcher_with_manager(tmp_path: Path) -> TaskDispatcher:
    manager = MagicMock()
    manager.project_path = str(tmp_path)
    manager.current_code = ""
    manager.claude_provider = object()
    manager._ui_log = MagicMock()
    manager.on_log = None
    tracker = MagicMock()
    tracker._generate_summary.return_value = {}
    return TaskDispatcher(manager=manager, config={}, tracker=tracker, max_parallel=1)


def _make_fix_task(affected_files):
    return DerivedTask(
        id="TASK-001",
        title="Fix Task",
        description="Behebe den Fehler in der Datei.",
        category=TaskCategory.CODE,
        priority=TaskPriority.HIGH,
        target_agent=TargetAgent.FIX,
        affected_files=affected_files,
        dependencies=[],
        source_issue="Serverstart-Problem in next.config.js",
        source_type="sandbox",
    )


def test_execute_single_task_fix_fails_without_resolvable_target_file(tmp_path):
    dispatcher = _make_dispatcher_with_manager(tmp_path)
    task = _make_fix_task([])

    with patch.object(dispatcher, "_get_agent_for_task", return_value=MagicMock()):
        result = dispatcher._execute_single_task(task)

    assert result.success is False
    assert "Zieldatei" in result.error_message
    dispatcher.shutdown()


def test_execute_single_task_fix_writes_corrected_file(tmp_path):
    dispatcher = _make_dispatcher_with_manager(tmp_path)
    target = tmp_path / "next.config.js"
    target.write_text("module.exports = {};\n", encoding="utf-8")
    task = _make_fix_task(["next.config.js"])

    sdk_output = """### CORRECTION: next.config.js
```javascript
module.exports = {
  serverExternalPackages: ['sqlite3'],
};
```
"""

    with patch.object(dispatcher, "_get_agent_for_task", return_value=MagicMock()), \
         patch("backend.claude_sdk.run_sdk_with_retry", return_value=sdk_output):
        result = dispatcher._execute_single_task(task)

    assert result.success is True
    assert result.modified_files == ["next.config.js"]
    content = target.read_text(encoding="utf-8")
    assert "serverExternalPackages" in content
    dispatcher.shutdown()


def test_execute_single_task_fix_fails_when_file_write_validation_fails(tmp_path):
    dispatcher = _make_dispatcher_with_manager(tmp_path)
    target = tmp_path / "next.config.js"
    target.write_text("module.exports = {};\n", encoding="utf-8")
    task = _make_fix_task(["next.config.js"])

    sdk_output = """### CORRECTION: next.config.js
```javascript
module.exports = { reactStrictMode: true };
```
"""

    with patch.object(dispatcher, "_get_agent_for_task", return_value=MagicMock()), \
         patch("backend.claude_sdk.run_sdk_with_retry", return_value=sdk_output), \
         patch.object(dispatcher, "_write_file_to_project", return_value=False):
        result = dispatcher._execute_single_task(task)

    assert result.success is False
    assert "Synchronisierung fehlgeschlagen" in result.error_message
    dispatcher.shutdown()


def test_execute_single_task_fix_fails_when_manager_sync_fails(tmp_path):
    dispatcher = _make_dispatcher_with_manager(tmp_path)
    target = tmp_path / "next.config.js"
    target.write_text("module.exports = {};\n", encoding="utf-8")
    task = _make_fix_task(["next.config.js"])

    sdk_output = """### CORRECTION: next.config.js
```javascript
module.exports = { reactStrictMode: true };
```
"""

    with patch.object(dispatcher, "_get_agent_for_task", return_value=MagicMock()), \
         patch("backend.claude_sdk.run_sdk_with_retry", return_value=sdk_output), \
         patch.object(dispatcher, "_sync_single_file_to_manager", return_value=False):
        result = dispatcher._execute_single_task(task)

    assert result.success is False
    assert "Synchronisierung fehlgeschlagen" in result.error_message
    dispatcher.shutdown()
