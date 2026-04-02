from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.atomizer.decomposer import Atomizer

app = FastAPI(title="Legion Atomizer")

# Initialize Atomizer with Librarian URL
LIBRARIAN_URL = os.getenv("LIBRARIAN_URL", "http://localhost:8001")
atomizer = Atomizer(librarian_url=LIBRARIAN_URL)


class DecomposeInput(BaseModel):
    """Input model for task decomposition"""
    spec_id: Optional[str] = None
    project_spec: Optional[dict] = None


class DecomposeResponse(BaseModel):
    """Response model for task decomposition"""
    tasks: list[dict]
    count: int


@app.post("/decompose", response_model=DecomposeResponse)
def decompose_project(data: DecomposeInput):
    """
    Decompose a project specification into atomic tasks.
    
    Accepts either:
    - spec_id: Fetch project spec from Librarian and decompose
    - project_spec: Direct project spec dictionary to decompose
    
    Returns a list of atomic tasks ready for assignment to workers.
    """
    try:
        # Determine source of project spec
        if data.spec_id:
            # Fetch from Librarian
            project_spec = atomizer.fetch_project_spec(data.spec_id)
        elif data.project_spec:
            # Use provided spec
            project_spec = data.project_spec
        else:
            raise HTTPException(
                status_code=400,
                detail="Either spec_id or project_spec must be provided"
            )
        
        # Decompose into tasks
        tasks = atomizer.decompose(project_spec)
        
        return DecomposeResponse(tasks=tasks, count=len(tasks))
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to decompose project: {str(e)}"
        )


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "atomizer"}
