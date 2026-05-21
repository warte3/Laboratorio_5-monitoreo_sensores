# server_ui.py
from flask import Flask, request, jsonify, render_template_string
from collections import deque
import time

app = Flask(__name__)

API_KEY = "cambia-esta-clave"      # Debe coincidir con el del ESP32
MAX_POINTS = 1000                 # Tamaño máx. del historial en memoria
data_buffer = deque(maxlen=MAX_POINTS)

panic_state = {"active": False, "timestamp": 0}

HTML = r"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Sistema de Monitoreo ESP32</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { font-family: 'DM Sans', sans-serif; }
    body {
      background: linear-gradient(135deg, #dbeafe 0%, #e0f2fe 40%, #bfdbfe 100%);
      min-height: 100vh;
    }
    .mono { font-family: 'Space Mono', monospace; }
 
    .card {
      background: rgba(255,255,255,0.75);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255,255,255,0.9);
      border-radius: 20px;
      box-shadow: 0 4px 24px rgba(59,130,246,0.10), 0 1px 4px rgba(59,130,246,0.08);
      transition: transform 0.18s, box-shadow 0.18s;
    }
    .card:hover {
      transform: translateY(-3px);
      box-shadow: 0 8px 32px rgba(59,130,246,0.16), 0 2px 8px rgba(59,130,246,0.10);
    }
 
    .card-icon {
      width: 44px; height: 44px;
      border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      font-size: 22px;
    }
 
    .badge-live {
      display: inline-flex; align-items: center; gap: 6px;
      background: #dcfce7; color: #166534;
      padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 500;
    }
    .badge-wait {
      display: inline-flex; align-items: center; gap: 6px;
      background: #f1f5f9; color: #64748b;
      padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 500;
    }
    .badge-panic {
      display: inline-flex; align-items: center; gap: 6px;
      background: #fee2e2; color: #991b1b;
      padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600;
      animation: panic-pulse 0.8s ease-in-out infinite;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; }
    .dot-green { background: #22c55e; animation: pulse 1.4s infinite; }
    .dot-gray  { background: #94a3b8; }
    .dot-red   { background: #ef4444; animation: pulse 0.6s infinite; }
    @keyframes pulse {
      0%,100% { opacity: 1; } 50% { opacity: 0.4; }
    }
 
    .val-big {
      font-family: 'Space Mono', monospace;
      font-size: 2rem; font-weight: 700; line-height: 1;
    }
 
    table thead tr th { font-size: 12px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }
    table tbody tr { transition: background 0.12s; }
    table tbody tr:hover { background: rgba(219,234,254,0.4); }
 
    .chart-wrap { position: relative; }
 
    /* alert bar */
    .alert-bar {
      border-radius: 12px; padding: 10px 16px;
      font-size: 13px; font-weight: 500;
      display: flex; align-items: center; gap: 8px;
    }
    .alert-red   { background: #fee2e2; color: #991b1b; }
    .alert-amber { background: #fef3c7; color: #92400e; }
    .alert-blue  { background: #dbeafe; color: #1e40af; }
    .alert-ok    { background: #dcfce7; color: #166534; }
 
    /* ── RELOJ en vivo ── */
    .live-clock {
      font-family: 'Space Mono', monospace;
      font-size: 13px;
      color: #60a5fa;
      letter-spacing: 0.03em;
    }
    .live-clock .clock-date {
      font-size: 11px;
      color: #93c5fd;
      text-transform: capitalize;
    }
 
    /* ══════════════════════════════
       TOAST NOTIFICATIONS
    ══════════════════════════════ */
    #toast-container {
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    }
 
    .toast {
      pointer-events: all;
      display: flex;
      align-items: flex-start;
      gap: 12px;
      min-width: 300px;
      max-width: 380px;
      padding: 14px 16px;
      border-radius: 16px;
      backdrop-filter: blur(20px);
      box-shadow: 0 8px 32px rgba(0,0,0,0.15), 0 2px 8px rgba(0,0,0,0.08);
      border: 1px solid rgba(255,255,255,0.5);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transform: translateX(120%);
      opacity: 0;
      transition: transform 0.35s cubic-bezier(0.34,1.56,0.64,1), opacity 0.35s ease;
    }
    .toast.show {
      transform: translateX(0);
      opacity: 1;
    }
    .toast.hide {
      transform: translateX(120%);
      opacity: 0;
      transition: transform 0.28s ease-in, opacity 0.28s ease-in;
    }
 
    .toast-critical {
      background: rgba(254,226,226,0.95);
      color: #7f1d1d;
      border-color: #fca5a5;
    }
    .toast-warning {
      background: rgba(254,243,199,0.95);
      color: #78350f;
      border-color: #fcd34d;
    }
    .toast-info {
      background: rgba(219,234,254,0.95);
      color: #1e3a5f;
      border-color: #93c5fd;
    }
    .toast-ok {
      background: rgba(220,252,231,0.95);
      color: #14532d;
      border-color: #86efac;
    }
    .toast-panic {
      background: rgba(220,38,38,0.95);
      color: #ffffff;
      border-color: #dc2626;
      animation: panic-pulse 0.8s ease-in-out infinite;
    }
 
    .toast-icon {
      font-size: 22px;
      line-height: 1;
      flex-shrink: 0;
    }
    .toast-body { flex: 1; }
    .toast-title {
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 2px;
    }
    .toast-msg {
      font-size: 12px;
      opacity: 0.9;
    }
    .toast-close {
      font-size: 16px;
      opacity: 0.7;
      flex-shrink: 0;
      line-height: 1;
      margin-top: 2px;
      color: inherit;
    }
    .toast-close:hover { opacity: 1; }
 
    /* barra de progreso del toast */
    .toast-progress {
      position: absolute;
      bottom: 0; left: 0;
      height: 3px;
      border-radius: 0 0 16px 16px;
      background: currentColor;
      opacity: 0.35;
      animation: toast-shrink 5s linear forwards;
    }
    .toast { position: relative; overflow: hidden; }
    @keyframes toast-shrink {
      from { width: 100%; }
      to   { width: 0%; }
    }

    /* ══════════════════════════════
       BANNER DE ALERTA SUPERIOR
    ══════════════════════════════ */
    @keyframes banner-pulse {
      0%,100% { opacity: 1; box-shadow: 0 0 0 0 rgba(239,68,68,0.25); }
      50%      { opacity: 0.92; box-shadow: 0 0 0 6px rgba(239,68,68,0); }
    }
    @keyframes panic-pulse {
      0%,100% { transform: scale(1); }
      50%      { transform: scale(1.02); }
    }
    .banner-tag {
      display: inline-flex; align-items: center; gap: 5px;
      background: rgba(0,0,0,0.07); border-radius: 7px;
      padding: 2px 10px; font-size: 13px; font-weight: 500;
    }
    .banner-tag-panic {
      display: inline-flex; align-items: center; gap: 5px;
      background: rgba(255,255,255,0.2); border-radius: 7px;
      padding: 2px 10px; font-size: 14px; font-weight: 700;
    }

    /* ── Umbrales ── */
    .threshold-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }
    .threshold-item {
      text-align: center;
      padding: 8px 12px;
      border-radius: 12px;
      background: rgba(255,255,255,0.5);
    }
    .threshold-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }
    .threshold-value {
      font-family: 'Space Mono', monospace;
      font-size: 13px;
      font-weight: 500;
    }

    /* ── OVERLAY DE PÁNICO ── */
    .panic-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.75);
      z-index: 9998;
      align-items: center;
      justify-content: center;
    }
    .panic-overlay.active {
      display: flex;
      animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    .panic-modal {
      background: white;
      border-radius: 24px;
      padding: 32px;
      text-align: center;
      max-width: 420px;
      width: 90%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
      animation: slideUp 0.4s cubic-bezier(0.34,1.56,0.64,1);
    }
    @keyframes slideUp {
      from { transform: translateY(50px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .panic-icon-large {
      font-size: 72px;
      animation: panic-pulse 0.8s ease-in-out infinite;
    }
    .panic-title {
      font-size: 24px;
      font-weight: 700;
      color: #dc2626;
      margin: 16px 0 8px;
    }
    .panic-subtitle {
      color: #64748b;
      font-size: 14px;
      margin-bottom: 8px;
      line-height: 1.5;
    }
    .panic-timestamp {
      color: #94a3b8;
      font-size: 12px;
      margin-bottom: 20px;
      font-family: 'Space Mono', monospace;
    }
    .panic-close-btn {
      background: #dc2626;
      color: white;
      border: none;
      padding: 12px 28px;
      border-radius: 10px;
      font-weight: 600;
      font-size: 15px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .panic-close-btn:hover {
      background: #b91c1c;
      transform: scale(1.03);
    }
  </style>
</head>
<body>
 
<!-- ══ CONTENEDOR DE TOASTS ══ -->
<div id="toast-container"></div>

<!-- ══ OVERLAY DE PÁNICO (se activa cuando el ESP32 envía B=true) ══ -->
<div id="panic-overlay" class="panic-overlay">
  <div class="panic-modal">
    <div class="panic-icon-large">🚨</div>
    <div class="panic-title">¡BOTÓN DE PÁNICO ACTIVADO!</div>
    <div class="panic-subtitle">El botón físico del dispositivo <strong id="panic-device">ESP32</strong> ha sido presionado.</div>
    <div class="panic-timestamp" id="panic-time">—</div>
    <button class="panic-close-btn" onclick="closePanicOverlay()">CERRAR ALERTA</button>
  </div>
</div>
 
<div class="max-w-6xl mx-auto px-4 py-8">
 
  <!-- Header -->
  <header class="mb-6 flex items-center justify-between flex-wrap gap-3">
    <div>
      <h1 class="text-3xl font-semibold text-blue-900 tracking-tight">Sistema de Monitoreo</h1>
      <p class="text-blue-400 text-sm mt-1">ESP32 · DHT11 + MPU6050 · Botón de Pánico</p>
    </div>
    <div class="flex items-center gap-4 flex-wrap">
      <!-- Reloj en vivo -->
      <div class="live-clock text-right">
        <div id="clock-time" class="font-bold text-base">--:--:--</div>
        <div id="clock-date" class="clock-date">cargando…</div>
      </div>
      <div id="badge-status" class="badge-wait">
        <span class="dot dot-gray"></span> Esperando datos…
      </div>
    </div>
  </header>

  <!-- ══ BANNER DE ALERTA SUPERIOR ══ -->
  <div id="top-alert-banner" style="display:none; width:100%; border-radius:14px; padding:13px 20px; margin-bottom:18px; font-weight:600; font-size:14px; align-items:center; gap:12px; border:1.5px solid;">
    <span id="banner-icon" style="font-size:20px; flex-shrink:0;">⚠️</span>
    <span id="banner-msgs" style="flex:1; display:flex; flex-wrap:wrap; gap:5px 14px;"></span>
    <span onclick="dismissBanner()" style="font-size:17px; opacity:0.45; cursor:pointer; flex-shrink:0;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.45">✕</span>
  </div>
 
  <!-- Alert row -->
  <div id="alert-row" class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6 hidden">
    <div id="alert-temp"   class="alert-bar alert-ok">🌡️ Temperatura normal</div>
    <div id="alert-hum"    class="alert-bar alert-ok">💧 Humedad normal</div>
    <div id="alert-gforce" class="alert-bar alert-ok">⚡ G-force normal</div>
  </div>
 
  <!-- Metric cards -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
 
    <div class="card p-5">
      <div class="flex items-center gap-3 mb-3">
        <div class="card-icon" style="background:#dbeafe">🖥️</div>
        <span class="text-blue-400 text-sm font-medium">Dispositivo</span>
      </div>
      <div id="card-device" class="mono text-blue-900 text-lg font-bold">—</div>
    </div>
 
    <div class="card p-5">
      <div class="flex items-center gap-3 mb-3">
        <div class="card-icon" style="background:#fee2e2">🌡️</div>
        <span class="text-blue-400 text-sm font-medium">Temperatura</span>
      </div>
      <div id="card-temp" class="val-big text-red-500">—</div>
      <div class="text-blue-300 text-xs mt-1">°C</div>
    </div>
 
    <div class="card p-5">
      <div class="flex items-center gap-3 mb-3">
        <div class="card-icon" style="background:#e0f2fe">💧</div>
        <span class="text-blue-400 text-sm font-medium">Humedad</span>
      </div>
      <div id="card-hum" class="val-big text-blue-500">—</div>
      <div class="text-blue-300 text-xs mt-1">%RH</div>
    </div>
 
    <div class="card p-5">
      <div class="flex items-center gap-3 mb-3">
        <div class="card-icon" style="background:#fef9c3">⚡</div>
        <span class="text-blue-400 text-sm font-medium">G-Force</span>
      </div>
      <div id="card-gforce" class="val-big text-amber-500">—</div>
      <div class="text-blue-300 text-xs mt-1">g</div>
    </div>
 
  </div>
 
  <!-- ══ UMBRALES DE VARIABLES ══ -->
  <div class="card px-6 py-4 mb-6">
    <span class="text-blue-300 text-xs font-semibold uppercase tracking-widest">Umbrales de alerta</span>
    <div class="threshold-grid mt-3">
      <div class="threshold-item">
        <div class="threshold-label" style="color:#ef4444;">🌡️ Temperatura</div>
        <div class="threshold-value" style="color:#ef4444;">Normal: 20°C – 35°C</div>
        <div class="threshold-value text-xs" style="color:#b91c1c;">Crítico: &lt;20°C o ≥35°C</div>
      </div>
      <div class="threshold-item">
        <div class="threshold-label" style="color:#3b82f6;">💧 Humedad</div>
        <div class="threshold-value" style="color:#3b82f6;">Normal: 40% – 60%</div>
        <div class="threshold-value text-xs" style="color:#1d4ed8;">Crítico: &lt;40% o ≥60%</div>
      </div>
      <div class="threshold-item">
        <div class="threshold-label" style="color:#f59e0b;">⚡ G-Force</div>
        <div class="threshold-value" style="color:#f59e0b;">Normal: &lt; 1.05 g</div>
        <div class="threshold-value text-xs" style="color:#b45309;">Mov. brusco: ≥ 1.10 g</div>
      </div>
    </div>
    <div id="card-device-full" class="text-blue-300 text-xs mt-3 text-center">—</div>
  </div>
 
  <!-- Charts: 3 columns -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
 
    <div class="card p-5 chart-wrap">
      <div class="flex items-center gap-2 mb-4">
        <span class="text-lg">🌡️</span>
        <h2 class="font-semibold text-blue-900 text-sm">Temperatura (°C)</h2>
      </div>
      <canvas id="chartTemp" height="180"></canvas>
    </div>
 
    <div class="card p-5 chart-wrap">
      <div class="flex items-center gap-2 mb-4">
        <span class="text-lg">💧</span>
        <h2 class="font-semibold text-blue-900 text-sm">Humedad (%RH)</h2>
      </div>
      <canvas id="chartHum" height="180"></canvas>
    </div>
 
    <div class="card p-5 chart-wrap">
      <div class="flex items-center gap-2 mb-4">
        <span class="text-lg">⚡</span>
        <h2 class="font-semibold text-blue-900 text-sm">G-Force (g)</h2>
      </div>
      <canvas id="chartG" height="180"></canvas>
    </div>
 
  </div>
 
  <!-- Table -->
  <div class="card p-6">
    <h2 class="font-semibold text-blue-900 mb-4">Últimas lecturas</h2>
    <div class="overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="text-blue-400 border-b border-blue-100">
            <th class="py-2 pr-6 text-left">Dispositivo</th>
            <th class="py-2 pr-6 text-left">Temp (°C)</th>
            <th class="py-2 pr-6 text-left">Humedad (%)</th>
            <th class="py-2 pr-6 text-left">G-Force (g)</th>
            <th class="py-2 pr-6 text-left">Pánico</th>
          </tr>
        </thead>
        <tbody id="table-body" class="text-blue-900"></tbody>
      </table>
    </div>
  </div>
 
  <footer class="text-center text-xs text-blue-300 mt-8">
    Flask · Chart.js · Tailwind · ESP32
  </footer>
</div>
 
<script>
/* ────────────────────────────────────────────
   CONFIGURACIÓN
──────────────────────────────────────────── */
const LOCALE = 'es-CO';
const TZ     = 'America/Bogota';
 
function fmtTs(ts) {
  if (!ts) return '—';
  let date;
  if (typeof ts === 'number') {
    date = new Date(ts * 1000);
  } else if (typeof ts === 'string') {
    date = new Date(ts);
    if (isNaN(date.getTime()) && !isNaN(Number(ts))) {
      date = new Date(Number(ts) * 1000);
    }
  } else {
    return '—';
  }
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleString(LOCALE, {
    timeZone: TZ, weekday: 'short', day: '2-digit', month: 'short',
    year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  });
}
 
function tickClock() {
  const now = new Date();
  document.getElementById('clock-time').textContent =
    now.toLocaleTimeString(LOCALE, { timeZone: TZ, hour12: false });
  document.getElementById('clock-date').textContent =
    now.toLocaleDateString(LOCALE, { timeZone: TZ, weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
}
setInterval(tickClock, 1000);
tickClock();
 
const fmt1 = v => v != null ? Number(v).toFixed(1) : '—';
const fmt2 = v => v != null ? Number(v).toFixed(2) : '—';

/* ────────────────────────────────────────────
   BOTÓN DE PÁNICO (recibido del ESP32)
──────────────────────────────────────────── */
let panicActive = false;

function triggerPanicAlert(device, timestamp) {
  if (panicActive) return; // Ya está activo, no repetir
  
  panicActive = true;
  
  // Mostrar overlay modal
  const overlay = document.getElementById('panic-overlay');
  overlay.classList.add('active');
  
  // Actualizar información en el modal
  document.getElementById('panic-device').textContent = device || 'ESP32';
  document.getElementById('panic-time').textContent = 'Activado: ' + fmtTs(timestamp);
  
  // Mostrar toast de pánico
  showToast('panic', '🚨', '¡BOTÓN DE PÁNICO ACTIVADO!', 
    `El dispositivo ${device || 'ESP32'} activó la alerta de emergencia`);
  
  // Actualizar banner superior
  const banner = document.getElementById('top-alert-banner');
  const msgsEl = document.getElementById('banner-msgs');
  const iconEl = document.getElementById('banner-icon');
  
  banner.style.display = 'flex';
  banner.style.background = 'rgba(220,38,38,0.95)';
  banner.style.color = '#ffffff';
  banner.style.borderColor = '#dc2626';
  banner.style.animation = 'banner-pulse 0.8s ease-in-out infinite';
  iconEl.textContent = '🚨';
  msgsEl.innerHTML = '<span class="banner-tag-panic">🔴 BOTÓN DE PÁNICO ACTIVADO DESDE DISPOSITIVO</span>';
  bannerDismissed = false;
  
  // Cambiar badge de estado
  const badge = document.getElementById('badge-status');
  badge.className = 'badge-panic';
  badge.innerHTML = '<span class="dot dot-red"></span> ¡PÁNICO ACTIVADO!';
  
  // Enviar solicitud para resetear el estado en el servidor
  fetch('/api/panic/reset', { method: 'POST' })
    .catch(err => console.log('Error reseteando pánico:', err));
}

function closePanicOverlay() {
  document.getElementById('panic-overlay').classList.remove('active');
  panicActive = false;
  
  // Restaurar badge
  const badge = document.getElementById('badge-status');
  badge.className = 'badge-live';
  badge.innerHTML = '<span class="dot dot-green"></span> Recibiendo';
  
  // Limpiar banner de pánico
  bannerDismissed = true;
  const banner = document.getElementById('top-alert-banner');
  banner.style.display = 'none';
}

/* ────────────────────────────────────────────
   BANNER DE ALERTA SUPERIOR
──────────────────────────────────────────── */
let bannerDismissed = false;

function dismissBanner() {
  bannerDismissed = true;
  const b = document.getElementById('top-alert-banner');
  b.style.transition = 'opacity 0.3s';
  b.style.opacity = '0';
  setTimeout(() => { b.style.display = 'none'; b.style.opacity = ''; b.style.transition = ''; }, 320);
}

function updateTopBanner(alerts) {
  if (bannerDismissed) return;
  if (panicActive) return; // No sobreescribir banner de pánico
  
  const banner = document.getElementById('top-alert-banner');
  const msgsEl = document.getElementById('banner-msgs');
  const iconEl = document.getElementById('banner-icon');
  const criticals = alerts.filter(a => a.level === 'critical');
  const warnings  = alerts.filter(a => a.level === 'warning');
  const infos     = alerts.filter(a => a.level === 'info');
  
  if (!criticals.length && !warnings.length && !infos.length) {
    banner.style.display = 'none'; return;
  }
  
  banner.style.display = 'flex';
  
  if (criticals.length > 0) {
    banner.style.background = 'rgba(254,226,226,0.97)';
    banner.style.color = '#7f1d1d';
    banner.style.borderColor = '#fca5a5';
    banner.style.animation = 'banner-pulse 1.8s ease-in-out infinite';
    iconEl.textContent = '🚨';
  } else if (warnings.length > 0) {
    banner.style.background = 'rgba(254,243,199,0.97)';
    banner.style.color = '#78350f';
    banner.style.borderColor = '#fcd34d';
    banner.style.animation = 'none';
    iconEl.textContent = '⚠️';
  } else {
    banner.style.background = 'rgba(219,234,254,0.97)';
    banner.style.color = '#1e3a5f';
    banner.style.borderColor = '#93c5fd';
    banner.style.animation = 'none';
    iconEl.textContent = 'ℹ️';
  }
  
  msgsEl.innerHTML = [...criticals, ...warnings, ...infos]
    .map(a => `<span class="banner-tag">${a.icon} ${a.msg}</span>`).join('');
}
 
/* ────────────────────────────────────────────
   SISTEMA DE TOASTS
──────────────────────────────────────────── */
const prevAlertState = { temp: null, hum: null, gforce: null };
 
function showToast(type, icon, title, msg) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `
    <div class="toast-icon">${icon}</div>
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${msg}</div>
    </div>
    <div class="toast-close">✕</div>
    <div class="toast-progress"></div>
  `;
  el.addEventListener('click', () => dismissToast(el));
  container.appendChild(el);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => el.classList.add('show'));
  });
  const duration = type === 'panic' ? 10000 : 5000;
  const timer = setTimeout(() => dismissToast(el), duration);
  el._timer = timer;
}
 
function dismissToast(el) {
  clearTimeout(el._timer);
  el.classList.replace('show', 'hide');
  el.addEventListener('transitionend', () => el.remove(), { once: true });
}
 
/* ────────────────────────────────────────────
   CHARTS
──────────────────────────────────────────── */
let tempChart, humChart, gChart;

const chartDefaults = () => ({
  responsive: true,
  animation: { duration: 300 },
  plugins: { legend: { display: false } },
  scales: {
    x: { display: false },
    y: {
      beginAtZero: false,
      grid: { color: 'rgba(147,197,253,0.2)' },
      ticks: { color: '#93c5fd', font: { family: 'Space Mono', size: 10 } }
    }
  },
  elements: { point: { radius: 0 } }
});

function mkDataset(color, fill) {
  return {
    data: [], tension: 0.35,
    borderColor: color, borderWidth: 2,
    backgroundColor: fill, fill: true
  };
}

function initCharts() {
  const ctxTemp = document.getElementById('chartTemp').getContext('2d');
  const ctxHum = document.getElementById('chartHum').getContext('2d');
  const ctxG = document.getElementById('chartG').getContext('2d');
  
  tempChart = new Chart(ctxTemp, {
    type: 'line',
    data: { labels: [], datasets: [mkDataset('#ef4444','rgba(239,68,68,0.08)')] },
    options: chartDefaults()
  });
  humChart = new Chart(ctxHum, {
    type: 'line',
    data: { labels: [], datasets: [mkDataset('#3b82f6','rgba(59,130,246,0.08)')] },
    options: chartDefaults()
  });
  gChart = new Chart(ctxG, {
    type: 'line',
    data: { labels: [], datasets: [mkDataset('#f59e0b','rgba(245,158,11,0.08)')] },
    options: chartDefaults()
  });
}
 
/* ────────────────────────────────────────────
   ALERTAS
──────────────────────────────────────────── */
function updateAlerts(last) {
  if (!last) return;
  
  // ══ VERIFICAR BOTÓN DE PÁNICO (viene del ESP32) ══
  if (last.B === true || last.B === 1 || last.B === "true") {
    triggerPanicAlert(last.device, last.ts);
  }
  
  document.getElementById('alert-row').classList.remove('hidden');
  const bannerAlerts = [];

  // ── Temperatura ──
  const at = document.getElementById('alert-temp');
  let newTempState;
  
  if (last.temp >= 35) {
    newTempState = 'critical';
    at.className = 'alert-bar alert-red';
    at.textContent = '🌡️ ¡TEMPERATURA ALTA! ≥ 35°C';
    bannerAlerts.push({ level: 'critical', icon: '🌡️', msg: `Temp alta: ${fmt1(last.temp)}°C` });
  } else if (last.temp <= 20) {
    newTempState = 'warning';
    at.className = 'alert-bar alert-blue';
    at.textContent = '🌡️ Temperatura baja: ' + fmt1(last.temp) + '°C';
    bannerAlerts.push({ level: 'info', icon: '🌡️', msg: `Temp baja: ${fmt1(last.temp)}°C` });
  } else {
    newTempState = 'ok';
    at.className = 'alert-bar alert-ok';
    at.textContent = '🌡️ Temperatura normal: ' + fmt1(last.temp) + '°C';
  }
  
  if (newTempState !== prevAlertState.temp) {
    if (newTempState === 'critical')
      showToast('critical', '🌡️', '¡Alerta de temperatura alta!', `Valor actual: ${fmt1(last.temp)} °C`);
    else if (newTempState === 'warning')
      showToast('info', '🌡️', 'Temperatura baja detectada', `Valor actual: ${fmt1(last.temp)} °C`);
    else if (prevAlertState.temp && prevAlertState.temp !== 'ok')
      showToast('ok', '🌡️', 'Temperatura normalizada', `Valor actual: ${fmt1(last.temp)} °C`);
    prevAlertState.temp = newTempState;
    bannerDismissed = false;
  }
 
  // ── Humedad (40-60%) ──
  const ah = document.getElementById('alert-hum');
  let newHumState;
  
  if (last.hum >= 60) {
    newHumState = 'critical';
    ah.className = 'alert-bar alert-red';
    ah.textContent = '💧 ¡HUMEDAD ALTA! ≥ 60%';
    bannerAlerts.push({ level: 'critical', icon: '💧', msg: `Humedad alta: ${fmt1(last.hum)}%` });
  } else if (last.hum <= 40) {
    newHumState = 'warning';
    ah.className = 'alert-bar alert-amber';
    ah.textContent = '💧 Humedad baja: ' + fmt1(last.hum) + '%';
    bannerAlerts.push({ level: 'warning', icon: '💧', msg: `Humedad baja: ${fmt1(last.hum)}%` });
  } else {
    newHumState = 'ok';
    ah.className = 'alert-bar alert-ok';
    ah.textContent = '💧 Humedad normal: ' + fmt1(last.hum) + '%';
  }
  
  if (newHumState !== prevAlertState.hum) {
    if (newHumState === 'critical')
      showToast('critical', '💧', '¡Alerta de humedad alta!', `Valor actual: ${fmt1(last.hum)} %`);
    else if (newHumState === 'warning')
      showToast('warning', '💧', 'Humedad baja detectada', `Valor actual: ${fmt1(last.hum)} %`);
    else if (prevAlertState.hum && prevAlertState.hum !== 'ok')
      showToast('ok', '💧', 'Humedad normalizada', `Valor actual: ${fmt1(last.hum)} %`);
    prevAlertState.hum = newHumState;
    bannerDismissed = false;
  }
 
  // ── G-Force (normal <1.05, movimiento brusco ≥1.10) ──
  const ag = document.getElementById('alert-gforce');
  let newGState;
  
  if (last.gforce >= 1.10) {
    newGState = 'critical';
    ag.className = 'alert-bar alert-red';
    ag.textContent = '⚡ ¡MOVIMIENTO BRUSCO! G-Force: ' + fmt2(last.gforce) + ' g';
    bannerAlerts.push({ level: 'critical', icon: '⚡', msg: `Mov. brusco: ${fmt2(last.gforce)} g` });
  } else if (last.gforce >= 1.05) {
    newGState = 'warning';
    ag.className = 'alert-bar alert-amber';
    ag.textContent = '⚡ Movimiento moderado: ' + fmt2(last.gforce) + ' g';
    bannerAlerts.push({ level: 'warning', icon: '⚡', msg: `Mov. moderado: ${fmt2(last.gforce)} g` });
  } else {
    newGState = 'ok';
    ag.className = 'alert-bar alert-ok';
    ag.textContent = '⚡ G-Force normal: ' + fmt2(last.gforce) + ' g';
  }
  
  if (newGState !== prevAlertState.gforce) {
    if (newGState === 'critical')
      showToast('critical', '⚡', '¡Alerta de movimiento brusco!', `G-Force: ${fmt2(last.gforce)} g`);
    else if (newGState === 'warning')
      showToast('warning', '⚡', 'Movimiento moderado detectado', `G-Force: ${fmt2(last.gforce)} g`);
    else if (prevAlertState.gforce && prevAlertState.gforce !== 'ok')
      showToast('ok', '⚡', 'G-Force normalizado', `Valor actual: ${fmt2(last.gforce)} g`);
    prevAlertState.gforce = newGState;
    bannerDismissed = false;
  }

  updateTopBanner(bannerAlerts);
}
 
/* ────────────────────────────────────────────
   TARJETAS
──────────────────────────────────────────── */
function updateCards(last) {
  document.getElementById('card-device').textContent = last?.device ?? '—';
  document.getElementById('card-device-full').textContent = last?.device ?? '—';
  document.getElementById('card-temp').textContent = fmt1(last?.temp);
  document.getElementById('card-hum').textContent = fmt1(last?.hum);
  document.getElementById('card-gforce').textContent = fmt2(last?.gforce);
 
  if (!panicActive) {
    const badge = document.getElementById('badge-status');
    badge.className = 'badge-live';
    badge.innerHTML = '<span class="dot dot-green"></span> Recibiendo';
  }
}
 
/* ────────────────────────────────────────────
   TABLA (con columna de pánico)
──────────────────────────────────────────── */
function repaintTable(rows) {
  const tb = document.getElementById('table-body');
  if (!tb) return;
  
  const fragment = document.createDocumentFragment();
  const recentRows = rows.slice(-20).reverse();
  
  for (const r of recentRows) {
    const tr = document.createElement('tr');
    tr.className = 'border-b border-blue-50';
    
    const panicBadge = (r.B === true || r.B === 1 || r.B === "true") 
      ? '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;">🚨 SÍ</span>'
      : '<span style="color:#94a3b8;">—</span>';
    
    tr.innerHTML = `
      <td class="py-2 pr-6 font-medium">${r.device ?? '—'}</td>
      <td class="py-2 pr-6 text-red-500 mono">${fmt1(r.temp)}</td>
      <td class="py-2 pr-6 text-blue-500 mono">${fmt1(r.hum)}</td>
      <td class="py-2 pr-6 text-amber-500 mono">${fmt2(r.gforce)}</td>
      <td class="py-2 pr-6">${panicBadge}</td>
    `;
    fragment.appendChild(tr);
  }
  
  tb.innerHTML = '';
  tb.appendChild(fragment);
}
 
/* ────────────────────────────────────────────
   FETCH PRINCIPAL
──────────────────────────────────────────── */
let isFetching = false;

async function fetchData() {
  if (isFetching) return;
  isFetching = true;
  
  try {
    const res = await fetch('/api/last?n=200');
    const payload = await res.json();
    const rows = payload.rows || [];
    
    if (!rows.length) {
      isFetching = false;
      return;
    }
    
    // Verificar si el servidor reporta pánico activo
    if (payload.panic && payload.panic.active && !panicActive) {
      triggerPanicAlert('ESP32', payload.panic.timestamp);
    }
    
    const labels = rows.map(r => r.ts);
    
    if (tempChart) {
      tempChart.data.labels = labels;
      tempChart.data.datasets[0].data = rows.map(r => r.temp);
      tempChart.update('none');
    }
    if (humChart) {
      humChart.data.labels = labels;
      humChart.data.datasets[0].data = rows.map(r => r.hum);
      humChart.update('none');
    }
    if (gChart) {
      gChart.data.labels = labels;
      gChart.data.datasets[0].data = rows.map(r => r.gforce);
      gChart.update('none');
    }
    
    repaintTable(rows);
    
    const last = rows[rows.length - 1];
    updateCards(last);
    updateAlerts(last);
    
  } catch (err) {
    console.error('Error fetching data:', err);
  } finally {
    isFetching = false;
  }
}
 
window.addEventListener('load', () => {
  initCharts();
  fetchData();
  setInterval(fetchData, 3000);
});
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.get("/api/last")
def api_last():
    try:
        n = int(request.args.get("n", 100))
    except:
        n = 100
    rows = list(data_buffer)[-n:]
    return jsonify({"rows": rows, "count": len(rows), "panic": panic_state })

@app.post("/ingest")
def ingest():
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    # Normaliza y enriquece
    row = {
        "device": data.get("device", "esp32"),
        "temp": float(data.get("temp", 0.0)),
        "hum": float(data.get("hum", 0.0)),
        "gforce": float(data.get("gforce",0.0)),
        "B": data.get("B", False),
        "ts": float(data.get("ts", time.time()))
    }
    data_buffer.append(row)
    return jsonify({"status": "ok", "stored": True})

if __name__ == "__main__":
    # Cambia el puerto si quieres
    app.run(host="0.0.0.0", port=8000, debug=False)