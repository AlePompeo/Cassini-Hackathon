# WASP — Water Analysis Satellite Program

> **Real-time Mediterranean pollution monitoring** via satellite imagery, smart IoT buoys, and an AI-powered dashboard.
> Built for [Cassini Hackathon #2](https://www.cassini.eu/hackathons) · April 2026

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-AGPL--3.0-red?logo=gnu)
![Arduino](https://img.shields.io/badge/Firmware-Arduino%20%2F%20ESP32-00979D?logo=arduino&logoColor=white)
![Copernicus](https://img.shields.io/badge/Data-Copernicus%20Sentinel--1%2F2-003247?logo=esa)

---

## What is WASP?

WASP (branded **AquaGuard**) is a SaaS platform that detects, classifies, and forecasts marine pollution across the Mediterranean in real time. It fuses three data sources that have never been combined in a single operational product:

| Source | What it detects |
|---|---|
| **Sentinel-1 SAR** | Oil slicks — day and night, through clouds |
| **Sentinel-2 optical** | Algal blooms and hydrocarbons via MCI, VNRI, OSI spectral indices |
| **Smart IoT buoys** | Surface-level water quality, transmitting every 15 min over the Kinéis LEO satellite network |

The result is a unified alert dashboard targeting coast guards, port authorities, municipalities, environmental NGOs, and maritime insurers.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  Copernicus Dataspace                        │
│            (Sentinel-1 SAR + Sentinel-2 optical)            │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
              CopernicusClient (services/copernicus.py)
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
 processing/sentinel1.py    processing/sentinel2.py
 Lee filter → dark spot     MCI / VNRI / OSI indices
 detection → area estimate  → bloom / hydrocarbon mask
          │                           │
          └─────────────┬─────────────┘
                        ▼
               PollutionEvent (Pydantic v2)
                        │
          ┌─────────────┴────────────────┐
          ▼                              ▼
   Alert (HIGH / CRITICAL)     LagrangianTracker
                                48-h trajectory forecast
                        │
                        ▼
          Frontend — Leaflet map + alert panel
                (polls backend every 30–60 s)

┌──────────────────────────────────────────────────────────────┐
│  IoT Smart Buoy (ESP32 + Kinéis KIM1)                       │
│  sensors → 24-byte CRC-16 packet → LEO satellite uplink     │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
       POST /api/iot/kineis/uplink
       → decoder → BuoyTelemetry → app_state
```

---

## Repository Structure

```
Cassini-Hackathon/
├── backend/                        # Python FastAPI server
│   ├── main.py                     # App entry point, startup seeding
│   ├── state.py                    # Shared in-memory store
│   ├── exceptions.py               # Domain exceptions
│   ├── requirements.txt
│   ├── api/                        # Route handlers
│   │   ├── detection.py            # Trigger analysis, list events
│   │   ├── trajectory.py           # Lagrangian forecast
│   │   ├── alerts.py               # Alert list + subscriptions
│   │   ├── buoys.py                # Buoy fleet status
│   │   └── kineis_webhook.py       # Kinéis satellite uplink receiver
│   ├── models/                     # Pydantic v2 schemas
│   │   ├── pollution_event.py      # PollutionEvent, EventType, Severity
│   │   ├── alert.py                # Alert, AlertZone
│   │   └── buoy.py                 # BuoyTelemetry, BuoyStatus
│   ├── processing/                 # Signal processing pipelines
│   │   ├── sentinel1.py            # SAR backscatter → oil spill mask
│   │   ├── sentinel2.py            # Spectral indices (MCI / VNRI / OSI)
│   │   └── trajectory.py           # Lagrangian particle tracker
│   ├── services/
│   │   └── copernicus.py           # Copernicus Dataspace STAC client
│   └── demo/
│       └── sample_data.py          # Synthetic Mediterranean events for demo mode
│
├── frontend/                       # Vanilla JS + Leaflet — no build step
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── main.js                 # App bootstrap, polling loop
│       ├── map.js                  # Leaflet map, event markers
│       └── alerts.js               # Alert panel rendering
│
├── iot/
│   ├── firmware/buoy_main/         # ESP32 Arduino sketch
│   │   ├── buoy_main.ino           # Main loop: sleep → wake → read → transmit
│   │   ├── config.h                # Pin map, thresholds, timing constants
│   │   ├── sensors.h/cpp           # ADC reads, DS18B20, pH, turbidity, DO, UV
│   │   ├── kineis.h/cpp            # KIM1 AT-command driver (UART)
│   │   ├── packet.h/cpp            # 24-byte packet encoder / CRC-16
│   │   └── power.h/cpp             # Deep-sleep scheduler, battery management
│   └── simulator/
│       └── buoy_simulator.py       # Software buoy — posts synthetic telemetry to backend
│
├── simulation/                     # Standalone MATLAB scripts
│   ├── oil_spill_trajectory.m      # 48-h Lagrangian particle tracking, Adriatic Sea
│   └── visualize_indices.m         # MCI / VNRI / OSI synthetic band visualizations
│
└── LICENSE                         # GNU AGPL v3
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- A modern browser (frontend requires no build step)
- MATLAB R2022b+ (optional, for simulations)
- Arduino IDE 2.x + ESP32 board package (optional, for firmware)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On startup the server seeds **20 synthetic Mediterranean pollution events** and alerts into memory. Interactive API docs are available at:

- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

### Frontend

Open `frontend/index.html` directly in any browser — no build step, no server needed. It polls the backend every 30–60 s and falls back to demo mode automatically if the backend is offline.

### IoT Buoy Simulator

```bash
cd iot/simulator

# Simulate 3 buoys transmitting every 15 minutes
python buoy_simulator.py --buoys 3 --interval 15

# One-shot transmission with an oil-spill event
python buoy_simulator.py --buoys 3 --once --oil-event
```

### MATLAB Simulations

```matlab
cd simulation
run('oil_spill_trajectory.m')   % → oil_spill_forecast.png
run('visualize_indices.m')      % → sentinel2_indices.png
```

No additional toolboxes required beyond the base MATLAB installation.

---

## API Reference

### Detection & Trajectory

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check + version |
| `GET` | `/api/status` | Dashboard summary statistics |
| `POST` | `/api/detection/analyze` | Trigger Sentinel-1/2 analysis over a bounding box |
| `GET` | `/api/detection/events` | List events — filter by `event_type`, `severity`, `limit` |
| `GET` | `/api/detection/events/{id}` | Single event by UUID |
| `POST` | `/api/trajectory/predict` | Lagrangian forecast from lat/lon + wind/current |
| `POST` | `/api/trajectory/predict/{event_id}` | Forecast for a known event (48 h default) |
| `GET` | `/api/trajectory/horizons/{event_id}` | Multi-horizon: 2h / 4h / 6h / 24h / 48h in one call |

### Alerts & Subscriptions

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/alerts/` | Recent alerts, newest first |
| `POST` | `/api/alerts/subscribe` | Subscribe by zone + severity via email / webhook |
| `GET` | `/api/alerts/zones` | 10 Mediterranean monitoring zones |

### IoT Buoys

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/iot/kineis/uplink` | Kinéis webhook — receives buoy satellite uplinks |
| `GET` | `/api/buoys/` | Fleet list with aggregated health |
| `GET` | `/api/buoys/{buoy_id}` | Single buoy status + last readings |
| `GET` | `/api/buoys/{buoy_id}/history` | Telemetry history (`limit` param) |

---

## IoT Buoy — Hardware & Firmware

### Sensors

| Sensor | Parameter | Why it matters |
|---|---|---|
| Resistive oil film | Surface hydrocarbon film | Detects slicks invisible to the naked eye |
| UV fluorescence photodiode | Dissolved aromatics | Identifies sub-surface hydrocarbons |
| Optical turbidity | NTU | Illegal dredging, industrial discharge, early bloom onset |
| Analog pH electrode | pH 0–14 | Chemical spills, algal metabolism shifts |
| Dissolved oxygen (analog) | mg/L | Early warning for dead zones before fish kills |
| DS18B20 (1-Wire) | Water temperature °C | Thermal discharge, bloom-favorable conditions |
| GPS (NMEA 0183, Galileo) | Latitude / Longitude | Metre-level geolocation on every reading |

All readings are packed into a **24-byte CRC-16/CCITT packet** and transmitted via the **Kinéis KIM1 modem** over LEO satellite.

### ESP32 Pin Map

| Pin | Function |
|---|---|
| GPIO 34 | Oil film sensor (ADC1_CH6) |
| GPIO 35 | UV fluorescence (ADC1_CH7) |
| GPIO 32 | Turbidity (ADC1_CH4) |
| GPIO 33 | pH electrode (ADC1_CH5) |
| GPIO 36 | Dissolved oxygen (ADC1_CH0 / VP) |
| GPIO 4 | DS18B20 temperature (1-Wire) |
| GPIO 17 / 16 | Kinéis KIM1 UART TX / RX |
| GPIO 25 / 26 | GPS UART TX / RX |
| GPIO 5 | Kinéis module power enable |
| GPIO 18 | GPS module power enable |
| GPIO 39 | Battery voltage divider |

### Transmission Schedule

| Mode | Interval |
|---|---|
| Normal | Every 15 minutes |
| Alert active | Every 2 minutes |
| Low battery | Every 60 minutes |
| Critical battery | Emergency deep sleep (4 h) |

---

## Detection Science

Every algorithm is grounded in peer-reviewed literature validated on real incidents.

| Method | Validation case | Source |
|---|---|---|
| SAR oil detection (Sentinel-1 σ° −22 to −26 dB) | Hebei Spirit tanker spill, Yellow Sea | Wu Dan et al., 2024 |
| Dual MCI / VNRI spectral indices | ENI crude spill + bloom, Lake Pertusillo 2017 | Laneve et al., 2022 — *Remote Sensing* MDPI |
| Oil Slope Index (spectral slope 550–750 nm) | Deepwater Horizon, Gulf of Mexico 2010 | Li et al., 2012 — Chinese Academy of Sciences |
| Lagrangian trajectory (GNOME methodology) | Oil spill reconstruction, Gulf of Naples | Trainiti et al., 2024 — IEEE / Università Parthenope |
| Integrated observing framework | IMDOS global marine debris system | Maximenko et al., 2021 — *Oceanography* |

---

## Monitoring Zones

| Zone | Primary threat |
|---|---|
| Strait of Sicily | Tanker routes — highest spill frequency in the Med |
| Gulf of Naples | Industrial discharge, port traffic |
| Northern Adriatic | Chronic eutrophication — Po River agricultural runoff |
| Southern Adriatic | International shipping lane crossings |
| Aegean Sea | Turkish and Greek port tanker traffic |
| Cyclades | Mass tourism, cruise shipping |
| Tyrrhenian Sea | Rome–Naples–Palermo petroleum corridor |
| Balearic Sea | Main Europe–Africa shipping corridor |
| Levantine Basin | Offshore oil extraction (Israel, Cyprus, Lebanon) |
| Gulf of Lion | Rhône river runoff — agricultural residue and plastics |

---

## Known Limitations (Demo Version)

| Limitation | Production fix |
|---|---|
| `CopernicusClient` is mocked — no real satellite downloads | Real STAC API + OAuth2 |
| In-memory `app_state` resets on restart | PostgreSQL persistence |
| Sentinel-2 bands are 256×256 synthetic arrays | Real L2A downloads from Copernicus Dataspace |
| Trajectory uses constant wind/current | CMEMS time-varying ocean forcing |
| `CORS allow_origins=["*"]` | API key / JWT authentication |
| `/horizons` runs 5 sequential simulations | Vectorise across time horizons |

---

## Roadmap

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

## Team

| Name | Background |
|---|---|
| Chiara | RF & antenna systems, network/database, space & defence electronics |
| Alessio | Computer science, robotics, GNC, satellite architectures |
| Priscilla | Network/database, geoinformation, satellite remote sensing, software |
| Caterina | Business administration, banking, international economics, strategy |

---

## Resources

- [MADOS dataset](https://zenodo.org/records/7879652) — Marine pollution segmentation benchmark for ML training
- [OpenEO oil spill notebook](https://documentation.dataspace.copernicus.eu/notebook-samples/openeo/OilSpill.html) — Sentinel-1/2 via Copernicus Dataspace
- [Copernicus Dataspace](https://dataspace.copernicus.eu/) — Free access to Sentinel satellite data
- [Kinéis IoT-LEO](https://www.kineis.com/) — Low-power LEO satellite IoT network
- [Cassini Hackathons](https://www.cassini.eu/hackathons) — EU Space Programme hackathon series

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** — see [LICENSE](LICENSE) for the full text.

Under AGPL-3.0, anyone who deploys a modified version of this software as a network service must also release the corresponding source code.

---

*AquaGuard — WASP · Cassini Hackathon #2 · April 2026*
