"""Event Ingestion and Risk Evaluation API Routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.database.repository import Repository
from src.engine.service import EventProcessingService
from src.agent.investigator import RiskInvestigationService
from src.agent.schemas import InvestigationReport, AuditLogRecord
from src.agent.audit import get_global_audit_logger
from src.api.schemas.events import PaymentEventInput, PaymentEventResponse
from src.api.schemas.risk import RiskAnalysisRequest, RiskAnalysisResponse, StoredRiskAssessmentResponse
from src.core.logging import get_logger

logger = get_logger("api_events")
router = APIRouter(tags=["Events & Risk Engine"])


@router.post(
    "/events",
    response_model=PaymentEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and assess a live payment event",
    description="Calculates real-time behavioural features, applies rule engine, computes risk score, persists to DB, and returns decision.",
)
def ingest_event(
    event: PaymentEventInput,
    db: Session = Depends(get_db),
) -> PaymentEventResponse:
    """Synchronously evaluates an incoming payment event and stores the assessment."""
    try:
        service = EventProcessingService(db)
        result = service.process_event(event.model_dump(), dry_run=False)
        return PaymentEventResponse(**result)
    except Exception as e:
        logger.error("Error processing event: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process event: {str(e)}",
        )


@router.post(
    "/risk/analyze",
    response_model=RiskAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Dry-run risk analysis for a payment event",
    description="Evaluates features and behavioural rules on-the-fly without database mutation. Returns full feature vector.",
)
def analyze_risk_dry_run(
    event: RiskAnalysisRequest,
    db: Session = Depends(get_db),
) -> RiskAnalysisResponse:
    """Evaluates behavioral risk on-the-fly in dry-run mode."""
    try:
        service = EventProcessingService(db)
        result = service.process_event(event.model_dump(), dry_run=True)
        return RiskAnalysisResponse(**result)
    except Exception as e:
        logger.error("Error analyzing event: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze event: {str(e)}",
        )


@router.get(
    "/risk/{transaction_id}",
    response_model=StoredRiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve stored risk assessment by Transaction ID",
)
def get_risk_assessment_by_tx(
    transaction_id: str,
    db: Session = Depends(get_db),
) -> StoredRiskAssessmentResponse:
    """Retrieves an existing transaction and its stored risk assessment."""
    repo = Repository(db)
    tx = repo.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with ID '{transaction_id}' not found.",
        )

    assessment = repo.get_risk_assessment(transaction_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk assessment for transaction '{transaction_id}' not found.",
        )

    return StoredRiskAssessmentResponse(
        transaction_id=tx.id,
        event_time=tx.event_time.isoformat() if tx.event_time else "",
        user_id=tx.user_id,
        merchant_id=tx.merchant_id,
        amount=tx.amount,
        currency=tx.currency,
        status=tx.status,
        failure_code=tx.failure_code,
        composite_risk_score=assessment.composite_risk_score,
        risk_tier=assessment.risk_tier,
        fast_action=assessment.fast_action,
        xgboost_score=assessment.xgboost_score,
        iforest_score=assessment.iforest_score,
        velocity_score=assessment.velocity_score,
        graph_score=assessment.graph_score,
        primary_rule_triggered=assessment.primary_rule_triggered,
        latency_ms=assessment.latency_ms,
    )


@router.post(
    "/investigate/{transaction_id}",
    response_model=InvestigationReport,
    status_code=status.HTTP_200_OK,
    summary="Trigger LangGraph AI Investigation Agent on a stored transaction",
    description="Orchestrates a stateful multi-step AI investigation (observe, analyze, investigate, correlate, decide, recommend, explain) over deterministic ML, rules, and NetworkX fraud graph evidence.",
)
def investigate_transaction_api(
    transaction_id: str,
    analyst_notes: str = None,
    db: Session = Depends(get_db),
) -> InvestigationReport:
    """Invokes the LangGraph Risk Investigation Agent on the requested transaction."""
    try:
        service = RiskInvestigationService(db)
        report = service.investigate_transaction(transaction_id, analyst_notes=analyst_notes)
        return report
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ve),
        )
    except Exception as e:
        logger.error("AI Investigation failed for %s: %s", transaction_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed: {str(e)}",
        )


@router.get(
    "/investigate/{investigation_id}/audit",
    response_model=AuditLogRecord,
    status_code=status.HTTP_200_OK,
    summary="Retrieve immutable audit log for an AI investigation",
)
def get_investigation_audit_log(
    investigation_id: str,
) -> AuditLogRecord:
    """Retrieves the full execution audit record for a given investigation ID."""
    audit_logger = get_global_audit_logger()
    record = audit_logger.get_record(investigation_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit record for investigation '{investigation_id}' not found.",
        )
    return record

