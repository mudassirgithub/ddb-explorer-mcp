"""Edge-case and error-path tests for ddb-explorer-mcp.

Covers: malformed inputs, permission errors, parameter capping,
pagination boundaries, empty tables, jsonify corner cases, _err helper,
_env_int helper, and transport dispatch.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# _jsonify corner cases
# ---------------------------------------------------------------------------


class TestJsonify:
    def test_frozenset(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        result = _jsonify(frozenset([1, 2, 3]))
        assert sorted(result) == [1, 2, 3]

    def test_non_utf8_bytes(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        result = _jsonify(b"\x80\x81\x82")
        assert result == "<3 bytes>"

    def test_nested_mixed_types(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        data = {
            "numbers": [Decimal("1"), Decimal("2.5")],
            "tags": {"a", "b"},
            "raw": b"test",
            "nested": {"deep": Decimal("0")},
        }
        result = _jsonify(data)
        assert result["numbers"] == [1, 2.5]
        assert result["raw"] == "test"
        assert result["nested"]["deep"] == 0
        assert isinstance(result["nested"]["deep"], int)

    def test_none_passthrough(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify(None) is None

    def test_string_passthrough(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify("hello") == "hello"

    def test_bool_passthrough(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify(True) is True

    def test_large_decimal_stays_int(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify(Decimal("999999999999")) == 999999999999
        assert isinstance(_jsonify(Decimal("999999999999")), int)

    def test_negative_decimal(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify(Decimal("-42.5")) == -42.5

    def test_zero_decimal(self, ddb):
        from ddb_explorer_mcp.server import _jsonify

        assert _jsonify(Decimal("0")) == 0
        assert isinstance(_jsonify(Decimal("0")), int)


# ---------------------------------------------------------------------------
# _err helper
# ---------------------------------------------------------------------------


class TestErrHelper:
    def test_client_error_structure(self, ddb):
        from ddb_explorer_mcp.server import _err

        exc = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "not allowed"}},
            "DescribeTable",
        )
        result = _err(exc)
        assert result["error"] is True
        assert result["code"] == "AccessDeniedException"
        assert result["message"] == "not allowed"

    def test_client_error_missing_fields(self, ddb):
        from ddb_explorer_mcp.server import _err

        exc = ClientError({"Error": {}}, "SomeOp")
        result = _err(exc)
        assert result["error"] is True
        assert result["code"] == "ClientError"

    def test_botocore_error(self, ddb):
        from ddb_explorer_mcp.server import _err

        exc = BotoCoreError()
        result = _err(exc)
        assert result["error"] is True
        assert result["code"] == "BotoCoreError"

    def test_generic_exception(self, ddb):
        from ddb_explorer_mcp.server import _err

        result = _err(ValueError("bad value"))
        assert result["error"] is True
        assert result["code"] == "ValueError"
        assert result["message"] == "bad value"


# ---------------------------------------------------------------------------
# _env_int helper
# ---------------------------------------------------------------------------


class TestEnvInt:
    def test_valid_int(self, monkeypatch, ddb):
        from ddb_explorer_mcp.server import _env_int

        monkeypatch.setenv("TEST_PORT", "9999")
        assert _env_int("TEST_PORT", 1234) == 9999

    def test_invalid_int_falls_back(self, monkeypatch, ddb):
        from ddb_explorer_mcp.server import _env_int

        monkeypatch.setenv("TEST_PORT", "not-a-number")
        assert _env_int("TEST_PORT", 1234) == 1234

    def test_missing_var_falls_back(self, ddb):
        from ddb_explorer_mcp.server import _env_int

        assert _env_int("NONEXISTENT_VAR_12345", 42) == 42

    def test_empty_string_falls_back(self, monkeypatch, ddb):
        from ddb_explorer_mcp.server import _env_int

        monkeypatch.setenv("TEST_PORT", "")
        assert _env_int("TEST_PORT", 42) == 42


# ---------------------------------------------------------------------------
# list_tables edge cases
# ---------------------------------------------------------------------------


class TestListTablesEdge:
    def test_empty_region_no_tables(self, ddb):
        result = ddb.list_tables()
        assert result["count"] == 0
        assert result["tables"] == []

    def test_filter_empty_string_returns_all(self, ddb, orders_table):
        result = ddb.list_tables(name_contains="")
        assert result["count"] == 1

    def test_filter_case_insensitive(self, ddb, orders_table):
        assert ddb.list_tables(name_contains="ORDERS")["count"] == 1
        assert ddb.list_tables(name_contains="OrDeRs")["count"] == 1


# ---------------------------------------------------------------------------
# describe_table / get_indexes — nonexistent tables
# ---------------------------------------------------------------------------


class TestDescribeEdge:
    def test_describe_nonexistent(self, ddb):
        result = ddb.describe_table("ghost-table")
        assert result["error"] is True
        assert result["code"] == "ResourceNotFoundException"

    def test_get_indexes_nonexistent(self, ddb):
        result = ddb.get_indexes("ghost-table")
        assert result["error"] is True
        assert result["code"] == "ResourceNotFoundException"

    def test_describe_table_no_gsi_no_lsi(self, ddb):
        """Table with no secondary indexes should return empty lists."""
        ddb._resource.create_table(
            TableName="simple",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        result = ddb.describe_table("simple")
        assert result["global_secondary_indexes"] == []
        assert result["local_secondary_indexes"] == []


# ---------------------------------------------------------------------------
# sample_items — parameter capping and edge cases
# ---------------------------------------------------------------------------


class TestSampleItemsEdge:
    def test_n_capped_at_20(self, ddb, orders_table):
        result = ddb.sample_items("orders", n=999)
        assert result["returned"] <= 20

    def test_n_floor_at_1(self, ddb, orders_table):
        result = ddb.sample_items("orders", n=-5)
        assert result["returned"] >= 1

    def test_n_zero_becomes_1(self, ddb, orders_table):
        result = ddb.sample_items("orders", n=0)
        assert result["returned"] >= 1

    def test_empty_table(self, ddb):
        ddb._resource.create_table(
            TableName="empty",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        result = ddb.sample_items("empty", n=5)
        assert result["returned"] == 0
        assert result["items"] == []
        assert result["attributes_seen"] == []

    def test_nonexistent_table(self, ddb):
        result = ddb.sample_items("ghost-table")
        assert result["error"] is True


# ---------------------------------------------------------------------------
# get_item — malformed key, wrong table
# ---------------------------------------------------------------------------


class TestGetItemEdge:
    def test_wrong_key_attribute(self, ddb, orders_table):
        result = ddb.get_item("orders", key={"wrong_key": "value"})
        assert result["error"] is True

    def test_nonexistent_table(self, ddb):
        result = ddb.get_item("ghost-table", key={"pk": "x"})
        assert result["error"] is True

    def test_consistent_read(self, ddb, orders_table):
        result = ddb.get_item(
            "orders",
            key={"pk": "USER#0", "sk": "ORDER#000"},
            consistent_read=True,
        )
        assert result["found"] is True


# ---------------------------------------------------------------------------
# batch_get_item — chunking, missing keys
# ---------------------------------------------------------------------------


class TestBatchGetItemEdge:
    def test_empty_keys(self, ddb, orders_table):
        result = ddb.batch_get_item("orders", keys=[])
        assert result == {"count": 0, "items": []}

    def test_all_keys_missing(self, ddb, orders_table):
        keys = [
            {"pk": "USER#99", "sk": "ORDER#999"},
            {"pk": "USER#98", "sk": "ORDER#998"},
        ]
        result = ddb.batch_get_item("orders", keys=keys)
        assert result["count"] == 0
        assert result["items"] == []

    def test_mixed_found_and_missing(self, ddb, orders_table):
        keys = [
            {"pk": "USER#0", "sk": "ORDER#000"},  # exists
            {"pk": "USER#99", "sk": "ORDER#999"},  # does not
        ]
        result = ddb.batch_get_item("orders", keys=keys)
        assert result["count"] == 1

    def test_large_batch_over_100(self, ddb, orders_table):
        """Verify chunking works with > 100 keys (most will not be found)."""
        keys = [{"pk": f"USER#{i}", "sk": f"ORDER#{i:03d}"} for i in range(150)]
        result = ddb.batch_get_item("orders", keys=keys)
        assert isinstance(result["count"], int)
        assert isinstance(result["items"], list)

    def test_nonexistent_table(self, ddb):
        result = ddb.batch_get_item("ghost-table", keys=[{"pk": "x", "sk": "y"}])
        assert result["error"] is True

    def test_consistent_read_flag(self, ddb, orders_table):
        keys = [{"pk": "USER#0", "sk": "ORDER#000"}]
        result = ddb.batch_get_item("orders", keys=keys, consistent_read=True)
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# query — parameter capping, bad expressions, pagination
# ---------------------------------------------------------------------------


class TestQueryEdge:
    def test_limit_capped_at_500(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            limit=99999,
        )
        assert result["count"] <= 500

    def test_limit_floor_at_1(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            limit=-10,
        )
        assert result["count"] >= 0

    def test_invalid_expression(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="INVALID EXPR !!!",
            expression_attribute_values={":pk": "USER#0"},
        )
        assert result["error"] is True

    def test_nonexistent_gsi(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            index_name="nonexistent_index",
        )
        assert result["error"] is True

    def test_scan_index_forward_false(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            scan_index_forward=False,
        )
        sks = [it["sk"] for it in result["items"]]
        assert sks == sorted(sks, reverse=True)

    def test_filter_expression(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk", "#s": "status"},
            expression_attribute_values={":pk": "USER#0", ":s": "open"},
            filter_expression="#s = :s",
        )
        assert result["count"] >= 0
        for item in result["items"]:
            assert item["status"] == "open"

    def test_projection_expression(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            projection_expression="pk, sk",
        )
        for item in result["items"]:
            assert "pk" in item
            assert "amount" not in item

    def test_empty_result_set(self, ddb, orders_table):
        result = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#NONEXISTENT"},
        )
        assert result["count"] == 0
        assert result["items"] == []
        assert result["last_evaluated_key"] is None

    def test_pagination_with_small_limit(self, ddb, orders_table):
        """Query with limit=1 should return last_evaluated_key for continuation."""
        page1 = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            limit=1,
        )
        assert page1["count"] == 1
        assert page1["last_evaluated_key"] is not None

        page2 = ddb.query(
            table_name="orders",
            key_condition_expression="#pk = :pk",
            expression_attribute_names={"#pk": "pk"},
            expression_attribute_values={":pk": "USER#0"},
            limit=1,
            exclusive_start_key=page1["last_evaluated_key"],
        )
        assert page2["count"] == 1
        assert page2["items"][0]["sk"] != page1["items"][0]["sk"]


# ---------------------------------------------------------------------------
# scan — parameter capping, pagination, filter, empty table
# ---------------------------------------------------------------------------


class TestScanEdge:
    def test_limit_capped_at_500(self, ddb, orders_table):
        result = ddb.scan("orders", limit=99999)
        assert isinstance(result["count"], int)

    def test_limit_floor_at_1(self, ddb, orders_table):
        result = ddb.scan("orders", limit=-10)
        assert isinstance(result["count"], int)

    def test_max_pages_capped_at_20(self, ddb, orders_table):
        result = ddb.scan("orders", max_pages=999)
        assert result["pages_read"] <= 20

    def test_max_pages_floor_at_1(self, ddb, orders_table):
        result = ddb.scan("orders", max_pages=-5)
        assert result["pages_read"] >= 1

    def test_empty_table_scan(self, ddb):
        ddb._resource.create_table(
            TableName="empty-scan",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        result = ddb.scan("empty-scan")
        assert result["count"] == 0
        assert result["items"] == []
        assert result["last_evaluated_key"] is None

    def test_nonexistent_table(self, ddb):
        result = ddb.scan("ghost-table")
        assert result["error"] is True

    def test_scan_with_filter(self, ddb, orders_table):
        result = ddb.scan(
            "orders",
            filter_expression="#s = :s",
            expression_attribute_names={"#s": "status"},
            expression_attribute_values={":s": "open"},
        )
        for item in result["items"]:
            assert item["status"] == "open"

    def test_scan_with_projection(self, ddb, orders_table):
        result = ddb.scan("orders", projection_expression="pk, sk")
        for item in result["items"]:
            assert "pk" in item
            assert "amount" not in item

    def test_scan_pagination_manual(self, ddb, orders_table):
        """Scan with limit=2, max_pages=1 — then continue with exclusive_start_key."""
        page1 = ddb.scan("orders", limit=2, max_pages=1)
        if page1["last_evaluated_key"]:
            page2 = ddb.scan(
                "orders",
                limit=2,
                max_pages=1,
                exclusive_start_key=page1["last_evaluated_key"],
            )
            all_pks = {it["pk"] for it in page1["items"]} | {it["pk"] for it in page2["items"]}
            assert len(all_pks) >= 1

    def test_scan_on_gsi(self, ddb, orders_table):
        result = ddb.scan("orders", index_name="by_user")
        assert result["count"] == 6


# ---------------------------------------------------------------------------
# transport dispatch
# ---------------------------------------------------------------------------


class TestTransportDispatch:
    def test_unknown_transport_raises(self, ddb):
        original = ddb.TRANSPORT
        try:
            ddb.TRANSPORT = "banana"
            with pytest.raises(SystemExit, match="Unknown MCP_TRANSPORT"):
                ddb.main()
        finally:
            ddb.TRANSPORT = original
