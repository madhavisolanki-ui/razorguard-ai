"""Audit Trail Recording for Agentic AI Investigations."""

from typing import Dict, Any, List, Optional
import datetime
from src.agent.schemas import AuditLogRecord, ToolCallRecord
from src.core.logging import get_logger

logger = get_logger("agent_audit")


class InvestigationAuditLogger:
    """In-memory and structured audit logger for AI risk investigations."""

    def __init__(self):
        self._audit_log: List[AuditLogRecord] = []

    def record_investigation(
        self,
        investigation_id: str,
        transaction_id: str,
        deterministic_inputs: Dict[str, Any],
        tools_executed: List[ToolCallRecord],
        investigation_path: List[str],
        final_verdict: Dict[str, Any],
        fallback_invoked: bool = False,
    ) -> AuditLogRecord:
        """Records an auditable trace of an AI investigation."""
        record = AuditLogRecord(
            investigation_id=investigation_id,
            transaction_id=transaction_id,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            deterministic_inputs=deterministic_inputs,
            tools_executed=tools_executed,
            investigation_path=investigation_path,
            final_verdict=final_verdict,
            fallback_invoked=fallback_invoked,
        )
        self._audit_log.append(record)
        logger.info(
            "Investigation recorded: ID=%s, Tx=%s, Action=%s, Fallback=%s, Tools=%d",
            investigation_id,
            transaction_id,
            final_verdict.get("recommended_action"),
            fallback_invoked,
            len(tools_executed),
        )
        return record

    def get_record(self, investigation_id: str) -> Optional[AuditLogRecord]:
        """Retrieves an audit record by investigation ID."""
        for r in self._audit_log:
            if r.investigation_id == investigation_id:
                return r
        return None

    def get_records_for_transaction(self, transaction_id: str) -> List[AuditLogRecord]:
        """Retrieves all audit records for a given transaction."""
        return [r for r in self._audit_log if r.transaction_id == transaction_id]


_GLOBAL_AUDIT_LOGGER = InvestigationAuditLogger()


def get_global_audit_logger() -> InvestigationAuditLogger:
    """Returns singleton audit logger."""
    return _GLOBAL_AUDIT_LOGGER
