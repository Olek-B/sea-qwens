import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.atomizer.contract_gen import (
    generate_api_contract,
    generate_function_contract,
    generate_file_contract,
    validate_contract
)


class TestGenerateApiContract:
    """Tests for generate_api_contract function"""

    def test_generates_basic_api_contract(self):
        """Test that generate_api_contract creates a basic API contract"""
        contract = generate_api_contract(
            endpoint="/api/users",
            method="GET"
        )
        assert contract["type"] == "api"
        assert contract["endpoint"] == "/api/users"
        assert contract["method"] == "GET"

    def test_generates_api_contract_with_request_schema(self):
        """Test API contract generation with request schema"""
        request_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"}
            }
        }
        contract = generate_api_contract(
            endpoint="/api/users",
            method="POST",
            request_schema=request_schema
        )
        assert contract["request"] == request_schema

    def test_generates_api_contract_with_response_schema(self):
        """Test API contract generation with response schema"""
        response_schema = {
            "type": "array",
            "items": {"type": "object"}
        }
        contract = generate_api_contract(
            endpoint="/api/users",
            method="GET",
            response_schema=response_schema
        )
        assert contract["response"] == response_schema

    def test_generates_api_contract_with_both_schemas(self):
        """Test API contract generation with both request and response schemas"""
        request_schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        response_schema = {"type": "object", "properties": {"success": {"type": "boolean"}}}
        
        contract = generate_api_contract(
            endpoint="/api/users/update",
            method="PUT",
            request_schema=request_schema,
            response_schema=response_schema
        )
        assert contract["request"] == request_schema
        assert contract["response"] == response_schema

    def test_default_request_schema_is_empty_object(self):
        """Test that default request schema is empty object when not provided"""
        contract = generate_api_contract(
            endpoint="/api/health",
            method="GET"
        )
        assert contract["request"] == {"type": "object"}

    def test_default_response_schema_is_empty_object(self):
        """Test that default response schema is empty object when not provided"""
        contract = generate_api_contract(
            endpoint="/api/health",
            method="GET"
        )
        assert contract["response"] == {"type": "object"}

    def test_includes_validation_rules(self):
        """Test that API contract includes validation rules"""
        contract = generate_api_contract(
            endpoint="/api/users",
            method="GET"
        )
        assert "validation_rules" in contract
        assert "status_codes" in contract["validation_rules"]
        assert contract["validation_rules"]["content_type"] == "application/json"


class TestGenerateFunctionContract:
    """Tests for generate_function_contract function"""

    def test_generates_basic_function_contract(self):
        """Test that generate_function_contract creates a basic function contract"""
        contract = generate_function_contract(
            name="calculate_total",
            params=["items"],
            return_type="number"
        )
        assert contract["type"] == "function"
        assert contract["function_name"] == "calculate_total"
        assert "items" in contract["parameters"]
        assert contract["return_type"] == "number"

    def test_generates_function_contract_with_multiple_params(self):
        """Test function contract with multiple parameters"""
        contract = generate_function_contract(
            name="process_data",
            params=["data", "config", "options"],
            return_type="dict"
        )
        assert len(contract["parameters"]) == 3
        assert "data" in contract["parameters"]
        assert "config" in contract["parameters"]
        assert "options" in contract["parameters"]

    def test_generates_function_contract_with_description(self):
        """Test function contract with description"""
        contract = generate_function_contract(
            name="validate_user",
            params=["user_data"],
            return_type="bool",
            description="Validates user data against schema"
        )
        assert contract["description"] == "Validates user data against schema"

    def test_default_description_is_empty_string(self):
        """Test that default description is empty string"""
        contract = generate_function_contract(
            name="simple_func",
            params=[],
            return_type="None"
        )
        assert contract["description"] == ""

    def test_includes_validation_rules(self):
        """Test that function contract includes validation rules"""
        contract = generate_function_contract(
            name="test_func",
            params=["a", "b"],
            return_type="int"
        )
        assert "validation_rules" in contract
        assert contract["validation_rules"]["param_count"] == 2
        assert contract["validation_rules"]["pure_function"] is True


class TestGenerateFileContract:
    """Tests for generate_file_contract function"""

    def test_generates_basic_file_contract(self):
        """Test that generate_file_contract creates a basic file contract"""
        contract = generate_file_contract(
            filepath="/path/to/file.py"
        )
        assert contract["type"] == "file"
        assert contract["filepath"] == "/path/to/file.py"
        assert contract["must_exist"] is True

    def test_generates_file_contract_with_expected_content(self):
        """Test file contract with expected content pattern"""
        contract = generate_file_contract(
            filepath="/path/to/config.json",
            expected_content='{"key": "value"}'
        )
        assert contract["expected_content_pattern"] == '{"key": "value"}'

    def test_generates_file_contract_must_exist_false(self):
        """Test file contract where file is not required to exist"""
        contract = generate_file_contract(
            filepath="/path/to/optional.txt",
            must_exist=False
        )
        assert contract["must_exist"] is False

    def test_default_must_exist_is_true(self):
        """Test that must_exist defaults to True"""
        contract = generate_file_contract(
            filepath="/path/to/required.txt"
        )
        assert contract["must_exist"] is True

    def test_default_expected_content_is_none(self):
        """Test that expected_content_pattern defaults to None"""
        contract = generate_file_contract(
            filepath="/path/to/file.txt"
        )
        assert contract["expected_content_pattern"] is None


class TestValidateContract:
    """Tests for validate_contract function"""

    def test_validates_object_with_required_fields_success(self):
        """Test validation passes when all required fields present"""
        contract = {
            "type": "object",
            "required": ["name", "email"]
        }
        data = {"name": "John", "email": "john@example.com"}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is True
        assert errors == []

    def test_validates_object_with_missing_required_field(self):
        """Test validation fails when required field is missing"""
        contract = {
            "type": "object",
            "required": ["name", "email"]
        }
        data = {"name": "John"}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is False
        assert len(errors) > 0
        assert "Missing required field: email" in errors

    def test_validates_object_with_multiple_missing_fields(self):
        """Test validation reports all missing required fields"""
        contract = {
            "type": "object",
            "required": ["name", "email", "age"]
        }
        data = {}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is False
        assert len(errors) == 3

    def test_validates_field_types_success(self):
        """Test validation passes when field types match"""
        contract = {
            "type": "object",
            "properties": {
                "name": {"type": "str"},
                "age": {"type": "int"}
            }
        }
        data = {"name": "John", "age": 30}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is True

    def test_validates_field_types_failure(self):
        """Test validation fails when field type doesn't match"""
        contract = {
            "type": "object",
            "properties": {
                "name": {"type": "str"},
                "age": {"type": "int"}
            }
        }
        data = {"name": "John", "age": "thirty"}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is False
        assert any("wrong type" in error for error in errors)

    def test_validates_empty_contract(self):
        """Test validation with empty contract"""
        contract = {}
        data = {"any": "data"}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is True
        assert errors == []

    def test_validates_non_object_contract(self):
        """Test validation with non-object type contract"""
        contract = {"type": "api", "endpoint": "/test"}
        data = {"endpoint": "/test"}
        is_valid, errors = validate_contract(contract, data)
        # Non-object contracts should pass validation (no object rules apply)
        assert is_valid is True

    def test_validates_partial_data_with_properties(self):
        """Test validation with partial data matching properties"""
        contract = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "str"},
                "email": {"type": "str"}
            }
        }
        data = {"name": "John"}
        is_valid, errors = validate_contract(contract, data)
        assert is_valid is True
        assert errors == []
