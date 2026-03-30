"""
Pydantic data model for a single asteroid record.

Represents the columns available after the ingest stage.
Optional fields (diameter_km, rotation_hours, albedo) are sparse
in the SBDB catalog — most asteroids lack these measurements.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AsteroidRecord(BaseModel):
    """One row of the ingested SBDB catalog."""

    model_config = ConfigDict(extra="forbid")

    spkid: int = Field(..., description="JPL Small-Body Kinetic ID")
    name: str = Field(..., description="Full asteroid designation")
    a_au: float = Field(..., description="Semi-major axis (AU)")
    eccentricity: float = Field(..., description="Orbital eccentricity, in [0, 1)")
    inclination_deg: float = Field(..., description="Orbital inclination (degrees)")
    diameter_km: float | None = Field(None, description="Estimated diameter (km) — sparse")
    rotation_hours: float | None = Field(None, description="Rotation period (hours) — sparse")
    albedo: float | None = Field(None, description="Geometric albedo in [0, 1] — sparse")
