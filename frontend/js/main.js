'use strict';

/* ─── AquaGuard App Entry Point ──────────────────────────── */
window.AQUA_API_BASE = 'http://localhost:8000';

// Demo fallback events (Mediterranean) used when backend is offline
const DEMO_EVENTS = [
  { id:'d1', event_type:'OIL_SPILL', severity:'CRITICAL',
    location:{lon:12.45, lat:37.50}, area_km2:62.3, confidence_score:0.91,
    detected_at: new Date(Date.now()-1800000).toISOString(),
    source_satellite:'Sentinel-1A',
    vnri_value:0.31, mci_value:null,
    description:'Oil slick detected near Strait of Sicily. Possible tanker discharge.' },
  { id:'d2', event_type:'ALGAL_BLOOM', severity:'HIGH',
    location:{lon:13.50, lat:44.50}, area_km2:28.7, confidence_score:0.86,
    detected_at: new Date(Date.now()-7200000).toISOString(),
    source_satellite:'Sentinel-2A',
    mci_value:0.018, vnri_value:null,
    description:'Harmful algal bloom in Northern Adriatic. Beach advisory issued.' },
  { id:'d3', event_type:'HYDROCARBON', severity:'MEDIUM',
    location:{lon:24.10, lat:37.90}, area_km2:9.4, confidence_score:0.78,
    detected_at: new Date(Date.now()-14400000).toISOString(),
    source_satellite:'Sentinel-2B',
    vnri_value:0.14, mci_value:null,
    description:'Hydrocarbon contamination detected in Aegean Sea.' },
  { id:'d4', event_type:'MARINE_DEBRIS', severity:'LOW',
    location:{lon:5.35, lat:43.30}, area_km2:3.1, confidence_score:0.67,
    detected_at: new Date(Date.now()-28800000).toISOString(),
    source_satellite:'Sentinel-2A',
    mci_value:null, vnri_value:null,
    description:'Marine debris accumulation in Gulf of Lion.' },
  { id:'d5', event_type:'OIL_SPILL', severity:'HIGH',
    location:{lon:16.87, lat:41.12}, area_km2:35.8, confidence_score:0.88,
    detected_at: new Date(Date.now()-3600000).toISOString(),
    source_satellite:'Sentinel-1B',
    vnri_value:0.22, mci_value:null,
    description:'Oil slick near Southern Adriatic. Coast guard notified.' },
  { id:'d6', event_type:'ALGAL_BLOOM', severity:'MEDIUM',
    location:{lon:35.50, lat:36.80}, area_km2:14.2, confidence_score:0.74,
    detected_at: new Date(Date.now()-43200000).toISOString(),
    source_satellite:'Sentinel-2B',
    mci_value:0.011, vnri_value:null,
    description:'Algal bloom in Levantine Basin. Tourism alert issued.' },
  { id:'d7', event_type:'OIL_SPILL', severity:'CRITICAL',
    location:{lon:23.72, lat:38.00}, area_km2:78.9, confidence_score:0.93,
    detected_at: new Date(Date.now()-900000).toISOString(),
    source_satellite:'Sentinel-1A',
    vnri_value:0.38, mci_value:null,
    description:'Major oil spill in Cyclades. Emergency response activated.' },
  { id:'d8', event_type:'HYDROCARBON', severity:'HIGH',
    location:{lon:14.22, lat:40.83}, area_km2:19.5, confidence_score:0.82,
    detected_at: new Date(Date.now()-5400000).toISOString(),
    source_satellite:'Sentinel-2A',
    vnri_value:0.19, mci_value:null,
    description:'Hydrocarbon plume in Gulf of Naples. Industrial source suspected.' },
];

