from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TicketLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: str = Field(index=True)
    title: str
    module_name: Optional[str] = None
    risk_level: Optional[str] = None
    artifact: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    # processing | done | error | needs_approval
    status: str
    dry_run: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
