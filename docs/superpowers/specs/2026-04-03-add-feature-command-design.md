# Add Feature Command — Design Spec

**Date:** 2026-04-03  
**Status:** Draft

## Problem

The current Sea Qwens CLI only supports `interview` — a full interview for creating a new project from scratch. There is no way to add a new feature to an existing project that has already been imported into the system.

## Goal

Add an `add-feature` command to the Manager CLI that lets users select an existing project, describe a new feature, and go through an adaptive interview that asks only the clarifying questions needed — with full awareness of the existing codebase.

## Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│  CLI: python -m services.manager.cli add-feature │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. GET /projects → list existing projects      │
│  2. User selects project (numbered list)        │
│  3. Load code context via CodeQueryTools        │
│  4. User describes the new feature              │
│  5. LLM analyzes: description + code context    │
│     → returns clarifying questions or "ready"   │
│  6. Ask follow-ups one at a time (no limit)     │
│  7. After each round, re-check with LLM         │
│  8. Build ProjectSpec with parent_project ref   │
│  9. POST to Librarian /project-specs            │
│                                                 │
└─────────────────────────────────────────────────┘
```

### New Files

| File | Purpose |
|------|---------|
| `services/manager/feature_interviewer.py` | `FeatureInterviewer` class — adaptive interview flow |
| `services/manager/tests/test_feature_interviewer.py` | Tests for FeatureInterviewer |

### Modified Files

| File | Change |
|------|--------|
| `services/manager/cli.py` | Add `@cli.command() def add_feature()` |
| `shared/models.py` | Add `parent_project: Optional[str] = None` to ProjectSpec |
| `services/librarian/app.py` | Add `GET /projects` endpoint |
| `services/librarian/neo4j_store.py` | Add `list_all_projects()` method |

## Data Flow

### 1. Project Selection

- CLI calls `GET /projects` on the Librarian.
- Librarian queries Neo4j for all stored project specs.
- Returns a list of `{id, name, tech_stack, features}`.
- CLI displays a numbered list. User picks one.

### 2. Code Context Loading

- CLI initializes `CodeQueryTools` and calls `get_project_overview(selected_project_name)`.
- Returns summary: file count, function count, class count, module structure.
- This context is passed to the LLM alongside the feature description.

### 3. Feature Description

- CLI prompts: "Describe the feature you want to add to {project_name}:"
- User provides a free-form description.

### 4. LLM-Driven Clarifying Questions

- The `FeatureInterviewer` sends a prompt to the LLM containing:
  - The existing project's code overview
  - The user's feature description
  - All accumulated Q&A so far (after the first round)
- The LLM responds with either:
  - `"READY"` — the spec is clear, no more questions needed
  - A list of clarifying questions (as many as needed)
- Questions are asked one at a time via `click.prompt()`.
- After each answer, the LLM is re-queried with the full context to determine if more questions are needed.
- **No limit on the number of rounds** — the loop continues until the LLM returns `"READY"`.

### 5. Spec Construction

- The `FeatureInterviewer.build_spec()` method constructs a `ProjectSpec` dict:
  - `name`: derived from the parent project name + feature name (e.g., `"myapp-add-auth"`)
  - `parent_project`: the ID or name of the existing project
  - `tech_stack`: inherited from the parent project, unless the user specified additions
  - `features`: the new feature(s) described
  - `constraints`: any constraints mentioned during the interview

### 6. Spec Submission

- The CLI displays the extracted spec.
- User confirms or cancels.
- On confirm, POST to `Librarian /project-specs`.

## LLM Integration

The LLM prompt template:

```
You are conducting a requirements interview for adding a feature to an existing software project.

EXISTING PROJECT:
{code_overview}

FEATURE DESCRIPTION:
{feature_description}

{PREVIOUS_Q_AND_A}

Based on the above, is the feature description clear enough to create a detailed project spec?

If YES, respond with exactly: READY

If NO, list the specific clarifying questions you need answered. Ask at most 5 questions per round.
Focus on: what the feature does, how it interacts with existing code, technical requirements,
constraints, and edge cases. Do NOT ask about things that are already covered in the description
or that are clearly present in the existing code.

Return your response as JSON:
- If ready: "READY"
- If questions needed: ["question 1", "question 2", ...]
```

The LLM is called via the same mechanism the existing `Interviewer` uses. If no LLM is available, fall back to a fixed set of 3 generic follow-up questions (requirements, constraints, success criteria).

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No projects in database | Display message: "No existing projects found. Run `interview` first to create a project." |
| Project not found by name | Display error, re-prompt for selection |
| Code context unavailable | Proceed with interview but warn user that questions won't be code-aware |
| LLM unavailable | Fall back to fixed follow-up questions, warn user |
| Librarian connection failed | Display error, show spec as JSON for manual submission |
| User cancels at any point | Exit cleanly with "Interview cancelled. No data sent." |

## Testing

- **Unit tests** for `FeatureInterviewer`:
  - `test_list_projects` — mocks Librarian response
  - `test_load_project_context` — mocks CodeQueryTools
  - `test_generate_questions_ready` — LLM returns READY immediately
  - `test_generate_questions_with_questions` — LLM returns questions, loop terminates after follow-ups
  - `test_build_spec` — verifies spec dict structure with parent_project
  - `test_build_spec_inherits_tech_stack` — verifies tech_stack inheritance
- **CLI tests**:
  - `test_add_feature_no_projects` — handles empty project list
  - `test_add_feature_happy_path` — full flow with mocked LLM
  - `test_add_feature_cancel` — user cancels
- **Librarian tests**:
  - `test_list_projects_endpoint` — GET /projects returns all specs

## API Changes

### New Librarian Endpoint

```
GET /projects

Response: 200 OK
[
  {
    "id": "spec-uuid-1",
    "name": "myapp",
    "tech_stack": ["FastAPI", "React", "PostgreSQL"],
    "features": ["user auth", "dashboard"]
  },
  ...
]
```

### ProjectSpec Model Change

```python
class ProjectSpec(BaseModel):
    id: Optional[str] = None
    name: str
    tech_stack: list[str] = []
    features: list[str] = []
    constraints: list[str] = []
    parent_project: Optional[str] = None  # NEW: ID/name of project being extended
```

## Alternatives Considered

1. **Extend existing Interviewer class** — rejected due to tight coupling with fixed-question flow.
2. **Standalone FeatureInterviewer without LLM** — rejected because fixed questions don't adapt to the feature or existing code.
3. **Append features to existing ProjectSpec** — rejected; creating a new spec with a parent reference is cleaner for the Atomizer to decompose independently.
