'use strict';

/* ─── Alerts & Detail Panel Controller ──────────────────── */
const AquaAlerts = (() => {
  const SEV_COLORS = {
    LOW: '#4488ff', MEDIUM: '#ffcc00', HIGH: '#ff6b35', CRITICAL: '#ff4455',
  };

  const TYPE_ICONS = {
    OIL_SPILL: '🛢️', ALGAL_BLOOM: '🌿', HYDROCARBON: '⚗️',
    MARINE_DEBRIS: '🗑️', UNKNOWN: '❓',
  };

  function renderAlertsList(alerts) {
    const container = document.getElementById('alerts-list');
    if (!alerts || alerts.length === 0) {
      container.innerHTML = '<div class="loading-placeholder">No active alerts</div>';
      return;
    }

    container.innerHTML = alerts.slice(0, 10).map(alert => {
      const ago = _timeAgo(alert.issued_at);
      const msg = alert.message.length > 80
        ? alert.message.substring(0, 80) + '…'
        : alert.message;

      return `
        <div class="alert-item ${alert.priority}" data-event-id="${alert.event_id}">
          <div class="alert-header">
            <span class="alert-badge ${alert.priority}">${alert.priority}</span>
            <span class="alert-time">${ago}</span>
          </div>
          <div class="alert-msg">${msg}</div>
        </div>`;
    }).join('');

    // Click alert → show event on map
    container.querySelectorAll('.alert-item').forEach(el => {
      el.addEventListener('click', () => {
        const eid = el.dataset.eventId;
        document.dispatchEvent(new CustomEvent('aqua:selectEvent', { detail: eid }));
      });
    });
  }

  function showEventDetail(event) {
    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    const typeName = event.event_type.replace(/_/g, ' ');
    const icon = TYPE_ICONS[event.event_type] || '❓';
    const sevColor = SEV_COLORS[event.severity] || '#8ba7c7';

    const mciRow = event.mci_value != null
      ? `<div class="detail-card">
           <div class="detail-card-label">MCI (chlorophyll)</div>
           <div class="detail-card-value" style="font-size:14px;">${event.mci_value.toFixed(4)}</div>
         </div>` : '';

    const vnriRow = event.vnri_value != null
      ? `<div class="detail-card">
           <div class="detail-card-label">VNRI (hydrocarbons)</div>
           <div class="detail-card-value" style="font-size:14px;">${event.vnri_value.toFixed(4)}</div>
         </div>` : '';

    const recs = _getAIRecommendation(event);
    const recHtml = recs.length > 0 ? `
      <div class="ai-rec-panel">
        <div class="ai-rec-header">🤖 AI Response Recommendations</div>
        ${recs.map(r => `
          <div class="ai-rec-item">
            <span class="ai-rec-priority ai-pri-${r.priority.toLowerCase()}">${r.priority}</span>
            <span class="ai-rec-text">${r.icon} ${r.action}</span>
          </div>`).join('')}
      </div>` : '';

    content.innerHTML = `
      <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
        <span style="font-size:22px;">${icon}</span>
        <div>
          <div style="font-size:16px; font-weight:700; color:#1a3050;">${typeName}</div>
          <span class="sev-badge ${event.severity}">${event.severity}</span>
        </div>
        <div style="margin-left:auto; font-size:12px; color:#3a607a;">
          ${event.source_satellite}<br/>
          ${_timeAgo(event.detected_at)}
        </div>
      </div>

      <div style="font-size:13px; color:#3a607a; margin-bottom:10px;">
        ${event.description || ''}
      </div>

      <div class="detail-grid">
        <div class="detail-card">
          <div class="detail-card-label">Area</div>
          <div class="detail-card-value">${event.area_km2.toFixed(1)} km²</div>
        </div>
        <div class="detail-card">
          <div class="detail-card-label">Confidence</div>
          <div class="detail-card-value">${(event.confidence_score * 100).toFixed(0)}%</div>
          <div class="confidence-bar">
            <div class="confidence-fill" style="width:${event.confidence_score * 100}%"></div>
          </div>
        </div>
        <div class="detail-card">
          <div class="detail-card-label">Location</div>
          <div class="detail-card-value" style="font-size:13px;">
            ${event.location.lat.toFixed(4)}°N<br/>
            ${event.location.lon.toFixed(4)}°E
          </div>
        </div>
        ${mciRow}
        ${vnriRow}
      </div>

      <button class="predict-btn" id="trajectory-btn">
        🔮 Predict 48h Trajectory
      </button>

      ${recHtml}`;

    document.getElementById('trajectory-btn').addEventListener('click', () => {
      AquaMap.showTrajectory(event.location.lon, event.location.lat, event.id);
    });

    panel.classList.add('open');
  }

  function hideDetail() {
    document.getElementById('detail-panel').classList.remove('open');
    AquaMap.clearTrajectory();
  }

  // Close button
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('detail-close').addEventListener('click', hideDetail);
  });

  return { renderAlertsList, showEventDetail, hideDetail };
})();

