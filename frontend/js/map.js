'use strict';

/* ─── Map Controller ─────────────────────────────────────── */
const AquaMap = (() => {
  let map = null;
  let markerLayer = null;
  let trajectoryLayer = null;
  let buoyLayer = null;
  let selectedEventId = null;

  const BUOY_STATE_COLORS = { UP: '#00a85a', DOWN: '#c4890a', REPLACE: '#e02840' };
  const LOC_TYPE_ICONS    = {
    COASTAL:  '⚓', LAKE: '🏔️', RIVER: '🌊',
    DAM: '🏗️', AQUEDUCT: '🏛️',
  };

  const TYPE_COLORS = {
    OIL_SPILL:    '#ff6b35',
    ALGAL_BLOOM:  '#00ff88',
    HYDROCARBON:  '#ff4455',
    MARINE_DEBRIS:'#4488ff',
    UNKNOWN:      '#8ba7c7',
  };

  const TYPE_ICONS = {
    OIL_SPILL:    '🛢️',
    ALGAL_BLOOM:  '🌿',
    HYDROCARBON:  '⚗️',
    MARINE_DEBRIS:'🗑️',
    UNKNOWN:      '❓',
  };

  function init(containerId) {
    map = L.map(containerId, {
      center: [38.5, 18.0],
      zoom: 6,
      zoomControl: true,
      attributionControl: true,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO | WASP © 2025',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);

    markerLayer = L.layerGroup().addTo(map);
    trajectoryLayer = L.layerGroup().addTo(map);
    buoyLayer = L.layerGroup().addTo(map);
  }

  function _severityColor(severity) {
    const map = { LOW: '#4488ff', MEDIUM: '#ffcc00', HIGH: '#ff6b35', CRITICAL: '#ff4455' };
    return map[severity] || '#8ba7c7';
  }

  function _makeMarkerHtml(event) {
    const color = TYPE_COLORS[event.event_type] || '#8ba7c7';
    const sevColor = _severityColor(event.severity);
    const isCritical = event.severity === 'CRITICAL';
    const isRecent = (Date.now() - new Date(event.detected_at).getTime()) < 3600_000;

    const pulseRing = (isCritical || isRecent) ? `
      <div style="
        position:absolute; top:50%; left:50%;
        transform:translate(-50%,-50%);
        width:30px; height:30px; border-radius:50%;
        border:2px solid ${color};
        animation: markerPulse 1.8s ease-out infinite;
        pointer-events:none;
      "></div>` : '';

    return `
      <div style="position:relative; width:24px; height:24px;">
        ${pulseRing}
        <div style="
          width:20px; height:20px; border-radius:50%;
          background:${color};
          border:2px solid ${sevColor};
          display:flex; align-items:center; justify-content:center;
          font-size:10px; box-shadow:0 0 8px ${color}88;
          position:absolute; top:2px; left:2px;
        ">
          ${TYPE_ICONS[event.event_type] || ''}
        </div>
      </div>`;
  }

  function _buildPopup(event) {
    const color = TYPE_COLORS[event.event_type] || '#8ba7c7';
    const detectedAgo = _timeAgo(event.detected_at);
    const typeName = event.event_type.replace(/_/g, ' ');

    return `
      <div style="min-width:200px;">
        <div style="font-size:15px; font-weight:700; color:${color}; margin-bottom:6px;">
          ${TYPE_ICONS[event.event_type]} ${typeName}
        </div>
        <div style="margin-bottom:4px;">
          <span style="color:#3a607a;">Severity:</span>
          <span style="color:${_severityColor(event.severity)}; font-weight:600;">
            ${event.severity}
          </span>
        </div>
        <div style="color:#3a607a; margin-bottom:2px;">
          Area: <span style="color:#1a3050;">${event.area_km2.toFixed(1)} km²</span>
        </div>
        <div style="color:#3a607a; margin-bottom:2px;">
          Confidence: <span style="color:#1a3050;">${(event.confidence_score * 100).toFixed(0)}%</span>
        </div>
        <div style="color:#3a607a; margin-bottom:8px;">
          Detected: <span style="color:#1a3050;">${detectedAgo}</span>
        </div>
        <button
          onclick="AquaMap.selectEvent('${event.id}')"
          style="
            width:100%; padding:6px; background:#ff6b35; border:none;
            border-radius:6px; color:#fff; font-weight:700; cursor:pointer;
            font-size:12px;
          ">
          Details &amp; Predict Trajectory →
        </button>
      </div>`;
  }

  function updateMarkers(events) {
    markerLayer.clearLayers();

    events.forEach(event => {
      const icon = L.divIcon({
        html: _makeMarkerHtml(event),
        className: '',
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker(
        [event.location.lat, event.location.lon],
        { icon }
      );

      marker.bindPopup(_buildPopup(event), {
        maxWidth: 260,
        className: 'aqua-popup',
      });

      marker.on('click', () => {
        selectedEventId = event.id;
        AquaAlerts.showEventDetail(event);
      });

      markerLayer.addLayer(marker);
    });
  }

  function showTrajectory(lon, lat, eventId) {
    clearTrajectory();

    const API_BASE = window.AQUA_API_BASE || 'http://localhost:8000';
    fetch(`${API_BASE}/api/trajectory/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lon, lat, wind_u: 4.5, wind_v: 1.8,
                             current_u: 0.15, current_v: 0.08,
                             duration_hours: 48, n_particles: 20 }),
    })
    .then(r => r.json())
    .then(data => _drawTrajectory(data, lon, lat))
    .catch(() => _drawMockTrajectory(lon, lat));
  }

  function _drawTrajectory(data, originLon, originLat) {
    if (!data.particles || data.particles.length === 0) {
      _drawMockTrajectory(originLon, originLat);
      return;
    }

    data.particles.forEach(track => {
      const latlngs = track.map(pt => [pt.lat, pt.lon]);
      L.polyline(latlngs, {
        color: '#ff6b35',
        weight: 1.5,
        opacity: 0.5,
        dashArray: '4 4',
      }).addTo(trajectoryLayer);
    });

    // Uncertainty circle at last point
    const lastUncert = data.uncertainty_radius_km.slice(-1)[0] || 20;
    const lastTrack = data.particles[0];
    if (lastTrack && lastTrack.length > 0) {
      const last = lastTrack[lastTrack.length - 1];
      L.circle([last.lat, last.lon], {
        radius: lastUncert * 1000,
        color: '#ff6b35',
        weight: 1.5,
        fill: true,
        fillColor: '#ff6b35',
        fillOpacity: 0.08,
        dashArray: '6 4',
      }).addTo(trajectoryLayer);
    }

    map.setView([originLat, originLon], 7);
  }

  function _drawMockTrajectory(lon, lat) {
    // Fallback: draw synthetic 48h trajectory without API
    const windU = 4.0, windV = 1.5, curU = 0.15, curV = 0.08;
    const factor = 0.03;
    const dt = 1 / 111000;  // 1 m in degrees (approx)
    const mPerDegLat = 111320;
    const mPerDegLon = 111320 * Math.cos(lat * Math.PI / 180);

    const latlngs = [[lat, lon]];
    let curLon = lon, curLat = lat;
    for (let t = 0; t < 48; t++) {
      curLon += (factor * windU + curU) * 3600 / mPerDegLon;
      curLat += (factor * windV + curV) * 3600 / mPerDegLat;
      latlngs.push([curLat, curLon]);
    }

    L.polyline(latlngs, {
      color: '#ff6b35', weight: 2.5, opacity: 0.8,
    }).addTo(trajectoryLayer);

    const lastLat = latlngs[latlngs.length - 1][0];
    const lastLon = latlngs[latlngs.length - 1][1];
    L.circle([lastLat, lastLon], {
      radius: 25000,
      color: '#ff6b35', fillColor: '#ff6b35',
      fillOpacity: 0.1, weight: 1.5, dashArray: '6 4',
    }).addTo(trajectoryLayer);

    map.setView([lat, lon], 7);
  }

  function clearTrajectory() {
    trajectoryLayer.clearLayers();
  }

  function selectEvent(eventId) {
    selectedEventId = eventId;
    // Dispatch to alerts controller via custom event
    document.dispatchEvent(new CustomEvent('aqua:selectEvent', { detail: eventId }));
  }

  /* ─── Buoy rendering ─────────────────────────────────────── */

  function _buoyStateColor(buoy) {
    const state = buoy.health && buoy.health.operational_state;
    return BUOY_STATE_COLORS[state] || (buoy.online ? '#00a85a' : '#c4890a');
  }

  function _buoyMarkerHtml(buoy) {
    const col = _buoyStateColor(buoy);
    const hasBact = buoy.active_alerts && buoy.active_alerts.includes('BACTERIA');
    const hasOil  = buoy.active_alerts && buoy.active_alerts.includes('OIL');
    const pulse   = (hasBact || hasOil) ? `
      <div style="
        position:absolute; top:50%; left:50%;
        transform:translate(-50%,-50%);
        width:28px; height:28px; border-radius:50%;
        border:2px solid ${col};
        animation: markerPulse 1.8s ease-out infinite;
        pointer-events:none;
      "></div>` : '';
    return `
      <div style="position:relative; width:22px; height:22px;">
        ${pulse}
        <div style="
          width:18px; height:18px; border-radius:4px;
          background:#f0f5fc; border:2px solid ${col};
          display:flex; align-items:center; justify-content:center;
          font-size:10px; box-shadow:0 0 8px ${col}88;
          position:absolute; top:2px; left:2px;
        ">🔵</div>
      </div>`;
  }

  const _RISK_COLORS = {
    VERY_LOW: '#00a85a', LOW: '#7bc142', MODERATE: '#f5a623',
    HIGH: '#e8622a', VERY_HIGH: '#e02840',
  };
  const _RISK_LABELS = {
    VERY_LOW: 'Very Low', LOW: 'Low', MODERATE: 'Moderate',
    HIGH: 'High', VERY_HIGH: 'Very High',
  };

  function _buoyRiskHtml(buoy) {
    let score, pollScore, wqScore, infraScore, category, trend, note;

    if (buoy.risk_profile) {
      score      = Math.round(buoy.risk_profile.overall_score);
      pollScore  = Math.round(buoy.risk_profile.pollution_risk);
      wqScore    = Math.round(buoy.risk_profile.water_quality_risk);
      infraScore = Math.round(buoy.risk_profile.infrastructure_risk);
      category   = buoy.risk_profile.category;  // e.g. "VERY_LOW"
      trend      = buoy.risk_profile.trend;
      note       = buoy.risk_profile.insurer_note;
    } else {
      // Offline fallback: derive from health + active_alerts
      const h = buoy.health;
      const locBase = {COASTAL:10,LAKE:15,RIVER:30,DAM:25,AQUEDUCT:10}[buoy.location_type] || 15;
      const pollAlerts = (buoy.active_alerts || []).filter(
        a => ['OIL','BACTERIA','ALGAE','UV'].includes(a)
      );
      pollScore  = Math.min(100, pollAlerts.length * 40);
      if (h && h.sensor_quality) {
        const sq = h.sensor_quality;
        wqScore = Math.round(
          (1 - (sq.turbidity*0.25 + sq.dissolved_oxygen*0.25 + sq.bacteria*0.35 + sq.ph*0.15)) * 100
        );
      } else { wqScore = 20; }
      infraScore = Math.round(Math.min(100,
        locBase + (h ? (1 - h.uptime_pct/100)*40 + h.false_positive_rate*20 : 20)
      ));
      score = Math.round(0.40*pollScore + 0.40*wqScore + 0.20*infraScore);
      category = score < 20 ? 'VERY_LOW' : score < 40 ? 'LOW'
               : score < 60 ? 'MODERATE' : score < 80 ? 'HIGH' : 'VERY_HIGH';
      trend = 'STABLE';
      const locLabel = {
        COASTAL:'coastal property', LAKE:'lakefront property',
        RIVER:'riverbank property', DAM:'reservoir-adjacent property',
        AQUEDUCT:'historic water infrastructure site',
      }[buoy.location_type] || 'nearby property';
      note = {
        VERY_LOW: `Minimal environmental liability for ${locLabel}. Standard policy terms apply.`,
        LOW:      `Low environmental risk. Minor premium for ${locLabel} recommended.`,
        MODERATE: `Moderate risk. Environmental liability rider advised for ${locLabel}.`,
        HIGH:     `High risk. Elevated premium; pre-acquisition assessment for ${locLabel}.`,
        VERY_HIGH:`Critical risk. Specialist underwriting required for ${locLabel}.`,
      }[category];
    }

    const col      = _RISK_COLORS[category] || '#8ba7c7';
    const label    = _RISK_LABELS[category] || category;
    const trendIcon = {IMPROVING:'↘', STABLE:'→', DEGRADING:'↗'}[trend] || '→';
    const trendCol  = {IMPROVING:'#00a85a', STABLE:'#3a607a', DEGRADING:'#e02840'}[trend] || '#3a607a';

    const _bar = (val, lbl) => `
      <div style="display:flex;align-items:center;gap:4px;margin-top:3px;">
        <span style="color:#3a607a;font-size:10px;width:72px;flex-shrink:0;">${lbl}</span>
        <div style="flex:1;height:4px;background:#e4eef8;border-radius:2px;">
          <div style="width:${val}%;height:100%;background:${
            val > 60 ? '#e02840' : val > 35 ? '#f5a623' : '#00a85a'
          };border-radius:2px;"></div>
        </div>
        <span style="font-size:10px;color:#1a3050;width:22px;text-align:right;">${val}</span>
      </div>`;

    return `
      <div style="margin-top:8px;border-top:1px solid #d0dff0;padding-top:8px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;">
          <span style="font-size:11px;font-weight:700;color:#1a3050;">📊 Insurance Risk Index</span>
          <span style="font-size:11px;font-weight:700;color:${col};
            background:${col}1a;padding:2px 7px;border-radius:10px;border:1px solid ${col}44;">
            ${label} · ${score}/100
          </span>
        </div>
        ${_bar(pollScore,  'Pollution')}
        ${_bar(wqScore,    'Water Quality')}
        ${_bar(infraScore, 'Infrastructure')}
        <div style="margin-top:5px;font-size:10px;color:#3a607a;">
          Trend: <span style="color:${trendCol};font-weight:600;">${trendIcon} ${trend}</span>
        </div>
        <div style="margin-top:4px;font-size:10px;color:#3a607a;line-height:1.45;
          border-left:2px solid ${col};padding-left:6px;">
          ${note}
        </div>
      </div>`;
  }

  function _buoyPopupHtml(buoy) {
    const col   = _buoyStateColor(buoy);
    const state = (buoy.health && buoy.health.operational_state) || (buoy.online ? 'UP' : 'DOWN');
    const alerts = (buoy.active_alerts || []).join(', ') || 'None';
    const fp    = buoy.health ? (buoy.health.false_positive_rate * 100).toFixed(1) + '%' : '—';
    const up    = buoy.health ? buoy.health.uptime_pct.toFixed(1) + '%' : '—';
    const sq    = buoy.health ? buoy.health.sensor_quality : null;

    const locIcon = LOC_TYPE_ICONS[buoy.location_type] || '📍';
    const locLine = buoy.location_name ? `
      <div style="color:#3a607a; margin-bottom:4px; font-size:12px;">
        ${locIcon} <span style="color:#1a3050; font-weight:600;">${buoy.location_name}</span>
      </div>` : '';

    const healthBars = sq ? `
      <div style="margin-top:6px; font-size:11px; color:#3a607a;">Sensor quality</div>
      ${['oil','uv','turbidity','ph','dissolved_oxygen','bacteria','gps'].map(k => {
        const v = sq[k] !== undefined ? sq[k] : 1.0;
        const pct = (v * 100).toFixed(0);
        const c = v > 0.75 ? '#00a85a' : v > 0.45 ? '#c4890a' : '#e02840';
        return `<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">
          <span style="color:#3a607a;width:72px;font-size:10px;">${k}</span>
          <div style="flex:1;height:4px;background:#d8e8f4;border-radius:2px;">
            <div style="width:${pct}%;height:100%;background:${c};border-radius:2px;"></div>
          </div>
          <span style="color:${c};font-size:10px;width:28px;">${pct}%</span>
        </div>`;
      }).join('')}` : '';

    return `
      <div style="min-width:240px;">
        <div style="font-size:14px; font-weight:700; color:${col}; margin-bottom:4px;">
          🔵 Buoy #${buoy.buoy_id}
        </div>
        ${locLine}
        <div style="margin-bottom:3px;">
          <span style="color:#3a607a;">State:</span>
          <span style="color:${col}; font-weight:700;"> ${state}</span>
        </div>
        <div style="color:#3a607a; margin-bottom:2px;">
          Battery: <span style="color:#1a3050;">${buoy.bat_mv} mV</span>
          &nbsp; Solar: <span style="color:#1a3050;">${buoy.solar_pct}%</span>
        </div>
        <div style="color:#3a607a; margin-bottom:2px;">
          Alerts: <span style="color:${alerts === 'None' ? '#00a85a' : '#e8622a'};">${alerts}</span>
        </div>
        <div style="color:#3a607a; margin-bottom:2px;">
          Uptime: <span style="color:#1a3050;">${up}</span>
          &nbsp; FP rate: <span style="color:#1a3050;">${fp}</span>
        </div>
        <div style="color:#3a607a; font-size:11px;">
          Readings: ${buoy.total_readings} &nbsp;|&nbsp;
          ${buoy.last_latitude.toFixed(4)}°N ${buoy.last_longitude.toFixed(4)}°E
        </div>
        ${healthBars}
        ${_buoyRiskHtml(buoy)}
      </div>`;
  }

  function updateBuoyMarkers(buoys) {
    buoyLayer.clearLayers();
    if (!buoys || buoys.length === 0) return;

    buoys.forEach(buoy => {
      const icon = L.divIcon({
        html: _buoyMarkerHtml(buoy),
        className: '',
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });

      const marker = L.marker(
        [buoy.last_latitude, buoy.last_longitude],
        { icon }
      );

      marker.bindPopup(_buoyPopupHtml(buoy), {
        maxWidth: 310,
        className: 'aqua-popup aqua-buoy-popup',
      });

      buoyLayer.addLayer(marker);
    });
  }

  function fitToEvents(events) {
    if (!events || events.length === 0) return;
    const latlngs = events.map(e => [e.location.lat, e.location.lon]);
    const bounds = L.latLngBounds(latlngs);
    map.fitBounds(bounds, { padding: [40, 40] });
  }

  // Inject pulse keyframe into document
  const style = document.createElement('style');
  style.textContent = `
    @keyframes markerPulse {
      0%   { transform: translate(-50%,-50%) scale(1);   opacity: 0.8; }
      100% { transform: translate(-50%,-50%) scale(2.2); opacity: 0; }
    }`;
  document.head.appendChild(style);

  return { init, updateMarkers, updateBuoyMarkers, showTrajectory,
           clearTrajectory, selectEvent, fitToEvents };
})();
