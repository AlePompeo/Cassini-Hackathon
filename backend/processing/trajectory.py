"""Lagrangian particle tracking for oil spill trajectory forecasting.

Implements a simplified GNOME-like (General NOAA Operational Modeling
Environment) Lagrangian transport model. Particles are advected by a
combination of surface currents, wind drift, and random Brownian diffusion.

Wind drift: 3% of wind speed at surface (empirically established for
floating oil in moderate sea states).

Diffusion coefficient: ~1.0 m²/s for coastal zones (GNOME default ~10⁴ cm²/s).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from exceptions import ModelError

# Degrees-to-metres conversion at equator
_M_PER_DEG_LAT = 111_320.0
_WIND_DRIFT_FACTOR = 0.03  # 3% of wind speed contributes to surface transport


@dataclass
class TrajectoryResult:
    """Output from a Lagrangian tracking run.

    Attributes:
        particles_lon: Shape (n_particles, n_timesteps). Longitude of each
            particle at each time step.
        particles_lat: Shape (n_particles, n_timesteps). Latitude of each
            particle at each time step.
        timesteps: UTC datetime for each column.
        uncertainty_radius_km: Per-timestep radius (km) of the 1-sigma
            uncertainty ellipse.
    """

    particles_lon: np.ndarray
    particles_lat: np.ndarray
    timesteps: list[datetime]
    uncertainty_radius_km: list[float]

    @property
    def n_particles(self) -> int:
        return self.particles_lon.shape[0]

    @property
    def n_timesteps(self) -> int:
        return self.particles_lon.shape[1]

    def centroid_at(self, step: int) -> tuple[float, float]:
        """Return (lon, lat) centroid of all particles at a given time step."""
        return (
            float(self.particles_lon[:, step].mean()),
            float(self.particles_lat[:, step].mean()),
        )


class LagrangianTracker:
    """Vectorised Lagrangian particle tracker for surface oil transport.

    Uses numpy array operations over all particles simultaneously; no
    Python-level per-particle loops.

    Example::

        tracker = LagrangianTracker()
        result = tracker.run(
            spill_lon=14.5, spill_lat=43.2,
            u_wind=5.0, v_wind=2.0,
            u_current=0.2, v_current=0.1,
            duration_hours=48,
            n_particles=200,
        )
    """

    def __init__(self, rng_seed: int | None = 42) -> None:
        self._rng = np.random.default_rng(rng_seed)

    def run(
        self,
        spill_lon: float,
        spill_lat: float,
        u_wind: float,
        v_wind: float,
        u_current: float,
        v_current: float,
        duration_hours: int = 48,
        n_particles: int = 200,
        diffusion_coeff: float = 1.0,
        dt_hours: float = 1.0,
        start_time: datetime | None = None,
    ) -> TrajectoryResult:
        """Run the Lagrangian trajectory simulation.

        Particle update per time step dt:
            dx = (wind_factor*u_wind + u_current) * dt + random_walk_x
            dy = (wind_factor*v_wind + v_current) * dt + random_walk_y
        where random_walk ~ N(0, sqrt(2 * D * dt)).

        Args:
            spill_lon: Initial spill longitude (decimal degrees).
            spill_lat: Initial spill latitude (decimal degrees).
            u_wind: Eastward wind component (m/s).
            v_wind: Northward wind component (m/s).
            u_current: Eastward surface current (m/s).
            v_current: Northward surface current (m/s).
            duration_hours: Forecast horizon in hours.
            n_particles: Number of Lagrangian particles.
            diffusion_coeff: Horizontal diffusion coefficient (m²/s).
            dt_hours: Integration time step (hours).
            start_time: UTC start time; defaults to current UTC time.

        Returns:
            TrajectoryResult with particle positions and uncertainty radii.

        Raises:
            ModelError: If simulation parameters are out of valid range.
        """
        if duration_hours <= 0:
            raise ModelError("duration_hours must be positive.")
        if n_particles < 1:
            raise ModelError("n_particles must be at least 1.")
        if diffusion_coeff < 0:
            raise ModelError("diffusion_coeff must be non-negative.")

        if start_time is None:
            start_time = datetime.utcnow()

        dt_s = dt_hours * 3600.0  # seconds per step
        n_steps = int(math.ceil(duration_hours / dt_hours)) + 1

        # m/deg conversion (latitude-dependent for longitude)
        m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(spill_lat))

        # Effective velocity components (m/s)
        u_total = _WIND_DRIFT_FACTOR * u_wind + u_current
        v_total = _WIND_DRIFT_FACTOR * v_wind + v_current

        # Deterministic displacement per step (in degrees)
        d_lon_step = (u_total * dt_s) / m_per_deg_lon
        d_lat_step = (v_total * dt_s) / _M_PER_DEG_LAT

        # Diffusion standard deviation per step (in metres → degrees)
        sigma_m = math.sqrt(2.0 * diffusion_coeff * dt_s)
        sigma_lon = sigma_m / m_per_deg_lon
        sigma_lat = sigma_m / _M_PER_DEG_LAT

        # Initialise all particles at spill origin
        lons = np.full((n_particles, n_steps), spill_lon, dtype=np.float64)
        lats = np.full((n_particles, n_steps), spill_lat, dtype=np.float64)

        timesteps: list[datetime] = []
        uncertainty_km: list[float] = []

        for step in range(n_steps):
            t = start_time + timedelta(hours=step * dt_hours)
            timesteps.append(t)

            # Uncertainty radius = std of particle cloud
            if step == 0:
                uncertainty_km.append(0.0)
            else:
                spread_lon = lons[:, step].std() * m_per_deg_lon / 1000.0
                spread_lat = lats[:, step].std() * _M_PER_DEG_LAT / 1000.0
                uncertainty_km.append(float(math.sqrt(spread_lon**2 + spread_lat**2)))

            if step < n_steps - 1:
                noise_lon = self._rng.normal(0.0, sigma_lon, n_particles)
                noise_lat = self._rng.normal(0.0, sigma_lat, n_particles)
                lons[:, step + 1] = lons[:, step] + d_lon_step + noise_lon
                lats[:, step + 1] = lats[:, step] + d_lat_step + noise_lat

        return TrajectoryResult(
            particles_lon=lons,
            particles_lat=lats,
            timesteps=timesteps,
            uncertainty_radius_km=uncertainty_km,
        )
