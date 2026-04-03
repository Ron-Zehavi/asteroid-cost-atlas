"""Pydantic models for API request validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Columns allowed for sorting in /api/asteroids
SORTABLE_COLUMNS = frozenset({
    "economic_priority_rank", "delta_v_km_s", "campaign_profit_usd",
    "mission_profit_usd", "total_precious_value_usd", "estimated_mass_kg",
    "diameter_estimated_km", "surface_gravity_m_s2", "margin_per_kg",
    "break_even_kg", "missions_supported", "a_au", "eccentricity",
    "inclination_deg", "moid_au", "tisserand_jupiter", "name",
})

# Columns allowed for filtering
COMPOSITION_CLASSES = frozenset({"C", "S", "M", "V", "U"})


class AsteroidQuery(BaseModel):
    """Query parameters for the paginated asteroid list."""

    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    sort: str = Field("economic_priority_rank")
    order: str = Field("asc")
    neo: str | None = None
    is_viable: bool | None = None
    composition_class: str | None = None
    orbit_class: str | None = None
    dv_min: float | None = Field(None, ge=0)
    dv_max: float | None = Field(None, ge=0)
    rank_max: int | None = Field(None, ge=1)
