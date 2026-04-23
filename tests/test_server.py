"""Functional tests for ddb-explorer-mcp tools against moto-backed DynamoDB."""

from __future__ import annotations

from decimal import Decimal


def test_list_tables_finds_seeded_table(ddb, orders_table):
    result = ddb.list_tables()
    assert result["count"] == 1
    assert result["tables"] == ["orders"]


def test_list_tables_substring_filter(ddb, orders_table):
    assert ddb.list_tables(name_contains="ORD")["tables"] == ["orders"]
    assert ddb.list_tables(name_contains="nope")["tables"] == []


def test_describe_table_returns_keys_and_gsi(ddb, orders_table):
    info = ddb.describe_table("orders")
    assert info["table_name"] == "orders"
    key_names = {k["AttributeName"] for k in info["key_schema"]}
    assert key_names == {"pk", "sk"}
    gsi_names = {gsi["name"] for gsi in info["global_secondary_indexes"]}
    assert gsi_names == {"by_user"}


def test_get_indexes_lists_only_indexes(ddb, orders_table):
    idx = ddb.get_indexes("orders")
    assert [g["name"] for g in idx["global_secondary_indexes"]] == ["by_user"]
    assert idx["local_secondary_indexes"] == []


def test_describe_nonexistent_table_returns_structured_error(ddb):
    out = ddb.describe_table("does-not-exist")
    assert out["error"] is True
    assert out["code"] == "ResourceNotFoundException"
    assert "message" in out


def test_get_item_found(ddb, orders_table):
    out = ddb.get_item("orders", key={"pk": "USER#0", "sk": "ORDER#000"})
    assert out["found"] is True
    assert out["item"]["user_id"] == "U0"
    assert out["item"]["amount"] == 100


def test_get_item_not_found(ddb, orders_table):
    out = ddb.get_item("orders", key={"pk": "USER#0", "sk": "ORDER#999"})
    assert out["found"] is False
    assert out["item"] is None


def test_batch_get_item(ddb, orders_table):
    keys = [
        {"pk": "USER#0", "sk": "ORDER#000"},
        {"pk": "USER#1", "sk": "ORDER#001"},
        {"pk": "USER#0", "sk": "ORDER#002"},
    ]
    out = ddb.batch_get_item("orders", keys=keys)
    assert out["count"] == 3
    sks = sorted(item["sk"] for item in out["items"])
    assert sks == ["ORDER#000", "ORDER#001", "ORDER#002"]


def test_query_by_partition_key(ddb, orders_table):
    out = ddb.query(
        table_name="orders",
        key_condition_expression="#pk = :pk",
        expression_attribute_names={"#pk": "pk"},
        expression_attribute_values={":pk": "USER#0"},
    )
    assert out["count"] == 3
    assert {it["user_id"] for it in out["items"]} == {"U0"}


def test_query_on_gsi(ddb, orders_table):
    out = ddb.query(
        table_name="orders",
        key_condition_expression="#u = :u",
        expression_attribute_names={"#u": "user_id"},
        expression_attribute_values={":u": "U1"},
        index_name="by_user",
    )
    assert out["count"] == 3
    assert {it["user_id"] for it in out["items"]} == {"U1"}


def test_scan_default_single_page(ddb, orders_table):
    out = ddb.scan("orders", limit=10, max_pages=1)
    assert out["count"] == 6
    assert out["pages_read"] == 1


def test_scan_max_pages_is_capped(ddb, orders_table):
    out = ddb.scan("orders", limit=10, max_pages=999)
    assert out["pages_read"] <= 20


def test_sample_items_returns_attribute_set(ddb, orders_table):
    out = ddb.sample_items("orders", n=3)
    assert out["returned"] == 3
    assert set(out["attributes_seen"]) >= {"pk", "sk", "user_id", "amount", "status"}


def test_decimal_coerced_to_int_or_float(ddb, orders_table):
    out = ddb.get_item("orders", key={"pk": "USER#0", "sk": "ORDER#000"})
    assert out["item"]["amount"] == 100
    assert isinstance(out["item"]["amount"], int)


def test_query_invalid_table_returns_structured_error(ddb):
    out = ddb.query(
        table_name="ghost",
        key_condition_expression="#p = :p",
        expression_attribute_names={"#p": "pk"},
        expression_attribute_values={":p": "anything"},
    )
    assert out["error"] is True
    assert out["code"] == "ResourceNotFoundException"


def test_scan_limit_is_capped(ddb, orders_table):
    out = ddb.scan("orders", limit=99999)
    assert out["count"] <= 6


def test_jsonify_handles_decimal_float_and_set(ddb, orders_table):
    from ddb_explorer_mcp.server import _jsonify

    assert _jsonify(Decimal("10")) == 10
    assert _jsonify(Decimal("10.5")) == 10.5
    assert _jsonify({"a", "b"}) == sorted(["a", "b"]) or set(_jsonify({"a", "b"})) == {"a", "b"}
    assert _jsonify(b"hello") == "hello"
    assert _jsonify({"k": [Decimal("1"), Decimal("2.5")]}) == {"k": [1, 2.5]}


def test_batch_get_item_empty_keys_fast_path(ddb, orders_table):
    out = ddb.batch_get_item("orders", keys=[])
    assert out == {"count": 0, "items": []}
