"""Security tests for ddb-explorer-mcp server."""

from __future__ import annotations

import os
import warnings
from unittest.mock import patch

import pytest
from ddb_explorer_mcp.server import (
    _check_credential_security,
    _env_int,
    _err,
    _validate_expression,
    _validate_expression_attributes,
    _is_production_mode,
)


class TestEnvIntBounds:
    """Test integer environment variable bounds validation."""

    def test_env_int_within_bounds(self, monkeypatch):
        """Test that values within bounds are accepted."""
        monkeypatch.setenv("DDB_QUERY_MAX_LIMIT", "200")
        assert _env_int("DDB_QUERY_MAX_LIMIT", 100) == 200

    def test_env_int_exceeds_upper_bound(self, monkeypatch):
        """Test that values above upper bound are clamped."""
        monkeypatch.setenv("DDB_QUERY_MAX_LIMIT", "2000")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _env_int("DDB_QUERY_MAX_LIMIT", 100)
            assert result == 1000  # Clamped to max
            assert len(w) == 1
            assert "outside safe bounds" in str(w[0].message)

    def test_env_int_below_lower_bound(self, monkeypatch):
        """Test that values below lower bound are clamped."""
        monkeypatch.setenv("DDB_QUERY_MAX_LIMIT", "0")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _env_int("DDB_QUERY_MAX_LIMIT", 100)
            assert result == 1  # Clamped to min
            assert len(w) == 1

    def test_env_int_invalid_value(self, monkeypatch):
        """Test that invalid values fall back to default."""
        monkeypatch.setenv("DDB_QUERY_MAX_LIMIT", "not-a-number")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _env_int("DDB_QUERY_MAX_LIMIT", 100)
            assert result == 100  # Default
            assert len(w) == 1
            assert "Invalid integer value" in str(w[0].message)

    def test_env_int_port_bounds(self, monkeypatch):
        """Test port number bounds (1024-65535)."""
        monkeypatch.setenv("MCP_PORT", "500")
        result = _env_int("MCP_PORT", 8000)
        assert result == 1024  # Clamped to min port


class TestErrorSanitization:
    """Test error message sanitization in production mode."""

    def test_error_sanitization_production(self, monkeypatch):
        """Test that errors are sanitized in production mode."""
        monkeypatch.setenv("DDB_PRODUCTION", "true")
        from ddb_explorer_mcp.server import _err, ClientError
        
        # Mock ClientError
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Table MySecretTable does not exist in region us-east-1"
                }
            },
            operation_name="DescribeTable"
        )
        
        result = _err(error)
        assert result["code"] == "ResourceNotFoundException"
        assert result["message"] == "Resource not found"
        assert "MySecretTable" not in result["message"]
        assert "us-east-1" not in result["message"]

    def test_error_sanitization_development(self, monkeypatch):
        """Test that full errors are shown in development mode."""
        monkeypatch.setenv("DDB_PRODUCTION", "false")
        from ddb_explorer_mcp.server import _err, ClientError
        
        error = ClientError(
            error_response={
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "Table MySecretTable does not exist"
                }
            },
            operation_name="DescribeTable"
        )
        
        result = _err(error)
        assert result["code"] == "ResourceNotFoundException"
        assert "MySecretTable" in result["message"]

    def test_unknown_error_sanitization(self, monkeypatch):
        """Test that unknown errors are generalized in production."""
        monkeypatch.setenv("DDB_PRODUCTION", "true")
        
        error = ValueError("Some internal error with sensitive data")
        result = _err(error)
        assert result["code"] == "RequestError"
        assert result["message"] == "Request could not be processed"
        assert "sensitive data" not in result["message"]


class TestExpressionValidation:
    """Test DynamoDB expression validation for injection prevention."""

    def test_valid_expression(self):
        """Test that valid expressions pass validation."""
        assert _validate_expression("#pk = :pk AND begins_with(#sk, :prefix)") is None
        assert _validate_expression("attribute_exists(#field)") is None
        assert _validate_expression("#a BETWEEN :low AND :high") is None

    def test_sql_injection_keywords(self):
        """Test that SQL keywords are blocked."""
        result = _validate_expression("DROP TABLE users")
        assert result["error"] is True
        assert "prohibited keyword: DROP" in result["message"]
        
        result = _validate_expression("field = 'test' OR DELETE FROM items")
        assert result["error"] is True
        assert "DELETE" in result["message"]

    def test_command_injection_characters(self):
        """Test that command injection characters are blocked."""
        result = _validate_expression("field = 'test'; ls -la")
        assert result["error"] is True
        assert "prohibited character: ';'" in result["message"]
        
        result = _validate_expression("field = `whoami`")
        assert result["error"] is True
        assert "prohibited character: '`'" in result["message"]

    def test_expression_length_limit(self):
        """Test that overly long expressions are rejected."""
        long_expr = "a = b AND " * 500  # Create > 4096 char expression
        result = _validate_expression(long_expr)
        assert result["error"] is True
        assert "Expression too long" in result["message"]

    def test_unbalanced_parentheses(self):
        """Test that unbalanced parentheses are caught."""
        result = _validate_expression("(a = b AND (c = d)")
        assert result["error"] is True
        assert "Unbalanced parentheses" in result["message"]

    def test_empty_expression(self):
        """Test that empty expressions are allowed."""
        assert _validate_expression("") is None
        assert _validate_expression(None) is None


