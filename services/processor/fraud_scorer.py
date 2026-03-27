from common.models import RawTransactionV1, ScoredTransactionV1, FraudDecision

async def evaluate_fraud(transaction: RawTransactionV1) -> ScoredTransactionV1:
    
    fraud_score = _calculate_score(transaction=transaction)
    
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
    