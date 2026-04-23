"""Shared fixtures — fake AWS creds + mocked DynamoDB via moto."""

from __future__ import annotations

from decimal import Decimal

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def _aws_credentials(monkeypatch):
    """Ensure moto receives dummy credentials (and never real ones)."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def ddb():
    """Activate moto and rebind the server module's boto3 clients inside it.

    Because server.py creates module-level `_client` and `_resource` at import
    time, we recreate them after entering `mock_aws()` so they target the mock.
    """
    with mock_aws():
        from ddb_explorer_mcp import server as srv

        srv._client = boto3.client("dynamodb", region_name="us-east-1")
        srv._resource = boto3.resource("dynamodb", region_name="us-east-1")
        yield srv


@pytest.fixture
def orders_table(ddb):
    """A composite-key `orders` table with a GSI and 6 seeded items."""
    table = ddb._resource.create_table(
        TableName="orders",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_user",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    for i in range(6):
        table.put_item(
            Item={
                "pk": f"USER#{i % 2}",
                "sk": f"ORDER#{i:03d}",
                "user_id": f"U{i % 2}",
                "amount": Decimal(str(100 + i)),
                "status": "open" if i % 2 == 0 else "closed",
            }
        )
    return table
