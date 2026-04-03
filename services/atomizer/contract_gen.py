"""Contract generator for Sea Qwens Atomizer service.

Generates JSON Schema contracts for API endpoints, functions, and files.
"""

from typing import Any, Optional


def generate_api_contract(
    endpoint: str,
    method: str = "GET",
    request_schema: Optional[dict] = None,
    response_schema: Optional[dict] = None
) -> dict:
    """Generate a JSON Schema contract for an API endpoint.
    
    Args:
        endpoint: The API endpoint path (e.g., "/api/users")
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        request_schema: Optional JSON Schema for request body
        response_schema: Optional JSON Schema for response body
        
    Returns:
        A dictionary containing the API contract
    """
    return {
        "type": "api",
        "endpoint": endpoint,
        "method": method,
        "request": request_schema or {"type": "object"},
        "response": response_schema or {"type": "object"},
        "validation_rules": {
            "status_codes": [200, 201, 400, 404, 500],
            "content_type": "application/json"
        }
    }


def generate_function_contract(
    name: str,
    params: list[str],
    return_type: str,
    description: str = ""
) -> dict:
    """Generate a contract for a function signature.
    
    Args:
        name: The function name
        params: List of parameter names
        return_type: The return type as a string
        description: Optional description of what the function does
        
    Returns:
        A dictionary containing the function contract
    """
    return {
        "type": "function",
        "function_name": name,
        "parameters": params,
        "return_type": return_type,
        "description": description,
        "validation_rules": {
            "param_count": len(params),
            "pure_function": True
        }
    }


def generate_file_contract(
    filepath: str,
    expected_content: Optional[str] = None,
    must_exist: bool = True
) -> dict:
    """Generate a contract for file existence/content.
    
    Args:
        filepath: The path to the file
        expected_content: Optional expected content pattern
        must_exist: Whether the file must exist (default True)
        
    Returns:
        A dictionary containing the file contract
    """
    return {
        "type": "file",
        "filepath": filepath,
        "must_exist": must_exist,
        "expected_content_pattern": expected_content
    }


def validate_contract(contract: dict, data: Any) -> tuple[bool, list[str]]:
    """Validate data against a contract.
    
    Args:
        contract: The contract dictionary to validate against
        data: The data to validate
        
    Returns:
        A tuple of (is_valid, errors) where:
        - is_valid: Boolean indicating if validation passed
        - errors: List of error messages (empty if valid)
    """
    errors = []

    if contract.get("type") == "object":
        required = contract.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        properties = contract.get("properties", {})
        for key, value in data.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get("type")
                if expected_type:
                    # Map JSON Schema types to Python types
                    type_mapping = {
                        "str": str,
                        "string": str,
                        "int": int,
                        "integer": int,
                        "float": float,
                        "bool": bool,
                        "boolean": bool,
                        "list": list,
                        "array": list,
                        "dict": dict,
                        "object": dict,
                        "None": type(None),
                        "null": type(None)
                    }
                    expected_python_type = type_mapping.get(expected_type)
                    if expected_python_type and not isinstance(value, expected_python_type):
                        errors.append(f"Field '{key}' has wrong type")

    return len(errors) == 0, errors
