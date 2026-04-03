"""
FastAPI app for the Sea Qwens Tester service.

Endpoints:
- POST /validate       – validate task output, merge if passed, update Librarian
- POST /retry/{task_id} – send task back to Worker for retry
- GET  /health         – health check
"""

import logging
from datetime import datetime
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.tester.validator import ContractValidator, ValidationResult
from services.tester.merger import GitMerger, MergeResult

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sea Qwens Tester",
    description="Validation and merge service for Sea Qwens",
    version="0.1.0",
)

# Collaborators – instantiated lazily for testability
_validator: Optional[ContractValidator] = None
_merger: Optional[GitMerger] = None

# Service URLs (overridable for tests)
_LIBRARIAN_URL = "http://localhost:8001"
_WORKER_URL = "http://localhost:8004"
_REPO_ROOT = "/home/loki/ideas/sea-qwens"


def get_validator() -> ContractValidator:
    global _validator
    if _validator is None:
        _validator = ContractValidator()
    return _validator


def get_merger() -> GitMerger:
    global _merger
    if _merger is None:
        _merger = GitMerger(_REPO_ROOT)
    return _merger


# ─── Request / Response Models ────────────────────────────────────────────────

class ValidateRequest(BaseModel):
    task_id: str
    worktree_path: str
    contract: dict


class ValidateResponse(BaseModel):
    task_id: str
    passed: bool
    contract_valid: bool
    tests_passed: bool
    semantic_valid: bool
    merged: bool = False
    errors: list[str] = []


class RetryRequest(BaseModel):
    worktree_path: str
    contract: dict = {}


class RetryResponse(BaseModel):
    task_id: str
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/validate", response_model=ValidateResponse)
async def validate_task(request: ValidateRequest):
    """
    Validate a completed task:
    1. Run contract + test + semantic validation
    2. If all pass, merge the task branch into main
    3. Update the task status in Librarian (DONE or FAILED)
    """
    task_id = request.task_id
    logger.info(f"Validating task: {task_id}")

    validator = get_validator()
    validation: ValidationResult = validator.validate(
        task_id=task_id,
        worktree_path=request.worktree_path,
        contract=request.contract,
    )

    merged = False

    if validation.passed:
        # Merge the task branch
        merger = get_merger()
        merge_result: MergeResult = merger.merge_task_branch(task_id)

        if merge_result.success:
            merged = True
            # Clean up the task branch
            merger.cleanup_task_branch(task_id)
            # Update Librarian: task is DONE
            _update_librarian_status(task_id, "DONE")
            logger.info(f"Task {task_id} validated and merged")
        else:
            # Merge failed – mark as MANUAL_REVIEW
            validation.errors.append(f"Merge failed: {merge_result.error}")
            _update_librarian_status(task_id, "MANUAL_REVIEW")
            logger.warning(f"Task {task_id} passed validation but merge failed")
    else:
        # Validation failed – mark as FAILED
        _update_librarian_status(task_id, "FAILED")
        logger.warning(f"Task {task_id} failed validation")

    return ValidateResponse(
        task_id=task_id,
        passed=validation.passed,
        contract_valid=validation.contract_valid,
        tests_passed=validation.tests_passed,
        semantic_valid=validation.semantic_valid,
        merged=merged,
        errors=validation.errors,
    )


@app.post("/retry/{task_id}", response_model=RetryResponse)
async def retry_task(task_id: str, request: RetryRequest):
    """
    Send a failed task back to the Worker for another attempt.
    Resets status to PENDING in Librarian and re-dispatches to Worker.
    """
    logger.info(f"Retrying task: {task_id}")

    # Reset status in Librarian
    _update_librarian_status(task_id, "PENDING")

    # Re-dispatch to Worker
    try:
        response = requests.post(
            f"{_WORKER_URL}/execute",
            json={
                "task": {
                    "task_id": task_id,
                    "title": f"Retry: {task_id}",
                    "status": "PENDING",
                    "contract": request.contract,
                },
                "worktree_path": request.worktree_path,
            },
            timeout=10,
        )

        if response.status_code in (200, 202):
            return RetryResponse(
                task_id=task_id,
                status="RETRIED",
                message=f"Task {task_id} sent back to Worker",
            )

        return RetryResponse(
            task_id=task_id,
            status="RETRY_FAILED",
            message=f"Worker rejected retry: {response.text}",
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Worker unreachable for retry: {e}")
        return RetryResponse(
            task_id=task_id,
            status="RETRY_FAILED",
            message=f"Worker unavailable: {str(e)}",
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="sea-qwens-tester",
        timestamp=datetime.utcnow().isoformat(),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _update_librarian_status(task_id: str, status: str) -> None:
    """Update a task's status in the Librarian service (best-effort)."""
    try:
        requests.post(
            f"{_LIBRARIAN_URL}/tasks/update",
            params={"task_id": task_id},
            json={"status": status},
            timeout=5,
        )
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to update Librarian for task {task_id}: {e}")
