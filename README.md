🐝 WASP — Water Analysis Satellite Program
> **Real-time Mediterranean pollution monitoring** via satellite imagery, smart IoT buoys, and an AI-powered dashboard.  
> Built for [Cassini Hackathon #2](https://github.com/cassinihackathons) · April 2026
---
What is WASP?
WASP (branded AquaGuard) is a SaaS platform that detects, classifies, and forecasts marine pollution across the Mediterranean in real time. It fuses three data sources that have never been combined in a single operational product:
Sentinel-1 SAR — detects oil slicks day and night, through clouds
Sentinel-2 optical — identifies algal blooms and hydrocarbons via spectral indices (MCI, VNRI, OSI)
Smart IoT buoys — surface-level water quality sensors transmitting every 15 minutes over the Kinéis LEO satellite network
The result is a unified alert dashboard used by coast guards, port authorities, municipalities, NGOs, and maritime insurers.
---
Architecture
```
Copernicus Dataspace (Sentinel-1 / Sentinel-2)
        │
        ▼
CopernicusClient → SAR + optical processing pipelines
        │
        ├── processing/sentinel1.py   →  oil spill mask (SAR backscatter)
        └── processing/sentinel2.py   →  MCI / VNRI / OSI indices
                    │
                    ▼
            PollutionEvent (Pydantic)
                    │
                    ├── Alert (HIGH / CRITICAL events)
                    │
                    └── LagrangianTracker → 48h trajectory forecast
                                │
                                ▼
                    Frontend — Leaflet map + alert panel

IoT Buoys (ESP32 + Kinéis KIM1)
        │  24-byte packet over LEO satellite
        ▼
POST /api/iot/kineis/uplink → decoder → BuoyTelemetry → app_state
```
---
Repository layout
```
Cassini-Hackathon/
├── aquaguard/
│   ├── iot/
│   │   ├── firmware/buoy_main/       # ESP32 sketch — sensors, Kinéis modem, packet codec
│   │   └── simulator/buoy_simulator.py
│   ├── backend/                      # Python FastAPI
│   │   ├── api/                      # 5 routers: detection, trajectory, alerts, buoys, IoT webhook
│   │   ├── models/                   # Pydantic v2 — PollutionEvent, Alert, BuoyTelemetry
│   │   ├── processing/               # Sentinel-1 SAR, Sentinel-2 optical, Lagrangian tracker
│   │   ├── services/copernicus.py    # Copernicus Dataspace STAC client
│   │   └── demo/sample_data.py       # Synthetic Mediterranean events for demo mode
│   ├── frontend/                     # Vanilla JS + Leaflet — no build step
│   │   ├── index.html
│   │   ├── css/style.css
│   │   └── js/  map.js · alerts.js · main.js
│   └── simulation/                   # Standalone MATLAB pitch visuals
│       ├── oil_spill_trajectory.m    # 48h Lagrangian particle tracking, Adriatic Sea
│       └── visualize_indices.m       # MCI / VNRI / OSI synthetic band maps
└── CLAUDE.md
```
---
Getting started
Backend
```bash
cd aquaguard/backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Swagger UI → `http://localhost:8000/docs`
On startup the server seeds 20 synthetic Mediterranean events and alerts into memory.
Frontend
Open `aquaguard/frontend/index.html` directly in any browser — no build step, no server needed. It polls the backend every 30–60 s and falls back to demo mode automatically if the backend is offline.
MATLAB simulations
```matlab
cd aquaguard/simulation
run('oil_spill_trajectory.m')   % → oil_spill_forecast.png
run('visualize_indices.m')      % → sentinel2_indices.png
```
No toolboxes required beyond the base MATLAB installation.
IoT buoy simulator
```bash
cd aquaguard/iot/simulator
python buoy_simulator.py --buoys 3 --interval 15
python buoy_simulator.py --buoys 3 --once --oil-event   # one-shot with spill event
```
---
API reference
Detection & trajectory
Method	Endpoint	Description
`GET`	`/`	Health check + version
`GET`	`/api/status`	Dashboard stats
`POST`	`/api/detection/analyze`	Trigger Sentinel-1/2 analysis over a bounding box
`GET`	`/api/detection/events`	List events — filter by `event_type`, `severity`, `limit`
`GET`	`/api/detection/events/{id}`	Single event by UUID
`POST`	`/api/trajectory/predict`	Lagrangian forecast from lat/lon + wind/current
`POST`	`/api/trajectory/predict/{event_id}`	Forecast for a known event (48h default)
`GET`	`/api/trajectory/horizons/{event_id}`	Multi-horizon: 2h / 4h / 6h / 24h / 48h in one call
Alerts & subscriptions
Method	Endpoint	Description
`GET`	`/api/alerts/`	Recent alerts, newest first
`POST`	`/api/alerts/subscribe`	Subscribe by zone + severity via email / webhook
`GET`	`/api/alerts/zones`	10 Mediterranean monitoring zones
IoT buoys
Method	Endpoint	Description
`POST`	`/api/iot/kineis/uplink`	Kinéis webhook — receives buoy uplinks
`GET`	`/api/buoys/`	Fleet list with aggregated health
`GET`	`/api/buoys/{buoy_id}`	Single buoy status + last readings
`GET`	`/api/buoys/{buoy_id}/history`	Telemetry history (`limit` param)
---
What the buoy measures
Sensor	Why it matters
Oil film (optical)	Detects surface hydrocarbon films invisible to the naked eye
UV fluorescence	Identifies dissolved aromatic hydrocarbons below the surface
Turbidity	Flags illegal dredging spoil, industrial discharge, early bloom onset
pH	Detects chemical spills and mass algal metabolism shifts
Dissolved oxygen	Early warning for dead zones before fish kill events
Water temperature	Identifies thermal discharge and bloom-favorable conditions
GPS (Galileo)	Every reading is geolocated to metre-level accuracy
Each reading is packed into a 24-byte packet (CRC-16/CCITT), transmitted via the Kinéis KIM1 modem over LEO satellite, and decoded by the backend webhook.
---
Science behind the detection
Every algorithm is grounded in peer-reviewed literature validated on real incidents.
Method	Validation case	Source
SAR oil detection (Sentinel-1 backscatter −22 to −26 dB)	Hebei Spirit tanker spill, Yellow Sea	Wu Dan et al., 2024
Dual MCI / VNRI spectral indices	ENI crude spill + bloom, Lake Pertusillo 2017	Laneve et al., 2022 — Remote Sensing MDPI
Oil Slope Index (spectral slope 550–750 nm)	Deepwater Horizon, Gulf of Mexico 2010	Li et al., 2012 — Chinese Academy of Sciences
Lagrangian trajectory (GNOME methodology)	Oil spill reconstruction, Gulf of Naples	Trainiti et al., 2024 — IEEE / Università Parthenope
Integrated observing framework	IMDOS global marine debris system	Maximenko et al., 2021 — Oceanography
---
Monitoring zones (default)
Zone	Primary threat
Strait of Sicily	Tanker routes — highest spill frequency in the Med
Gulf of Naples	Industrial discharge, port traffic
Northern Adriatic	Chronic eutrophication — Po River agricultural runoff
Southern Adriatic	International shipping lane crossings
Aegean Sea	Turkish and Greek port tanker traffic
Cyclades	Mass tourism, cruise shipping
Tyrrhenian Sea	Rome–Naples–Palermo petroleum corridor
Balearic Sea	Main Europe–Africa shipping corridor
Levantine Basin	Offshore oil extraction (Israel, Cyprus, Lebanon)
Gulf of Lion	Rhône river runoff — agricultural residue and plastics
---
Roadmap
```
Phase 1 — Production backend
  ☐ Real Copernicus STAC API (OAuth2) replacing mock client
  ☐ PostgreSQL persistence — events, alerts, subscriptions
  ☐ CMEMS ocean current forecasts for trajectory
  ☐ AIS vessel tracking — identify probable spill sources

Phase 2 — Alert delivery
  ☐ Email (SendGrid), webhook push, SMS (Twilio)

Phase 3 — IoT at sea
  ☐ First physical buoy deployment at a pilot port
  ☐ Buoy health monitoring dashboard

Phase 4 — AI / ML
  ☐ CNN classifier trained on MADOS dataset (replacing threshold logic)
  ☐ Harmful algal bloom toxin early warning
  ☐ Digital twin — simulate boom deployment and dispersant coverage
```
---
Known limitations (demo version)
Limitation	Production fix
`CopernicusClient` is a mock — no real satellite data	Real STAC API + OAuth2
In-memory `app_state` resets on restart	PostgreSQL
Sentinel-2 bands are 256×256 synthetic arrays	Real L2A downloads
Trajectory uses constant wind/current	CMEMS time-varying forcing
CORS `allow_origins=["*"]`	API key / JWT
`/horizons` runs 5 sequential simulations	Vectorise across horizons
---
Team
Name	Background
Chiara	RF & antenna systems, network/database, space & defence electronics
Alessio	Computer science, robotics, GNC, satellite architectures
Priscilla	Network/database, geoinformation, satellite remote sensing, software
Caterina	Business administration, banking, international economics, strategy
---
Resources
MADOS dataset — marine pollution segmentation for ML training
OpenEO oil spill notebook — Sentinel-1/2 via Copernicus Dataspace
Copernicus Dataspace
Kinéis IoT-LEO
Cassini Hackathon
---
AquaGuard — WASP · Cassini Hackathon #2 · April 2026
