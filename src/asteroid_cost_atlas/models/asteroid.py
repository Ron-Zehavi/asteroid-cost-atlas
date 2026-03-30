"""
Pydantic data model for a single asteroid record.

Represents the columns available after the ingest stage.
Optional fields are sparse in the SBDB catalog — most asteroids
only have orbital elements and absolute magnitude.
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
    abs_magnitude: float | None = Field(None, description="Absolute magnitude H")
    magnitude_slope: float | None = Field(None, description="Magnitude slope parameter G")
    diameter_km: float | None = Field(None, description="Measured diameter (km) — sparse")
    rotation_hours: float | None = Field(None, description="Rotation period (hours) — sparse")
    albedo: float | None = Field(None, description="Geometric albedo in [0, 1] — sparse")
    neo: str | None = Field(None, description="Near-Earth Object flag (Y/N)")
    pha: str | None = Field(None, description="Potentially Hazardous Asteroid flag (Y/N)")
    orbit_class: str | None = Field(None, description="Orbit classification (APO, ATE, AMO, etc.)")
    moid_au: float | None = Field(None, description="Earth MOID (AU)")
    spectral_type: str | None = Field(None, description="SMASSII spectral taxonomy — sparse")