const DEMO_ALERTS = [
  { id:'a1', event_id:'d7', priority:'CRITICAL',
    message:'CRITICAL: Major oil spill 78.9 km² in Cyclades. Emergency response activated.',
    issued_at: new Date(Date.now()-900000).toISOString() },
  { id:'a2', event_id:'d1', priority:'CRITICAL',
    message:'CRITICAL: Oil slick 62.3 km² near Strait of Sicily. Coast guard dispatched.',
    issued_at: new Date(Date.now()-1800000).toISOString() },
  { id:'a3', event_id:'d5', priority:'WARNING',
    message:'WARNING: Oil spill 35.8 km² Southern Adriatic. Monitoring in progress.',
    issued_at: new Date(Date.now()-3600000).toISOString() },
  { id:'a4', event_id:'d2', priority:'WARNING',
    message:'WARNING: Harmful algal bloom 28.7 km² Northern Adriatic. Beach advisory.',
    issued_at: new Date(Date.now()-7200000).toISOString() },
];

// Demo fallback buoys at beaches, lakes, rivers, dams, and Roman aqueducts
const DEMO_BUOYS = [
  // Coastal beaches
  { buoy_id:1,  last_latitude:44.06, last_longitude:12.57, bat_mv:4050, solar_pct:72,
    active_alerts:['OIL'], total_readings:18, online:true, location_name:'Rimini Beach', location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:0.92,uv:0.89,turbidity:0.95,ph:0.98,dissolved_oxygen:0.96,bacteria:0.94,gps:1.0}, false_positive_rate:0.11, uptime_pct:94.4 } },
  { buoy_id:2,  last_latitude:40.63, last_longitude:14.48, bat_mv:3980, solar_pct:81,
    active_alerts:[], total_readings:22, online:true, location_name:'Positano', location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:1.0,uv:0.97,turbidity:1.0,ph:0.95,dissolved_oxygen:0.98,bacteria:0.96,gps:1.0}, false_positive_rate:0.0, uptime_pct:100.0 } },
  { buoy_id:3,  last_latitude:43.70, last_longitude:7.27,  bat_mv:3820, solar_pct:68,
    active_alerts:[], total_readings:15, online:true, location_name:"Nice, Côte d'Azur", location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:0.98,uv:0.95,turbidity:0.97,ph:0.96,dissolved_oxygen:0.99,bacteria:0.97,gps:1.0}, false_positive_rate:0.05, uptime_pct:88.2 } },
  { buoy_id:4,  last_latitude:42.65, last_longitude:18.09, bat_mv:4100, solar_pct:55,
    active_alerts:[], total_readings:20, online:true, location_name:'Dubrovnik', location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:1.0,uv:1.0,turbidity:0.98,ph:0.97,dissolved_oxygen:1.0,bacteria:0.98,gps:1.0}, false_positive_rate:0.0, uptime_pct:96.0 } },
  { buoy_id:5,  last_latitude:39.57, last_longitude:3.07,  bat_mv:3750, solar_pct:64,
    active_alerts:['OIL'], total_readings:12, online:true, location_name:'Alcudia, Mallorca', location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:0.88,uv:0.85,turbidity:0.90,ph:0.95,dissolved_oxygen:0.92,bacteria:0.88,gps:0.95}, false_positive_rate:0.16, uptime_pct:80.0 } },
  { buoy_id:6,  last_latitude:40.25, last_longitude:17.89, bat_mv:4020, solar_pct:77,
    active_alerts:[], total_readings:19, online:true, location_name:'Porto Cesareo', location_type:'COASTAL',
    health:{ operational_state:'UP', sensor_quality:{oil:0.97,uv:0.96,turbidity:0.99,ph:0.98,dissolved_oxygen:0.97,bacteria:0.98,gps:1.0}, false_positive_rate:0.04, uptime_pct:95.0 } },
  // Lakes
  { buoy_id:7,  last_latitude:45.63, last_longitude:10.72, bat_mv:3890, solar_pct:48,
    active_alerts:['BACTERIA'], total_readings:16, online:true, location_name:'Lake Garda', location_type:'LAKE',
    health:{ operational_state:'UP', sensor_quality:{oil:1.0,uv:0.98,turbidity:0.82,ph:0.79,dissolved_oxygen:0.74,bacteria:0.71,gps:1.0}, false_positive_rate:0.08, uptime_pct:84.2 } },
  { buoy_id:8,  last_latitude:46.00, last_longitude:9.26,  bat_mv:4080, solar_pct:60,
    active_alerts:[], total_readings:21, online:true, location_name:'Lake Como', location_type:'LAKE',
    health:{ operational_state:'UP', sensor_quality:{oil:1.0,uv:0.99,turbidity:0.98,ph:0.97,dissolved_oxygen:0.96,bacteria:0.97,gps:1.0}, false_positive_rate:0.02, uptime_pct:98.0 } },
  { buoy_id:9,  last_latitude:43.12, last_longitude:12.10, bat_mv:3610, solar_pct:40,
    active_alerts:['ALGAE'], total_readings:10, online:true, location_name:'Lake Trasimeno', location_type:'LAKE',
    health:{ operational_state:'UP', sensor_quality:{oil:0.95,uv:0.93,turbidity:0.76,ph:0.71,dissolved_oxygen:0.68,bacteria:0.70,gps:0.98}, false_positive_rate:0.12, uptime_pct:75.0 } },
  { buoy_id:10, last_latitude:42.60, last_longitude:11.90, bat_mv:3970, solar_pct:52,
    active_alerts:[], total_readings:14, online:true, location_name:'Lake Bolsena', location_type:'LAKE',
    health:{ operational_state:'UP', sensor_quality:{oil:0.99,uv:0.98,turbidity:0.95,ph:0.93,dissolved_oxygen:0.95,bacteria:0.94,gps:1.0}, false_positive_rate:0.06, uptime_pct:87.5 } },
  // Rivers
  { buoy_id:11, last_latitude:41.89, last_longitude:12.47, bat_mv:3780, solar_pct:35,
    active_alerts:['ALGAE','BACTERIA'], total_readings:24, online:true, location_name:'Tiber River, Rome', location_type:'RIVER',
    health:{ operational_state:'UP', sensor_quality:{oil:0.90,uv:0.88,turbidity:0.65,ph:0.60,dissolved_oxygen:0.55,bacteria:0.50,gps:0.97}, false_positive_rate:0.09, uptime_pct:92.3 } },
  { buoy_id:12, last_latitude:44.55, last_longitude:12.25, bat_mv:4010, solar_pct:65,
    active_alerts:[], total_readings:18, online:true, location_name:'Po River Delta', location_type:'RIVER',
    health:{ operational_state:'UP', sensor_quality:{oil:0.96,uv:0.95,turbidity:0.88,ph:0.90,dissolved_oxygen:0.85,bacteria:0.87,gps:1.0}, false_positive_rate:0.05, uptime_pct:90.0 } },
  { buoy_id:13, last_latitude:43.77, last_longitude:11.25, bat_mv:3840, solar_pct:58,
    active_alerts:[], total_readings:13, online:true, location_name:'Arno, Florence', location_type:'RIVER',
    health:{ operational_state:'UP', sensor_quality:{oil:0.97,uv:0.96,turbidity:0.85,ph:0.88,dissolved_oxygen:0.82,bacteria:0.85,gps:0.99}, false_positive_rate:0.07, uptime_pct:86.7 } },
  { buoy_id:14, last_latitude:43.93, last_longitude:4.83,  bat_mv:3920, solar_pct:70,
    active_alerts:[], total_readings:16, online:true, location_name:'Rhône, Avignon', location_type:'RIVER',
    health:{ operational_state:'UP', sensor_quality:{oil:0.99,uv:0.98,turbidity:0.90,ph:0.91,dissolved_oxygen:0.89,bacteria:0.90,gps:1.0}, false_positive_rate:0.03, uptime_pct:92.0 } },
  // Dams
  { buoy_id:15, last_latitude:40.28, last_longitude:16.02, bat_mv:3650, solar_pct:42,
    active_alerts:['BACTERIA','ALGAE'], total_readings:11, online:true, location_name:'Lago del Pertusillo', location_type:'DAM',
    health:{ operational_state:'UP', sensor_quality:{oil:0.93,uv:0.91,turbidity:0.62,ph:0.58,dissolved_oxygen:0.52,bacteria:0.48,gps:0.95}, false_positive_rate:0.14, uptime_pct:73.3 } },
  { buoy_id:16, last_latitude:43.94, last_longitude:11.98, bat_mv:3990, solar_pct:55,
    active_alerts:[], total_readings:17, online:true, location_name:'Lago di Bilancino', location_type:'DAM',
    health:{ operational_state:'UP', sensor_quality:{oil:0.98,uv:0.97,turbidity:0.93,ph:0.94,dissolved_oxygen:0.91,bacteria:0.92,gps:1.0}, false_positive_rate:0.04, uptime_pct:91.8 } },
  { buoy_id:17, last_latitude:46.27, last_longitude:12.34, bat_mv:3180, solar_pct:10,
    active_alerts:['LOW_BAT'], total_readings:9,  online:false, location_name:'Lago del Vajont', location_type:'DAM',
    health:{ operational_state:'DOWN', sensor_quality:{oil:0.70,uv:0.68,turbidity:0.75,ph:0.72,dissolved_oxygen:0.70,bacteria:0.71,gps:0.60}, false_positive_rate:0.22, uptime_pct:45.0 } },
  // Roman aqueducts / historic water infrastructure
  { buoy_id:18, last_latitude:41.86, last_longitude:12.54, bat_mv:4050, solar_pct:62,
    active_alerts:[], total_readings:20, online:true, location_name:'Aqua Claudia, Rome', location_type:'AQUEDUCT',
    health:{ operational_state:'UP', sensor_quality:{oil:1.0,uv:0.99,turbidity:0.97,ph:0.96,dissolved_oxygen:0.98,bacteria:0.97,gps:1.0}, false_positive_rate:0.01, uptime_pct:97.5 } },
  { buoy_id:19, last_latitude:43.94, last_longitude:4.54,  bat_mv:3210, solar_pct:8,
    active_alerts:['LOW_BAT'], total_readings:8,  online:true, location_name:'Pont du Gard', location_type:'AQUEDUCT',
    health:{ operational_state:'REPLACE', sensor_quality:{oil:0.88,uv:0.86,turbidity:0.90,ph:0.89,dissolved_oxygen:0.87,bacteria:0.88,gps:0.92}, false_positive_rate:0.18, uptime_pct:62.5 } },
  { buoy_id:20, last_latitude:40.95, last_longitude:-4.12, bat_mv:3880, solar_pct:50,
    active_alerts:[], total_readings:15, online:true, location_name:'Segovia Aqueduct', location_type:'AQUEDUCT',
    health:{ operational_state:'UP', sensor_quality:{oil:0.99,uv:0.98,turbidity:0.96,ph:0.94,dissolved_oxygen:0.95,bacteria:0.95,gps:0.98}, false_positive_rate:0.05, uptime_pct:88.0 } },
];

