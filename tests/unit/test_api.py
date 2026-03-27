from fastapi.testclient import TestClient
from services.gateway.main import app, _get_db, _get_redis_client
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

client = TestClient(app=app)


""" Test Missing amount """
def test_create_transaction_fail_on_missing_amount():
    bad_transaction = {
        
            "idempotency_key": f"idem-key-bad-{str(uuid4())}",
            "from_account_id": str(uuid4()),
            "to_account_id": str(uuid4()),
            "currency": "CAD",
            "metadata": {
                "ip_address": "192.168.1.15",
                "device_id": "iphone-17-pro-max-xyz",
                "geo_location": "Edmonton, AB",
                "user_agent": "Eventforge-iOS-App/1.0"
            }
    }
    
    response = client.post("/transactions", json=bad_transaction)
    
    assert response.status_code not in [200, 201, 202]
    assert response.status_code == 422

""" Happy Path : Successful transaction """
def test_create_transaction_success():
    
    # Redis Mock
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = ""
    
    # DB Mock
    mock_db_session = AsyncMock()
    mock_db_session.begin = MagicMock(return_value=AsyncMock())
    
    # Override dependencies
    
    app.dependency_overrides[_get_db] = lambda: mock_db_session
    app.dependency_overrides[_get_redis_client] = lambda: mock_redis
    
    good_transaction = {
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
    
    try:
        response = client.post("/transactions", json=good_transaction)
        assert response.status_code == 201
        
        data = response.json()
        assert "transaction_id" in data
        assert data["message"] == "Transaction created successfully"

        mock_redis.get.assert_called_once()
        assert mock_db_session.add.call_count == 2
        mock_redis.set.assert_called_once()
        
    finally:
        app.dependency_overrides.clear()
        
""" Same transaction multiple times """
def test_duplicate_idempotancy_key():
    
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = str(uuid4()).encode("utf-8")       # There's already some tx_id present for given idempotancy key
    
    mock_db_session = AsyncMock()
    mock_db_session.begin = MagicMock(return_value=AsyncMock())
    
    app.dependency_overrides[_get_db] = lambda: mock_db_session
    app.dependency_overrides[_get_redis_client] = lambda: mock_redis


    idempotancy_key = f"idem-key-happy-{uuid4()}"
    transaction = {
        "idempotency_key": idempotancy_key ,
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
    try:
        response = client.post("/transactions", json=transaction)
        
        assert response.status_code == 202
        mock_redis.get.assert_called_once_with(
            f"idempotency:tx:{idempotancy_key}")
        mock_redis.set.assert_not_called()
        mock_db_session.add.assert_not_called()
    finally:
        app.dependency_overrides.clear()
    
    
""" Test database failure """

def test_database_exception():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.get.return_value = ""

    mock_db_session = AsyncMock()
    mock_db_session.begin = MagicMock(return_value=AsyncMock())
    mock_db_session.add = MagicMock(side_effect=Exception("Simulating Database Exception"))

    app.dependency_overrides[_get_db] = lambda: mock_db_session
    app.dependency_overrides[_get_redis_client] = lambda: mock_redis
    
    transaction = {
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
    try:
        response = client.post("/transactions", json=transaction)

        assert response.status_code == 500
        assert response.json() == "Internal Server Error"
        mock_redis.get.assert_called_once()
        mock_redis.set.assert_not_called()
        
    finally:
        app.dependency_overrides.clear()