function _timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime();
  const h = Math.floor(diff / 3600000);
  const m = Math.floor(diff / 60000);
  if (m < 2) return 'just now';
  if (h < 1) return `${m}m ago`;
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/* ─── AI Recommendation Engine ───────────────────────────── */
function _getAIRecommendation(event) {
  const sev  = event.severity;
  const type = event.event_type;
  const area = event.area_km2 || 0;
  const conf = event.confidence_score || 0;
  const ageH = (Date.now() - new Date(event.detected_at).getTime()) / 3600000;
  const recs = [];

  const isCritOrHigh = sev === 'CRITICAL' || sev === 'HIGH';

  if (type === 'OIL_SPILL') {
    if (sev === 'CRITICAL') {
      recs.push({ priority: 'IMMEDIATE', icon: '🚨', action: 'Activate emergency oil spill response plan (OSRP) — contact regional coast guard command' });
      recs.push({ priority: 'IMMEDIATE', icon: '🚢', action: 'Dispatch response vessels to reported coordinates for visual confirmation' });
      recs.push({ priority: 'URGENT',    icon: '📡', action: 'Issue NAVTEX maritime warning to all vessels in affected zone' });
    } else if (sev === 'HIGH') {
      recs.push({ priority: 'URGENT', icon: '⚓', action: 'Alert coast guard and maritime environmental authority for rapid assessment' });
      recs.push({ priority: 'URGENT', icon: '🔭', action: 'Run updated 48h trajectory forecast — pre-position boom and skimmer assets' });
    } else {
      recs.push({ priority: 'MONITOR', icon: '🛰️', action: 'Schedule next Sentinel-1 SAR pass for size and spread confirmation' });
      recs.push({ priority: 'MONITOR', icon: '🔍', action: 'Cross-reference AIS vessel history to identify probable discharge source' });
    }
    if (area > 50) {
      recs.push({ priority: 'URGENT', icon: '✈️', action: `Large slick (${area.toFixed(0)} km²) — assess aerial dispersant deployment with environmental authority` });
    }
    if (isCritOrHigh) {
      recs.push({ priority: 'MEDIUM', icon: '🪤', action: 'Deploy containment boom if slick is within 10 km of sensitive coastline or marine protected area' });
    }
  }

  if (type === 'ALGAL_BLOOM') {
    if (isCritOrHigh) {
      recs.push({ priority: 'IMMEDIATE', icon: '🏖️', action: 'Issue beach closure advisory for all affected coastal zones within 5 km' });
      recs.push({ priority: 'IMMEDIATE', icon: '🎣', action: 'Suspend recreational fishing and shellfish harvesting pending toxin analysis' });
      recs.push({ priority: 'URGENT',    icon: '🧪', action: 'Deploy in-situ sampling team — test for cyanotoxins (microcystin, anatoxin)' });
      recs.push({ priority: 'URGENT',    icon: '💧', action: 'Alert downstream drinking water intakes — increase treatment monitoring' });
    } else {
      recs.push({ priority: 'MONITOR', icon: '⚠️', action: 'Issue precautionary beach advisory, pending toxin lab confirmation (48h)' });
      recs.push({ priority: 'MONITOR', icon: '🔬', action: 'Schedule water quality sampling within 24 hours' });
    }
    recs.push({ priority: 'MEDIUM', icon: '🌾', action: 'Investigate upstream agricultural nutrient loading (N/P runoff) as bloom trigger' });
    if (event.mci_value && event.mci_value > 0.02) {
      recs.push({ priority: 'MEDIUM', icon: '📊', action: `Elevated MCI (${event.mci_value.toFixed(4)}) — consider satellite-derived chlorophyll-a mapping across full basin` });
    }
  }

  if (type === 'HYDROCARBON') {
    recs.push({ priority: isCritOrHigh ? 'URGENT' : 'MEDIUM', icon: '🚢', action: 'Cross-reference AIS vessel positions ±6h around detection time for discharge source ID' });
    recs.push({ priority: 'MEDIUM', icon: '⚓', action: 'Notify port authority and national coastal environmental agency (ISPRA/similar)' });
    if (isCritOrHigh) {
      recs.push({ priority: 'URGENT', icon: '🧪', action: 'Collect water samples for BTEX and PAH compound analysis (lab turnaround 48h)' });
      recs.push({ priority: 'MEDIUM', icon: '🛥️', action: 'Pre-position oil recovery vessel in case slick spreads toward sensitive zone' });
    }
    if (event.vnri_value && event.vnri_value > 0.20) {
      recs.push({ priority: 'MEDIUM', icon: '📡', action: `High VNRI (${event.vnri_value.toFixed(4)}) confirms petroleum hydrocarbons — escalate to MARPOL violation report` });
    }
  }

  if (type === 'MARINE_DEBRIS') {
    recs.push({ priority: 'MEDIUM', icon: '🛥️', action: 'Schedule cleanup vessel deployment — optimal timing based on current trajectory forecast' });
    recs.push({ priority: 'MEDIUM', icon: '📍', action: 'Run 72h Lagrangian drift model to predict debris accumulation hotspot for targeted collection' });
    recs.push({ priority: 'LOW',    icon: '📋', action: 'Log event to OSPAR/Barcelona Convention marine litter monitoring database' });
    recs.push({ priority: 'LOW',    icon: '🔗', action: 'Flag location to citizen science network for shoreline survey coordination' });
  }

  // Cross-cutting recommendations based on metadata
  if (conf < 0.75) {
    recs.push({ priority: 'MONITOR', icon: '🛰️', action: `Low confidence (${(conf * 100).toFixed(0)}%) — request next satellite overpass for verification before escalating response` });
  }
  if (ageH > 6 && isCritOrHigh) {
    recs.push({ priority: 'URGENT', icon: '🔄', action: `Event is ${ageH.toFixed(0)}h old — run updated trajectory forecast; actual position may differ significantly` });
  }
  if (ageH > 24) {
    recs.push({ priority: 'MONITOR', icon: '📅', action: `Event exceeds 24h — verify whether incident is resolved or still active via latest SAR imagery` });
  }

  return recs;
}
