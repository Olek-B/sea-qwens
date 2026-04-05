import uuid
import json
import re
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from shared.code_query_tools import ProjectCodeContext, CodeQueryTools
except ImportError:
    ProjectCodeContext = None
    CodeQueryTools = None


# Entity name extraction patterns
_ENTITY_PATTERNS = [
    (r'(\w+)\s+catalog', 'Product'),
    (r'shopping\s+cart', 'Cart'),
    (r'checkout', 'Order'),
    (r'user\s+(?:auth|login|register)', 'User'),
    (r'order\s+(?:management|processing|creation)', 'Order'),
    (r'(\w+)\s+management', r'\1'),
]

# Operation extraction
_OP_MAP = {
    'crud': ['create', 'read', 'update', 'delete'],
    'add/remove': ['add', 'remove', 'view'],
    'creation': ['create'],
    'list': ['list', 'view'],
    'search': ['search', 'filter'],
}


def generate_task_id() -> str:
    """Generate a unique task identifier using UUID4"""
    return str(uuid.uuid4())


class Atomizer:
    """
    Atomizer service for decomposing project specifications into atomic tasks.

    Acts as a technical lead: generates detailed contracts specifying
    endpoints, models, file structure, and validation rules that workers must follow.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def decompose(self, project_spec: dict) -> list[dict]:
        """Decompose a project specification into atomic tasks."""
        code_context = self._load_code_context(project_spec)
        return self._mock_decompose(project_spec, code_context)

    def _load_code_context(self, project_spec: dict):
        """Load code context for the project if available."""
        if ProjectCodeContext is None:
            return None
        try:
            tools = CodeQueryTools(self.librarian_url)
            ctx = ProjectCodeContext(tools)
            overview = ctx.get_project_overview(project_spec.get("name", ""))
            if overview:
                return ctx
        except Exception as e:
            logger.warning(f"Failed to load code context: {e}")
        return None

    def _parse_feature_description(self, feature: str) -> dict:
        """Parse feature description to extract entity and operations.
        
        Examples:
            "Product catalog with CRUD endpoints" -> entity="Product", ops=["create","read","update","delete"]
            "Shopping cart with add/remove items" -> entity="Cart", ops=["add","remove","view"]
            "User checkout with order creation" -> entity="Order", ops=["create"]
        """
        feature_lower = feature.lower()

        # Extract entity name
        entity = None
        for pattern, replacement in _ENTITY_PATTERNS:
            match = re.search(pattern, feature_lower)
            if match:
                if replacement.startswith('\\'):
                    entity = re.sub(pattern, replacement, feature_lower, flags=re.IGNORECASE)
                    entity = entity.title()
                else:
                    entity = replacement
                break

        if not entity:
            # Fallback: use first significant word
            words = [w for w in feature.split() if len(w) > 3]
            entity = words[0].title() if words else "Feature"

        # Extract operations
        operations = []
        for keyword, ops in _OP_MAP.items():
            if keyword in feature_lower:
                operations.extend(ops)

        if not operations:
            if 'crud' in feature_lower:
                operations = ['create', 'read', 'update', 'delete']
            else:
                operations = ['create', 'read', 'update', 'delete']  # Default to full CRUD

        return {
            "entity": entity,
            "operations": list(dict.fromkeys(operations)),  # Dedupe preserving order
            "raw": feature
        }

    def _build_setup_contract(self, project_name: str, tech_stack: list[str]) -> dict:
        """Build detailed setup contract with file structure and dependencies."""
        return {
            "type": "setup",
            "project_name": project_name,
            "tech_stack": tech_stack,
            "structure": {
                "files": [
                    {"path": "main.py", "description": "FastAPI application entry point with lifespan"},
                    {"path": "models.py", "description": "Pydantic models and SQLAlchemy/aiosqlite schemas"},
                    {"path": "requirements.txt", "description": "Python package dependencies"},
                    {"path": ".env.example", "description": "Environment variable template"}
                ],
                "directories": ["tests/"]
            },
            "dependencies": {
                "required": ["fastapi", "uvicorn[standard]", "pydantic>=2.0"],
                "optional": ["aiosqlite", "httpx", "pytest", "pytest-asyncio"]
            },
            "requirements": [
                "Use async/await for all database operations",
                "Use FastAPI lifespan for database connection setup",
                "Create a requirements.txt with pinned dependencies",
                "Follow Python 3.11+ conventions"
            ]
        }

    def _build_model_spec(self, entity: str, operations: list[str]) -> dict:
        """Generate data model specification for an entity."""
        entity_lower = entity.lower()

        # Predefined model schemas for common entities
        model_schemas = {
            "product": {
                "fields": [
                    {"name": "id", "type": "int", "constraints": "PRIMARY KEY AUTOINCREMENT"},
                    {"name": "name", "type": "str", "constraints": "NOT NULL, max 255 chars"},
                    {"name": "description", "type": "str", "constraints": "TEXT, optional"},
                    {"name": "price", "type": "float", "constraints": "NOT NULL, > 0"},
                    {"name": "stock", "type": "int", "constraints": "DEFAULT 0, >= 0"}
                ],
                "pydantic_validators": [
                    "Field(..., min_length=1, max_length=255) for name",
                    "Field(..., gt=0) for price",
                    "Field(default=0, ge=0) for stock"
                ]
            },
            "cart": {
                "fields": [
                    {"name": "id", "type": "int", "constraints": "PRIMARY KEY AUTOINCREMENT"},
                    {"name": "user_id", "type": "str", "constraints": "NOT NULL, indexed"},
                    {"name": "product_id", "type": "int", "constraints": "NOT NULL, FK->products(id)"},
                    {"name": "quantity", "type": "int", "constraints": "DEFAULT 1, >= 1"}
                ],
                "pydantic_validators": [
                    "Field(..., min_length=1) for user_id",
                    "Field(default=1, ge=1) for quantity"
                ]
            },
            "order": {
                "fields": [
                    {"name": "id", "type": "int", "constraints": "PRIMARY KEY AUTOINCREMENT"},
                    {"name": "user_id", "type": "str", "constraints": "NOT NULL, indexed"},
                    {"name": "total", "type": "float", "constraints": "NOT NULL, >= 0"},
                    {"name": "status", "type": "str", "constraints": "DEFAULT 'pending'"},
                    {"name": "created_at", "type": "datetime", "constraints": "DEFAULT CURRENT_TIMESTAMP"}
                ],
                "pydantic_validators": [
                    "Field(..., min_length=1) for user_id",
                    "Field(..., ge=0) for total",
                    "Field(default='pending') for status"
                ]
            },
            "user": {
                "fields": [
                    {"name": "id", "type": "int", "constraints": "PRIMARY KEY AUTOINCREMENT"},
                    {"name": "username", "type": "str", "constraints": "NOT NULL, UNIQUE, max 150"},
                    {"name": "email", "type": "str", "constraints": "NOT NULL, UNIQUE, valid email"},
                    {"name": "hashed_password", "type": "str", "constraints": "NOT NULL"}
                ],
                "pydantic_validators": [
                    "Field(..., min_length=3, max_length=150) for username",
                    "Field(..., pattern=r'^[\\w.+-]+@[\\w-]+\\.[\\w.-]+$') for email",
                    "Field(..., min_length=8) for password (input model only)"
                ]
            }
        }

        return model_schemas.get(entity_lower, {
            "fields": [
                {"name": "id", "type": "int", "constraints": "PRIMARY KEY AUTOINCREMENT"},
                {"name": "name", "type": "str", "constraints": "NOT NULL"}
            ],
            "pydantic_validators": ["Add validators as needed"]
        })

    def _build_endpoint_spec(self, entity: str, operations: list[str]) -> list[dict]:
        """Generate REST endpoint specifications."""
        entity_lower = entity.lower()
        path = f"/{entity_lower}s" if not entity_lower.endswith('s') else f"/{entity_lower}"
        single_path = f"{path}/{{{entity_lower}_id}}"

        endpoints = []

        if 'read' in operations:
            endpoints.append({
                "method": "GET",
                "path": path,
                "description": f"List all {entity_lower}s",
                "response": f"List[{entity}]",
                "status": 200
            })
            endpoints.append({
                "method": "GET",
                "path": single_path,
                "description": f"Get single {entity_lower} by ID",
                "response": entity,
                "status": 200,
                "errors": [{"status": 404, "condition": "not found"}]
            })

        if 'create' in operations:
            endpoints.append({
                "method": "POST",
                "path": path,
                "description": f"Create new {entity_lower}",
                "request": f"{entity}Create",
                "response": entity,
                "status": 201,
                "errors": [{"status": 422, "condition": "validation error"}]
            })

        if 'update' in operations:
            endpoints.append({
                "method": "PUT",
                "path": single_path,
                "description": f"Update {entity_lower}",
                "request": f"{entity}Update",
                "response": entity,
                "status": 200,
                "errors": [{"status": 404, "condition": "not found"}]
            })

        if 'delete' in operations:
            endpoints.append({
                "method": "DELETE",
                "path": single_path,
                "description": f"Delete {entity_lower}",
                "status": 204,
                "errors": [{"status": 404, "condition": "not found"}]
            })

        # Special operations
        if 'add' in operations and entity_lower == 'cart':
            endpoints.append({
                "method": "POST",
                "path": f"/cart/items",
                "description": "Add item to cart",
                "request": "CartItemAdd",
                "response": "CartItem",
                "status": 201
            })
            endpoints.append({
                "method": "DELETE",
                "path": f"/cart/items/{{product_id}}",
                "description": "Remove item from cart",
                "status": 204
            })

        if 'create' in operations and entity_lower == 'order':
            endpoints.append({
                "method": "POST",
                "path": "/orders",
                "description": "Create order from current cart (checkout)",
                "request": "OrderCreate",
                "response": "Order",
                "status": 201
            })
            endpoints.append({
                "method": "GET",
                "path": "/orders/{order_id}",
                "description": "Get order details with line items",
                "response": "OrderDetail",
                "status": 200
            })

        return endpoints

    def _build_feature_contract(self, feature: str, tech_stack: list[str], existing_matches: list = None) -> dict:
        """Build detailed feature implementation contract."""
        parsed = self._parse_feature_description(feature)
        entity = parsed["entity"]
        operations = parsed["operations"]

        model_spec = self._build_model_spec(entity, operations)
        endpoints = self._build_endpoint_spec(entity, operations)

        # Determine which files to create/modify
        files_to_create = [
            {"path": "models.py", "content": f"{entity} Pydantic models with validation"},
        ]

        # Check if main.py already exists (from setup task context)
        files_to_create.append({
            "path": "main.py",
            "content": f"REST endpoints for {entity} at {endpoints[0]['path'] if endpoints else '/entity'}"
        })

        contract = {
            "type": "feature",
            "feature": feature,
            "tech_stack": tech_stack,
            "entity": entity,
            "operations": operations,
            "endpoints": endpoints,
            "models": {
                entity: model_spec
            },
            "files_to_create": files_to_create,
            "implementation_notes": [
                f"Use aiosqlite for async SQLite operations",
                f"Return proper HTTP status codes (201 for POST, 204 for DELETE)",
                f"Use HTTPException with detail for errors",
                f"Add response_model to all endpoint decorators"
            ]
        }

        if existing_matches:
            contract["type"] = "extend_feature"
            contract["existing_code"] = existing_matches
            contract["implementation_notes"].insert(0, "Extend existing code, do not replace")

        return contract

    def _build_integration_contract(self, project_name: str, feature_tasks: list[dict]) -> dict:
        """Build integration test contract."""
        # Extract entities from feature tasks to build cross-entity tests
        tests = []
        for ft in feature_tasks:
            contract = ft.get("contract", {})
            entity = contract.get("entity", "unknown")
            endpoints = contract.get("endpoints", [])

            if endpoints:
                # Create basic endpoint test
                first_ep = endpoints[0]
                tests.append(f"Test {first_ep['method']} {first_ep['path']} returns expected status")

        # Cross-entity integration tests
        tests.extend([
            "Create entity A, then create entity B that references A",
            "Full workflow: create → read → update → delete",
            "Error handling: 404 for non-existent resources",
            "Validation: 422 for invalid input data"
        ])

        return {
            "type": "integration",
            "project_name": project_name,
            "tests": tests,
            "test_files": [
                {"path": "tests/test_api.py", "description": "Integration tests for all endpoints"}
            ],
            "requirements": [
                "Use pytest with pytest-asyncio for async tests",
                "Use httpx.AsyncClient for FastAPI testing",
                "Use fresh database for each test",
                "Test both success and error paths"
            ]
        }

    def _mock_decompose(self, project_spec: dict, code_context=None) -> list[dict]:
        """
        Decompose project spec into detailed, contract-specified tasks.

        Each task contract includes exact endpoints, model definitions,
        file structure, and validation rules that workers must follow.
        """
        tasks = []
        project_name = project_spec.get("name", "Unknown Project")
        tech_stack = project_spec.get("tech_stack", [])
        features = project_spec.get("features", [])

        existing_features = {}
        if code_context:
            existing_features = code_context.find_existing_features(project_name, features)

        # Task 1: Project Setup
        setup_task = {
            "task_id": generate_task_id(),
            "title": f"Setup project structure for {project_name}",
            "status": "PENDING",
            "dependencies": [],
            "contract": self._build_setup_contract(project_name, tech_stack)
        }
        tasks.append(setup_task)
        setup_task_id = setup_task["task_id"]

        # Feature tasks
        feature_task_ids = []
        for feature in features:
            feature_info = existing_features.get(feature, {})
            existing_matches = feature_info.get("matches", []) if feature_info.get("found") else None

            feature_task = {
                "task_id": generate_task_id(),
                "title": f"Extend existing {feature}" if existing_matches else f"Implement feature: {feature}",
                "status": "PENDING",
                "dependencies": [setup_task_id],
                "contract": self._build_feature_contract(feature, tech_stack, existing_matches)
            }
            tasks.append(feature_task)
            feature_task_ids.append(feature_task["task_id"])

        # Integration task
        if len(features) > 1:
            feature_contracts = [t for t in tasks if t["contract"]["type"] in ("feature", "extend_feature")]
            integration_task = {
                "task_id": generate_task_id(),
                "title": f"Integration testing for {project_name}",
                "status": "PENDING",
                "dependencies": feature_task_ids,
                "contract": self._build_integration_contract(project_name, feature_contracts)
            }
            tasks.append(integration_task)

        return tasks

    def fetch_project_spec(self, spec_id: str) -> dict:
        """Fetch a project specification from the Librarian service."""
        url = f"{self.librarian_url}/project-specs/{spec_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def save_tasks(self, tasks: list[dict], output_path: str) -> None:
        """Save decomposed tasks to a JSON file."""
        with open(output_path, 'w') as f:
            json.dump(tasks, f, indent=2)