/* ─── App State ───────────────────────────────────────────── */
let allEvents = [];
let activeFilters = {
  types: new Set(['OIL_SPILL','ALGAL_BLOOM','HYDROCARBON','MARINE_DEBRIS','UNKNOWN']),
  minSeverity: 'ALL',
};

const SEV_ORDER = { ALL: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };

/* ─── API helpers ─────────────────────────────────────────── */
async function fetchJson(path, options = {}) {
  const url = `${window.AQUA_API_BASE}${path}`;
  const res = await fetch(url, { ...options, signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* ─── Data fetching ───────────────────────────────────────── */
async function fetchStatus() {
  try {
    const data = await fetchJson('/api/status');
    document.getElementById('val-events').textContent = data.total_events ?? '—';
    document.getElementById('val-alerts').textContent = data.active_alerts ?? '—';
    document.getElementById('val-zones').textContent = data.zones_monitored ?? '—';
    setOnline(true);
  } catch {
    setOnline(false);
  }
}

async function fetchEvents() {
  try {
    const events = await fetchJson('/api/detection/events?limit=50');
    allEvents = events;
    setOnline(true);
    document.getElementById('offline-banner').style.display = 'none';
  } catch {
    allEvents = DEMO_EVENTS;
    setOnline(false);
    document.getElementById('offline-banner').style.display = 'block';
    // populate stats from demo
    document.getElementById('val-events').textContent = DEMO_EVENTS.length;
    document.getElementById('val-alerts').textContent = DEMO_ALERTS.length;
    document.getElementById('val-zones').textContent = 10;
  }
  applyFiltersAndRender();
}

async function fetchAlerts() {
  try {
    const alerts = await fetchJson('/api/alerts/?limit=10');
    AquaAlerts.renderAlertsList(alerts);
  } catch {
    AquaAlerts.renderAlertsList(DEMO_ALERTS);
  }
}

async function fetchBuoys() {
  try {
    const buoys = await fetchJson('/api/buoys/');
    AquaMap.updateBuoyMarkers(buoys);
    document.getElementById('val-buoys').textContent = buoys.length;
  } catch {
    AquaMap.updateBuoyMarkers(DEMO_BUOYS);
    document.getElementById('val-buoys').textContent = DEMO_BUOYS.length;
  }
}

/* ─── Filter logic ────────────────────────────────────────── */
function applyFiltersAndRender() {
  const minSevLevel = SEV_ORDER[activeFilters.minSeverity] || 0;
  const filtered = allEvents.filter(e =>
    activeFilters.types.has(e.event_type) &&
    (SEV_ORDER[e.severity] || 0) >= minSevLevel
  );
  AquaMap.updateMarkers(filtered);
}

/* ─── Status indicator ────────────────────────────────────── */
function setOnline(online) {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  dot.className = `status-dot ${online ? 'online' : 'offline'}`;
  txt.textContent = online ? 'Live — Copernicus' : 'Demo mode';
}

/* ─── Counter animation ───────────────────────────────────── */
function animateCounter(el, target) {
  let current = 0;
  const step = Math.ceil(target / 20);
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, 40);
}

/* ─── Bootstrap ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {
  AquaMap.init('map');

  // Type filter checkboxes
  document.querySelectorAll('.type-filter').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) activeFilters.types.add(cb.value);
      else activeFilters.types.delete(cb.value);
      applyFiltersAndRender();
    });
  });

  // Severity buttons
  document.querySelectorAll('.sev-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sev-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilters.minSeverity = btn.dataset.sev;
      applyFiltersAndRender();
    });
  });

  // Subscribe modal
  document.getElementById('subscribe-btn').addEventListener('click', () => {
    document.getElementById('modal-overlay').style.display = 'flex';
  });
  document.getElementById('modal-close').addEventListener('click', () => {
    document.getElementById('modal-overlay').style.display = 'none';
  });
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget)
      document.getElementById('modal-overlay').style.display = 'none';
  });
  document.getElementById('subscribe-form').addEventListener('submit', async e => {
    e.preventDefault();
    const email = document.getElementById('sub-email').value;
    const severity = document.getElementById('sub-severity').value;
    try {
      await fetchJson('/api/alerts/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, min_severity: severity }),
      });
    } catch { /* offline demo */ }
    document.getElementById('subscribe-form').style.display = 'none';
    document.getElementById('modal-success').style.display = 'block';
    setTimeout(() => {
      document.getElementById('modal-overlay').style.display = 'none';
      document.getElementById('subscribe-form').style.display = 'block';
      document.getElementById('modal-success').style.display = 'none';
    }, 2500);
  });

  // Buoy layer toggle
  document.getElementById('buoy-show').addEventListener('change', e => {
    if (e.target.checked) fetchBuoys();
    else AquaMap.updateBuoyMarkers([]);
  });

  // Select event via custom event from map popup or alert list
  document.addEventListener('aqua:selectEvent', async e => {
    const eid = e.detail;
    const event = allEvents.find(ev => ev.id == eid || ev.id === eid);
    if (event) AquaAlerts.showEventDetail(event);
  });

  // Initial data load
  await Promise.all([fetchStatus(), fetchEvents(), fetchAlerts(), fetchBuoys()]);

  // Animate stats
  const evVal = parseInt(document.getElementById('val-events').textContent) || 0;
  const alVal = parseInt(document.getElementById('val-alerts').textContent) || 0;
  animateCounter(document.getElementById('val-events'), evVal);
  animateCounter(document.getElementById('val-alerts'), alVal);

  // Polling intervals
  setInterval(fetchStatus, 30_000);
  setInterval(fetchEvents, 60_000);
  setInterval(fetchAlerts, 45_000);
  setInterval(fetchBuoys,  60_000);
});
