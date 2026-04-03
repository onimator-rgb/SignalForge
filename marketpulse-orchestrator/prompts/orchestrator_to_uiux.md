# Orchestrator → UI/UX Agent Communication Protocol

## When to Dispatch

The Orchestrator dispatches to the UI/UX Agent when:
- A roadmap feature requires frontend UI changes
- A periodic UI quality audit is requested
- The Orchestrator detects accumulated frontend technical debt
- A new frontend view or major component is being planned

## Dispatch Format

The Orchestrator sends a task_spec with:

```json
{
  "task_id": "marketpulse-task-YYYYMMDD-NNNN",
  "task_type": "ui_ux_analysis",
  "target_repo": "https://github.com/onimator-rgb/SignalForge",
  "scope": "full" | "partial",
  "focus_areas": ["dashboard", "navigation", "data-tables"],
  "context": "Reason for requesting analysis",
  "constraints": {
    "max_analysis_time_minutes": 15,
    "output_format": "handoff_for_coder"
  }
}
```

## Expected Response

The UI/UX Agent returns:

```json
{
  "agent": "uiux_worker",
  "task_type": "ui_ux_analysis",
  "repo_analyzed": "https://github.com/...",
  "files_collected": 42,
  "report_path": "reports/uiux/uiux_analysis_<timestamp>.md",
  "handoff_path": "reports/uiux/signalforge_uiux_handoff_for_coding_agent.txt",
  "handoff_filename": "signalforge_uiux_handoff_for_coding_agent.txt",
  "duration_seconds": 120.5,
  "status": "completed" | "error",
  "error": null | "error description",
  "timestamp": "ISO8601",
  "next_recommended_step": "dispatch_to_coder" | "ask_human"
}
```

## Orchestrator Behavior After Response

- If `status == "completed"` and `next_recommended_step == "dispatch_to_coder"`:
  → Include the handoff document path in the next Coder task_spec
  → The Coder should read the handoff file and implement changes

- If `status == "error"`:
  → Log the error
  → If retries < max_retries: retry
  → Else: mark as failed, continue to next task

## Chaining: UI/UX → Coder Pipeline

When UI/UX analysis feeds into Coder work:

1. Orchestrator dispatches to UI/UX Agent
2. UI/UX Agent produces handoff document
3. Orchestrator creates a new task_spec for Coder with:
   ```json
   {
     "task_id": "...",
     "title": "Implement UI/UX improvements from analysis",
     "description": "Follow the handoff document at <handoff_path>",
     "subtasks": [
       {
         "id": "s1",
         "title": "Read and implement UI/UX handoff",
         "description": "Read the file at <handoff_path> and implement all P1 changes in order",
         "files_expected": ["frontend/src/..."]
       }
     ],
     "uiux_handoff_path": "<handoff_path>"
   }
   ```
4. Coder implements changes per the handoff
5. Validator verifies implementation

## Security Notes

- UI/UX Agent is **read-only** — it never modifies the target repo
- It only writes to `reports/uiux/` directory
- No API keys, secrets, or credentials are accessed
- No external services called (except git clone)
