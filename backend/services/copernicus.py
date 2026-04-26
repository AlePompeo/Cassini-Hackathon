"""Mock Copernicus Dataspace API client.

In production, this module would use the Copernicus Dataspace STAC API
(https://dataspace.copernicus.eu/) with OAuth2 credentials to search for and
download Sentinel-1/2 scenes.

For the hackathon demo, it returns synthetic band arrays that simulate a
realistic polluted scene (oil slick + algal bloom) without requiring
authentication.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from exceptions import DataSourceError
from models.pollution_event import BoundingBox


class CopernicusClient:
    """Client for the Copernicus Dataspace catalogue and download API.

    Attributes:
        username: Copernicus Dataspace account username.
        password: Copernicus Dataspace account password.
    """

    def __init__(
        self,
        username: str = "demo",
        password: str = "demo",
    ) -> None:
        self.username = username
        self.password = password
        self._authenticated = False

    def search_sentinel2(
        self,
        aoi: BoundingBox,
        start_date: datetime,
        end_date: datetime,
        cloud_cover_max: float = 20.0,
    ) -> list[dict]:
        """Search for Sentinel-2 L2A products covering the AOI.

        Args:
            aoi: Geographic bounding box.
            start_date: Start of the search window (UTC).
            end_date: End of the search window (UTC).
            cloud_cover_max: Maximum acceptable cloud cover percentage.

        Returns:
            List of product metadata dicts with keys: id, title, date,
            cloud_cover, platform, bbox.
        """
        # Demo: return synthetic product metadata for the AOI
        return [
            {
                "id": "S2A_MSIL2A_20240315T095031_demo_01",
                "title": "Sentinel-2A L2A Demo Scene",
                "date": start_date.isoformat(),
                "cloud_cover": 8.2,
                "platform": "Sentinel-2A",
                "bbox": [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
            },
            {
                "id": "S2B_MSIL2A_20240320T095031_demo_02",
                "title": "Sentinel-2B L2A Demo Scene",
                "date": end_date.isoformat(),
                "cloud_cover": 3.5,
                "platform": "Sentinel-2B",
                "bbox": [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
            },
        ]

    def search_sentinel1(
        self,
        aoi: BoundingBox,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """Search for Sentinel-1 GRD IW products covering the AOI.

        Args:
            aoi: Geographic bounding box.
            start_date: Start of the search window.
            end_date: End of the search window.

        Returns:
            List of product metadata dicts.
        """
        return [
            {
                "id": "S1A_IW_GRDH_20240315T052312_demo_01",
                "title": "Sentinel-1A IW GRDH Demo",
                "date": start_date.isoformat(),
                "polarisation": "VV,VH",
                "platform": "Sentinel-1A",
                "bbox": [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
            }
        ]

    def get_sample_sentinel2_bands(
        self,
        scene_id: str,
        size: int = 256,
        rng_seed: int = 7,
    ) -> dict[str, np.ndarray]:
        """Return synthetic Sentinel-2 band arrays simulating a polluted scene.

        The synthetic scene contains:
        - A background water reflectance spectrum (low NIR, low visible)
        - An oil slick patch in the upper-left quadrant (elevated VNRI ~0.25)
        - An algal bloom region in the lower-right quadrant (elevated MCI ~0.015)

        Args:
            scene_id: Product identifier (ignored; all return same synthetic scene).
            size: Width and height of the returned arrays in pixels.
            rng_seed: NumPy RNG seed for reproducibility.

        Returns:
            Dictionary with keys 'B03', 'B04', 'B05', 'B06' each containing
            a (size, size) float32 reflectance array in [0, 1].
        """
        rng = np.random.default_rng(rng_seed)

        # --- Background: calm sea water ---
        b03 = rng.normal(0.030, 0.003, (size, size)).astype(np.float32)
        b04 = rng.normal(0.020, 0.002, (size, size)).astype(np.float32)
        b05 = rng.normal(0.015, 0.002, (size, size)).astype(np.float32)
        b06 = rng.normal(0.010, 0.001, (size, size)).astype(np.float32)

        # --- Oil slick: upper-left quadrant (row 20-100, col 20-110) ---
        # Oil raises green and red-edge reflectance → high VNRI
        oil_r = slice(20, 100)
        oil_c = slice(20, 110)
        b03[oil_r, oil_c] += rng.normal(0.045, 0.005, (80, 90))
        b04[oil_r, oil_c] -= rng.normal(0.005, 0.001, (80, 90))
        b06[oil_r, oil_c] += rng.normal(0.030, 0.004, (80, 90))

        # --- Algal bloom: lower-right quadrant (row 150-230, col 140-220) ---
        # Bloom raises B05 (705 nm) relative to B04 and B06 → high MCI
        bloom_r = slice(150, 230)
        bloom_c = slice(140, 220)
        b05[bloom_r, bloom_c] += rng.normal(0.025, 0.004, (80, 80))
        b04[bloom_r, bloom_c] += rng.normal(0.005, 0.001, (80, 80))
        b06[bloom_r, bloom_c] += rng.normal(0.010, 0.002, (80, 80))

        # Clip to physically plausible range
        for arr in (b03, b04, b05, b06):
            np.clip(arr, 0.0, 1.0, out=arr)

        return {"B03": b03, "B04": b04, "B05": b05, "B06": b06}

    def get_sample_sar_scene(
        self,
        scene_id: str,
        size: int = 256,
        rng_seed: int = 13,
    ) -> np.ndarray:
        """Return a synthetic Sentinel-1 sigma-naught image in dB.

        Background ocean at -10 to -15 dB (moderate wind). Oil patch regions
        at -22 to -26 dB (anomalously dark).

        Args:
            scene_id: Product identifier (unused).
            size: Width and height of the SAR scene in pixels.
            rng_seed: RNG seed for reproducibility.

        Returns:
            2-D float32 array of sigma-naught in dB.
        """
        rng = np.random.default_rng(rng_seed)

        # Rough sea background
        sigma0_db = rng.normal(-12.0, 2.5, (size, size)).astype(np.float32)

        # Oil slick 1: elongated patch, typical of tanker discharge
        sigma0_db[30:90, 40:130] = rng.normal(-23.0, 1.5, (60, 90))

        # Oil slick 2: smaller circular spill
        for i in range(170, 210):
            for j in range(160, 200):
                if (i - 190) ** 2 + (j - 180) ** 2 < 400:
                    sigma0_db[i, j] = rng.normal(-24.5, 1.0)

        return sigma0_db
