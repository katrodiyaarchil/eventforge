import pytest
from fastapi.testclient import TestClient
from services.gateway.main import app, _get_db, _get_redis_client
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

client = TestClient(app=app)


@pytest.fixture(scope="module")
def valid_transaction_payload():
    return {
        "idempotency_key": f"idem-key-happy-{uuid4()}",
        "from_account_id": str(uuid4()),
        "to_account_id": str(uuid4()),
        "amount_cents": 5000,
        "currency": "CAD",
        "metadata": {
            "ip_address": "192.168.1.15",
            "device_id": "iphone-17-pro-max-xyz",
            "geo_location": "Edmonton, AB",
            "user_agent": "Eventforge-iOS-App/1.0"
        }
    }


@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.set.return_value = True
    mock.get.return_value = ""
    return mock


@pytest.fixture
def mock_db_session():
    mock = AsyncMock()
    mock.begin = MagicMock(return_value=AsyncMock())
    return mock


@pytest.fixture(autouse=True)
def override_dependencies(mock_db_session, mock_redis):
    app.dependency_overrides[_get_db] = lambda: mock_db_session
    app.dependency_overrides[_get_redis_client] = lambda: mock_redis
    yield
    app.dependency_overrides.clear()


""" Test Missing amount """


def test_create_transaction_fail_on_missing_amount(valid_transaction_payload):
    bad_transaction = valid_transaction_payload.copy()
    del bad_transaction["amount_cents"]

    response = client.post("/transactions", json=bad_transaction)

    assert response.status_code == 422


""" Happy Path : Successful transaction """


def test_create_transaction_success(valid_transaction_payload, mock_redis, mock_db_session):
    response = client.post("/transactions", json=valid_transaction_payload)

    assert response.status_code == 201

    data = response.json()
    assert "transaction_id" in data
    assert data["message"] == "Transaction created successfully"

    mock_redis.get.assert_called_once()
    assert mock_db_session.add.call_count == 2
    mock_redis.set.assert_called_once()


""" Same transaction multiple times """


def test_duplicate_idempotancy_key(valid_transaction_payload, mock_redis, mock_db_session):
    # Override the default mock behavior just for this test
    mock_redis.get.return_value = str(uuid4()).encode("utf-8")

    response = client.post("/transactions", json=valid_transaction_payload)

    assert response.status_code == 202
    mock_redis.get.assert_called_once_with(
        f"idempotency:tx:{valid_transaction_payload['idempotency_key']}")
    mock_redis.set.assert_not_called()
    mock_db_session.add.assert_not_called()


""" Test database failure """


def test_database_exception(valid_transaction_payload, mock_redis, mock_db_session):
    # Override the default DB mock behavior to throw an error
    mock_db_session.add = MagicMock(side_effect=Exception(
        "Simulating Database Exception"))

    response = client.post("/transactions", json=valid_transaction_payload)

    assert response.status_code == 500
    assert response.json() == "Internal Server Error"
    mock_redis.get.assert_called_once()
    mock_redis.set.assert_not_called()
