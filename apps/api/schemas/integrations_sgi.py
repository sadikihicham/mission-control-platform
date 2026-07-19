"""DTO du webhook entrant SGI (ADR-0011)."""
from pydantic import BaseModel


class SubscriptionEventIn(BaseModel):
    company_id: str
    activity_key: str
    enabled: bool