class TestAttributeValidation:
    """Test expression attribute name and value validation."""

    def test_valid_attribute_names(self):
        """Test that valid attribute names pass."""
        names = {"#pk": "partition_key", "#sk": "sort_key"}
        assert _validate_expression_attributes(names=names) is None

    def test_invalid_attribute_placeholder(self):
        """Test that invalid placeholders are rejected."""
        names = {"pk": "partition_key"}  # Missing #
        result = _validate_expression_attributes(names=names)
        assert result["error"] is True
        assert "Invalid attribute name placeholder" in result["message"]

    def test_valid_nested_attributes(self):
        """Test that nested attributes with dots are allowed."""
        names = {"#addr": "address.city.name"}
        assert _validate_expression_attributes(names=names) is None

    def test_invalid_attribute_name(self):
        """Test that invalid attribute names are rejected."""
        names = {"#key": "123invalid"}  # Can't start with number
        result = _validate_expression_attributes(names=names)
        assert result["error"] is True
        assert "Invalid attribute name" in result["message"]

    def test_valid_expression_values(self):
        """Test that valid expression values pass."""
        values = {":pk": "USER#123", ":limit": 100}
        assert _validate_expression_attributes(values=values) is None

    def test_invalid_value_placeholder(self):
        """Test that invalid value placeholders are rejected."""
        values = {"pk": "USER#123"}  # Missing :
        result = _validate_expression_attributes(values=values)
        assert result["error"] is True
        assert "Invalid value placeholder" in result["message"]

    def test_oversized_value(self):
        """Test that oversized values are rejected."""
        huge_value = "x" * 500_000  # > 400KB limit
        values = {":data": huge_value}
        result = _validate_expression_attributes(values=values)
        assert result["error"] is True
        assert "exceeds size limit" in result["message"]


class TestCredentialSecurity:
    """Test AWS credential security warnings."""

    def test_long_term_key_warning(self, monkeypatch, capsys):
        """Test warning for long-term AWS keys."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _check_credential_security()
            
            # Check warnings were issued
            security_warnings = [warning for warning in w if "[SECURITY]" in str(warning.message)]
            assert len(security_warnings) >= 2
            assert any("long-term AWS access key" in str(warning.message) for warning in security_warnings)
            assert any("Consider using IAM roles" in str(warning.message) for warning in security_warnings)

    def test_http_mode_warning(self, monkeypatch, capsys):
        """Test warning for HTTP mode without auth."""
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _check_credential_security()
            
            # Check HTTP warning was issued
            security_warnings = [warning for warning in w if "[SECURITY]" in str(warning.message)]
            assert len(security_warnings) >= 1
            assert any("without built-in authentication" in str(warning.message) for warning in security_warnings)

    def test_tls_warning(self, monkeypatch):
        """Test warning for missing TLS configuration."""
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        monkeypatch.delenv("DDB_TLS_CERT", raising=False)
        monkeypatch.delenv("DDB_REQUIRE_TLS", raising=False)
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _check_credential_security()
            
            # Check TLS warning was issued
            security_warnings = [warning for warning in w if "[SECURITY]" in str(warning.message)]
            assert any("No TLS configuration detected" in str(warning.message) for warning in security_warnings)

    def test_temporary_credentials_no_warning(self, monkeypatch):
        """Test that temporary credentials don't trigger long-term key warning."""
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ASIAIOSFODNN7EXAMPLE")  # ASIA = temporary
        monkeypatch.setenv("AWS_SESSION_TOKEN", "token123")
        monkeypatch.setenv("MCP_TRANSPORT", "stdio")
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _check_credential_security()
            
            # Should not warn about long-term keys
            assert not any("long-term AWS access key" in str(warning.message) for warning in w)


class TestIntegrationSecurity:
    """Integration tests for security features in tool functions."""

    def test_query_with_sql_injection(self, ddb, orders_table):
        """Test that query rejects SQL injection attempts."""
        result = ddb.query(
            table_name="orders",
            key_condition_expression="pk = :pk OR 1=1; DROP TABLE users",
            expression_attribute_values={":pk": "USER#1"},
        )
        assert result["error"] is True
        assert "prohibited keyword: DROP" in result["message"]

    def test_scan_with_command_injection(self, ddb, orders_table):
        """Test that scan rejects command injection attempts."""
        result = ddb.scan(
            table_name="orders",
            filter_expression="status = 'active'; cat /etc/passwd",
        )
        assert result["error"] is True
        assert "prohibited character" in result["message"]

    def test_query_with_invalid_placeholders(self, ddb, orders_table):
        """Test that invalid placeholders are rejected."""
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"invalid": "pk"},  # Missing #
            expression_attribute_values={":pk": "USER#1"},
        )
        assert result["error"] is True
        assert "Invalid attribute name placeholder" in result["message"]

    def test_production_error_sanitization_integration(self, ddb, monkeypatch):
        """Test error sanitization in production mode during actual operations."""
        monkeypatch.setenv("DDB_PRODUCTION", "true")
        
        # Try to query non-existent table
        result = ddb.query(
            table_name="non_existent_secret_table",
            key_condition_expression="pk = :pk",
            expression_attribute_values={":pk": "test"},
        )
        
        assert result["error"] is True
        assert result["message"] == "Resource not found"
        assert "non_existent_secret_table" not in result["message"]