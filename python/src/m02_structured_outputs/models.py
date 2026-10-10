"""Pydantic v2 domain schemas used for structured output extraction."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComponentRisk(BaseModel):
    """Specific architectural or security risk item."""
    model_config = ConfigDict(extra="forbid")

    component_name: str = Field(description="Name of the affected service or subsystem.")
    risk_level: RiskLevel = Field(description="Categorical risk rating.")
    description: str = Field(description="Clear explanation of the failure mode or vulnerability.")
    mitigation_strategy: str = Field(description="Concrete engineering fix.")


class SystemArchitectureSpec(BaseModel):
    """Structured architectural review payload.
    
    NOTE: 'extra = forbid' generates 'additionalProperties: false' in the JSON Schema,
    which is an absolute prerequisite for OpenAI Strict Structured Outputs!
    """
    model_config = ConfigDict(extra="forbid")

    system_name: str = Field(description="Official name of the architecture or service.")
    estimated_monthly_tco_usd: float = Field(description="Total cost of ownership estimation in USD.")
    scalability_rating_1_to_10: int = Field(ge=1, le=10, description="Scale of 1-10.")
    risks: List[ComponentRisk] = Field(description="Identified architectural risks.")
    recommended_patterns: List[str] = Field(description="Resilience and architecture patterns to adopt.")

