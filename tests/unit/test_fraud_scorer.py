import pytest
from services.processor.fraud_scorer import evaluate_fraud
from common.models import RawTransactionV1, TransactionMetadata, FraudDecision
from uuid import uuid4

@pytest.fixture
def rawTransactionObject():
    transaction = RawTransactionV1(
        idempotency_key=f"idem-key-test-{uuid4()}",
        from_account_id=uuid4(),
        to_account_id=uuid4(),
        amount_cents=1_000_000,
        currency="CAD",
        metadata=TransactionMetadata(
            ip_address="192.168.1.15",
            device_id="iphone-17-pro-max-xyz",
            geo_location="Montreal, QC",
            user_agent="Eventforge-iOS-App/1.0"
        )
    )
    return transaction

@pytest.mark.asyncio
async def test_zero_fraud_score(rawTransactionObject):
    
    scored_tx = await evaluate_fraud(rawTransactionObject)
    
    assert scored_tx.decision == FraudDecision.APPROVED
    assert scored_tx.fraud_score == 0
    

@pytest.mark.asyncio
async def test_no_geo_location(rawTransactionObject):
    mutated_metadata = rawTransactionObject.metadata.model_copy(update={"geo_location": None})
    mutated_tx = rawTransactionObject.model_copy(update={"metadata": mutated_metadata})
  
    scored_tx = await evaluate_fraud(mutated_tx)

    assert scored_tx.decision == FraudDecision.APPROVED
    assert scored_tx.fraud_score == 25
    

@pytest.mark.asyncio
async def test_transaction_flagged(rawTransactionObject):

    mutated_tx = rawTransactionObject.model_copy(
        update={"amount_cents": 1000100})
    
    scored_tx = await evaluate_fraud(mutated_tx)

    assert scored_tx.decision == FraudDecision.FLAGGED
    assert scored_tx.fraud_score == 50


@pytest.mark.asyncio
async def test_transaction_rejected(rawTransactionObject):

    mutated_metadata = rawTransactionObject.metadata.model_copy(
        update={"geo_location": None})
    mutated_tx = rawTransactionObject.model_copy(
        update={"metadata": mutated_metadata, "amount_cents": 1000100}
        )

    scored_tx = await evaluate_fraud(mutated_tx)

    assert scored_tx.decision == FraudDecision.REJECTED
    assert scored_tx.fraud_score == 75
