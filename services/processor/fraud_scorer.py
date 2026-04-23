from common.models import RawTransactionV1, ScoredTransactionV1, FraudDecision
import redis.asyncio as redis
from .velocity_store import check_and_update_velocity


async def evaluate_fraud(
    transaction: RawTransactionV1,
    redis_client: redis.Redis,
    window_size: int = 300
) -> ScoredTransactionV1:

    velocity_amount_cents = await check_and_update_velocity(
        redis_client=redis_client,
        from_account_id=transaction.from_account_id,
        transaction_id=transaction.transaction_id,
        amount_cents=transaction.amount_cents,
        window=window_size
    )
    
    fraud_score = _calculate_score(
        transaction=transaction) + _calculate_velocity_panelty(velocity_amount_cents)
    
    decision = FraudDecision.FLAGGED
    
    if fraud_score >= 75:
        decision = FraudDecision.REJECTED
    elif fraud_score >= 50:
        decision = FraudDecision.FLAGGED
    else:
        decision = FraudDecision.APPROVED
        
    return ScoredTransactionV1(**transaction.model_dump(), fraud_score=fraud_score, decision=decision)


def _calculate_score(transaction: RawTransactionV1) -> int:
    score = 0
    if transaction.amount_cents > 10_00_000:
        score += 50
    if not transaction.metadata.geo_location:
        score += 25
    return score


def _calculate_velocity_panelty(velocity_amount_cents: int) -> int:
    """ Calculate fraud points based on the amount transfered in window(seconds) """
    if velocity_amount_cents > 200_000:
        return 60
    elif velocity_amount_cents > 50_000:
        return 25
    else:
        return 0
