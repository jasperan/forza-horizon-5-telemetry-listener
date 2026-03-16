/* ==========================================================================
   Forza Telemetry Dashboard - app.js
   Zero dependencies. Vanilla JS. Canvas gauges, track map, coach feed.
   ========================================================================== */

(function () {
    'use strict';

    // ── Global State ─────────────────────────────────────────────────────
    let latestData = null;
    let trackPoints = [];         // {x, z, speed}
    let gForceTrail = [];         // last 60 {x, z} samples
    let bestLapTime = Infinity;
    let lastLapNumber = 0;
    let lastSessionId = null;

    const MAX_GFORCE_TRAIL = 60;
    const MAX_COACH_ITEMS = 8;
    const DEG = Math.PI / 180;

    // ── DOM References ───────────────────────────────────────────────────
    const $ = (id) => document.getElementById(id);

    const dom = {
        connectionStatus: $('connection-status'),
        statusText: document.querySelector('#connection-status .status-text'),
        modeToggle: $('mode-toggle'),
        // Full mode
        rpmCanvas: $('rpm-gauge'),
        speedCanvas: $('speed-gauge'),
        trackCanvas: $('track-map'),
        gforceCanvas: $('gforce-circle'),
        gearDisplay: $('gear-display'),
        speedDisplay: $('speed-display'),
        tireFL: $('tire-fl'),
        tireFR: $('tire-fr'),
        tireRL: $('tire-rl'),
        tireRR: $('tire-rr'),
        deltaValue: $('delta-value'),
        bestLap: $('best-lap'),
        currentLap: $('current-lap'),
        lapCount: $('lap-count'),
        coachFeed: $('coach-feed'),
        throttleBar: $('throttle-bar'),
        brakeBar: $('brake-bar'),
        steerIndicator: $('steer-indicator'),
        throttleVal: $('throttle-val'),
        brakeVal: $('brake-val'),
        steerVal: $('steer-val'),
        // Compact mode
        compactGear: $('compact-gear'),
        compactSpeed: $('compact-speed'),
        compactThrottle: $('compact-throttle'),
        compactBrake: $('compact-brake'),
        compactDelta: $('compact-delta'),
        compactCoachMsg: $('compact-coach-msg'),
    };

    // Canvas 2D contexts
    const rpmCtx = dom.rpmCanvas.getContext('2d');
    const speedCtx = dom.speedCanvas.getContext('2d');
    const trackCtx = dom.trackCanvas.getContext('2d');
    const gforceCtx = dom.gforceCanvas.getContext('2d');

    // ── Connection Status ────────────────────────────────────────────────
    function updateConnectionStatus(connected) {
        if (connected) {
            dom.connectionStatus.className = 'connected';
            dom.statusText.textContent = 'Connected';
        } else {
            dom.connectionStatus.className = 'disconnected';
            dom.statusText.textContent = 'Disconnected';
        }
    }

    // ── WebSocket with Auto-Reconnect ────────────────────────────────────
    class TelemetrySocket {
        constructor(path, onMessage) {
            this.url = 'ws://' + window.location.host + path;
            this.onMessage = onMessage;
            this.reconnectDelay = 2000;
            this.connect();
        }

        connect() {
            this.ws = new WebSocket(this.url);
            this.ws.onmessage = (e) => {
                try {
                    this.onMessage(JSON.parse(e.data));
                } catch (err) {
                    // ignore malformed messages
                }
            };
            this.ws.onopen = () => updateConnectionStatus(true);
            this.ws.onerror = () => updateConnectionStatus(false);
            this.ws.onclose = () => {
                updateConnectionStatus(false);
                setTimeout(() => this.connect(), this.reconnectDelay);
            };
        }

        send(data) {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify(data));
            }
        }
    }

    // ── Utility: Format Time ─────────────────────────────────────────────
    function formatLapTime(seconds) {
        if (!seconds || seconds <= 0 || seconds === Infinity) return '--:--.---';
        var mins = Math.floor(seconds / 60);
        var secs = seconds - mins * 60;
        var secsStr = secs.toFixed(3);
        if (secs < 10) secsStr = '0' + secsStr;
        return mins + ':' + secsStr;
    }

    function formatDelta(seconds) {
        if (seconds === 0 || seconds == null) return '+0.000';
        var sign = seconds >= 0 ? '+' : '-';
        return sign + Math.abs(seconds).toFixed(3);
    }

    // ── Utility: Color Interpolation ─────────────────────────────────────
    function lerpColor(a, b, t) {
        // a, b are [r, g, b], t is 0..1
        return [
            Math.round(a[0] + (b[0] - a[0]) * t),
            Math.round(a[1] + (b[1] - a[1]) * t),
            Math.round(a[2] + (b[2] - a[2]) * t),
        ];
    }

    function rpmColor(ratio) {
        // green -> yellow -> red
        if (ratio < 0.5) {
            var c = lerpColor([46, 204, 113], [241, 196, 15], ratio * 2);
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        var c = lerpColor([241, 196, 15], [231, 76, 60], (ratio - 0.5) * 2);
        return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
    }

    function speedColor(ratio) {
        // blue -> cyan -> white
        if (ratio < 0.5) {
            var c = lerpColor([52, 152, 219], [26, 188, 220], ratio * 2);
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        var c = lerpColor([26, 188, 220], [236, 240, 241], (ratio - 0.5) * 2);
        return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
    }

    function trackSpeedColor(ratio) {
        // blue (slow) -> green -> yellow -> red (fast)
        if (ratio < 0.33) {
            var c = lerpColor([52, 152, 219], [46, 204, 113], ratio / 0.33);
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        if (ratio < 0.66) {
            var c = lerpColor([46, 204, 113], [241, 196, 15], (ratio - 0.33) / 0.33);
            return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
        }
        var c = lerpColor([241, 196, 15], [231, 76, 60], (ratio - 0.66) / 0.34);
        return 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';
    }

    // ── Arc Gauge Drawing ────────────────────────────────────────────────
    function drawArcGauge(ctx, canvas, value, maxValue, colorFn, label) {
        var w = canvas.width;
        var h = canvas.height;
        var cx = w / 2;
        var cy = h / 2;
        var radius = Math.min(w, h) * 0.38;
        var lineWidth = radius * 0.18;

        // Arc angles: 210deg start, 330deg end (240deg sweep)
        var startAngle = 150 * DEG;   // 210 deg from top = 150 deg in canvas coords (canvas 0 = 3 o'clock)
        var endAngle = 390 * DEG;     // 330 deg from top = 390 deg canvas
        var sweepAngle = endAngle - startAngle;

        var ratio = Math.min(Math.max(value / (maxValue || 1), 0), 1);
        var valueAngle = startAngle + sweepAngle * ratio;

        ctx.clearRect(0, 0, w, h);

        // Background arc
        ctx.beginPath();
        ctx.arc(cx, cy, radius, startAngle, endAngle);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.lineWidth = lineWidth;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Value arc (segmented for color gradient)
        if (ratio > 0.001) {
            var segments = 60;
            var segSweep = (valueAngle - startAngle) / segments;
            for (var i = 0; i < segments; i++) {
                var segRatio = i / segments;
                var a1 = startAngle + segSweep * i;
                var a2 = a1 + segSweep + 0.01; // tiny overlap to avoid gaps
                ctx.beginPath();
                ctx.arc(cx, cy, radius, a1, a2);
                ctx.strokeStyle = colorFn(segRatio * ratio);
                ctx.lineWidth = lineWidth;
                ctx.lineCap = 'butt';
                ctx.stroke();
            }
        }

        // Redline zone marker (>90% of max)
        if (maxValue > 0) {
            var redlineStart = startAngle + sweepAngle * 0.9;
            ctx.beginPath();
            ctx.arc(cx, cy, radius + lineWidth * 0.7, redlineStart, endAngle);
            ctx.strokeStyle = 'rgba(231, 76, 60, 0.3)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Tick marks
        var tickCount = 8;
        for (var i = 0; i <= tickCount; i++) {
            var tickAngle = startAngle + (sweepAngle * i) / tickCount;
            var innerR = radius + lineWidth * 0.6;
            var outerR = radius + lineWidth * 0.9;
            ctx.beginPath();
            ctx.moveTo(cx + Math.cos(tickAngle) * innerR, cy + Math.sin(tickAngle) * innerR);
            ctx.lineTo(cx + Math.cos(tickAngle) * outerR, cy + Math.sin(tickAngle) * outerR);
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // Numeric value below center
        ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.font = '600 12px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, cx, cy + radius * 0.6);
    }

    // ── RPM Gauge ────────────────────────────────────────────────────────
    function drawRPM() {
        if (!latestData) return;
        var rpm = latestData.current_engine_rpm || 0;
        var maxRpm = latestData.engine_max_rpm || 9000;
        drawArcGauge(rpmCtx, dom.rpmCanvas, rpm, maxRpm, rpmColor, Math.round(rpm).toLocaleString() + ' RPM');
    }

    // ── Speed Gauge ──────────────────────────────────────────────────────
    function drawSpeed() {
        if (!latestData) return;
        var speedMs = latestData.speed || 0;
        var speedKmh = speedMs * 3.6;
        var maxSpeed = 400; // reasonable max for Forza
        drawArcGauge(speedCtx, dom.speedCanvas, speedKmh, maxSpeed, speedColor, Math.round(speedKmh) + ' KM/H');
    }

    // ── G-Force Circle ──────────────────────────────────────────────────
    function drawGForce() {
        var canvas = dom.gforceCanvas;
        var w = canvas.width;
        var h = canvas.height;
        var cx = w / 2;
        var cy = h / 2;
        var radius = Math.min(w, h) * 0.42;

        gforceCtx.clearRect(0, 0, w, h);

        // Outer circle
        gforceCtx.beginPath();
        gforceCtx.arc(cx, cy, radius, 0, Math.PI * 2);
        gforceCtx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        gforceCtx.lineWidth = 1;
        gforceCtx.stroke();

        // Inner circles (0.5G, 1G)
        gforceCtx.beginPath();
        gforceCtx.arc(cx, cy, radius * 0.5, 0, Math.PI * 2);
        gforceCtx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        gforceCtx.stroke();

        // Crosshairs
        gforceCtx.beginPath();
        gforceCtx.moveTo(cx - radius, cy);
        gforceCtx.lineTo(cx + radius, cy);
        gforceCtx.moveTo(cx, cy - radius);
        gforceCtx.lineTo(cx, cy + radius);
        gforceCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        gforceCtx.lineWidth = 1;
        gforceCtx.stroke();

        // Labels
        gforceCtx.fillStyle = 'rgba(255, 255, 255, 0.25)';
        gforceCtx.font = '9px system-ui, sans-serif';
        gforceCtx.textAlign = 'center';
        gforceCtx.fillText('BRAKE', cx, cy - radius + 12);
        gforceCtx.fillText('ACCEL', cx, cy + radius - 6);
        gforceCtx.textAlign = 'left';
        gforceCtx.fillText('L', cx - radius + 4, cy - 4);
        gforceCtx.textAlign = 'right';
        gforceCtx.fillText('R', cx + radius - 4, cy - 4);

        // Trail dots (fading)
        for (var i = 0; i < gForceTrail.length; i++) {
            var sample = gForceTrail[i];
            var alpha = (i + 1) / gForceTrail.length * 0.4;
            var dotX = cx + (sample.x / 2) * radius; // normalize: 2G = full radius
            var dotY = cy - (sample.z / 2) * radius; // invert Z: positive = braking = up

            // Clamp to circle
            var dx = dotX - cx;
            var dy = dotY - cy;
            var dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > radius) {
                dotX = cx + (dx / dist) * radius;
                dotY = cy + (dy / dist) * radius;
            }

            gforceCtx.beginPath();
            gforceCtx.arc(dotX, dotY, 2, 0, Math.PI * 2);
            gforceCtx.fillStyle = 'rgba(52, 152, 219, ' + alpha + ')';
            gforceCtx.fill();
        }

        // Current dot
        if (latestData) {
            var gx = latestData.acceleration_x || 0;
            var gz = latestData.acceleration_z || 0;
            var curX = cx + (gx / 2) * radius;
            var curY = cy - (gz / 2) * radius;

            // Clamp
            var cdx = curX - cx;
            var cdy = curY - cy;
            var cdist = Math.sqrt(cdx * cdx + cdy * cdy);
            if (cdist > radius) {
                curX = cx + (cdx / cdist) * radius;
                curY = cy + (cdy / cdist) * radius;
            }

            // Glow
            gforceCtx.beginPath();
            gforceCtx.arc(curX, curY, 6, 0, Math.PI * 2);
            var glow = gforceCtx.createRadialGradient(curX, curY, 0, curX, curY, 6);
            glow.addColorStop(0, 'rgba(231, 76, 60, 0.8)');
            glow.addColorStop(1, 'rgba(231, 76, 60, 0)');
            gforceCtx.fillStyle = glow;
            gforceCtx.fill();

            // Dot
            gforceCtx.beginPath();
            gforceCtx.arc(curX, curY, 3, 0, Math.PI * 2);
            gforceCtx.fillStyle = '#e74c3c';
            gforceCtx.fill();
        }
    }

    // ── Track Map ────────────────────────────────────────────────────────
    function drawTrackMap() {
        var canvas = dom.trackCanvas;
        var w = canvas.width;
        var h = canvas.height;
        var pad = 30;

        trackCtx.clearRect(0, 0, w, h);

        if (trackPoints.length < 2) {
            trackCtx.fillStyle = 'rgba(255, 255, 255, 0.15)';
            trackCtx.font = '12px system-ui, sans-serif';
            trackCtx.textAlign = 'center';
            trackCtx.fillText('Waiting for position data...', w / 2, h / 2);
            return;
        }

        // Compute bounds
        var minX = Infinity, maxX = -Infinity;
        var minZ = Infinity, maxZ = -Infinity;
        var minSpd = Infinity, maxSpd = -Infinity;

        for (var i = 0; i < trackPoints.length; i++) {
            var p = trackPoints[i];
            if (p.x < minX) minX = p.x;
            if (p.x > maxX) maxX = p.x;
            if (p.z < minZ) minZ = p.z;
            if (p.z > maxZ) maxZ = p.z;
            if (p.speed < minSpd) minSpd = p.speed;
            if (p.speed > maxSpd) maxSpd = p.speed;
        }

        var rangeX = maxX - minX || 1;
        var rangeZ = maxZ - minZ || 1;
        var spdRange = maxSpd - minSpd || 1;

        // Scale to fit canvas with padding, maintain aspect ratio
        var scaleX = (w - pad * 2) / rangeX;
        var scaleZ = (h - pad * 2) / rangeZ;
        var scale = Math.min(scaleX, scaleZ);
        var offsetX = (w - rangeX * scale) / 2;
        var offsetZ = (h - rangeZ * scale) / 2;

        function mapPoint(p) {
            return {
                x: offsetX + (p.x - minX) * scale,
                y: offsetZ + (p.z - minZ) * scale,
            };
        }

        // Draw track path, color by speed
        for (var i = 1; i < trackPoints.length; i++) {
            var a = mapPoint(trackPoints[i - 1]);
            var b = mapPoint(trackPoints[i]);
            var spdRatio = (trackPoints[i].speed - minSpd) / spdRange;

            trackCtx.beginPath();
            trackCtx.moveTo(a.x, a.y);
            trackCtx.lineTo(b.x, b.y);
            trackCtx.strokeStyle = trackSpeedColor(spdRatio);
            trackCtx.lineWidth = 2;
            trackCtx.stroke();
        }

        // Current position: bright white dot with glow
        var last = mapPoint(trackPoints[trackPoints.length - 1]);

        trackCtx.beginPath();
        trackCtx.arc(last.x, last.y, 8, 0, Math.PI * 2);
        var posGlow = trackCtx.createRadialGradient(last.x, last.y, 0, last.x, last.y, 8);
        posGlow.addColorStop(0, 'rgba(255, 255, 255, 0.9)');
        posGlow.addColorStop(1, 'rgba(255, 255, 255, 0)');
        trackCtx.fillStyle = posGlow;
        trackCtx.fill();

        trackCtx.beginPath();
        trackCtx.arc(last.x, last.y, 3, 0, Math.PI * 2);
        trackCtx.fillStyle = '#fff';
        trackCtx.fill();
    }

    // ── Tire Temps (DOM) ─────────────────────────────────────────────────
    function updateTireTemp(el, temp) {
        var tempC = Math.round(temp);
        var tempSpan = el.querySelector('.tire-temp');
        tempSpan.textContent = tempC + '\u00B0C';

        // Remove all state classes
        el.classList.remove('cold', 'optimal', 'hot');

        if (tempC < 150) {
            el.classList.add('cold');
        } else if (tempC <= 200) {
            el.classList.add('optimal');
        } else {
            el.classList.add('hot');
        }
    }

    function updateTires() {
        if (!latestData) return;
        updateTireTemp(dom.tireFL, latestData.tire_temp_FL || 0);
        updateTireTemp(dom.tireFR, latestData.tire_temp_FR || 0);
        updateTireTemp(dom.tireRL, latestData.tire_temp_RL || 0);
        updateTireTemp(dom.tireRR, latestData.tire_temp_RR || 0);
    }

    // ── Lap Delta (DOM) ──────────────────────────────────────────────────
    function updateDelta() {
        if (!latestData) return;

        var currentLapTime = latestData.current_lap || 0;
        var bestTime = latestData.best_lap || 0;
        var lapNum = latestData.lap_number || 0;

        // Update best lap tracking
        if (bestTime > 0 && bestTime < bestLapTime) {
            bestLapTime = bestTime;
        }

        // Calculate delta (current vs best at same distance, approximate with time)
        var delta = latestData.last_lap_delta || 0;

        // Delta display
        dom.deltaValue.textContent = formatDelta(delta);
        dom.deltaValue.className = 'delta-time ' + (
            delta < -0.001 ? 'negative' :
            delta > 0.001 ? 'positive' : 'neutral'
        );

        dom.bestLap.textContent = formatLapTime(bestLapTime === Infinity ? 0 : bestLapTime);
        dom.currentLap.textContent = formatLapTime(currentLapTime);
        dom.lapCount.textContent = lapNum;

        // Compact mode
        dom.compactDelta.textContent = formatDelta(delta);
        dom.compactDelta.className = 'compact-delta-val ' + (
            delta < -0.001 ? 'negative' :
            delta > 0.001 ? 'positive' : 'neutral'
        );
    }

    // ── Inputs (DOM) ─────────────────────────────────────────────────────
    function updateInputs() {
        if (!latestData) return;

        var throttle = latestData.accel || 0;    // 0-255
        var brake = latestData.brake || 0;       // 0-255
        var steer = latestData.steer || 0;       // -127 to +127

        var throttlePct = Math.round((throttle / 255) * 100);
        var brakePct = Math.round((brake / 255) * 100);

        // Full mode
        dom.throttleBar.style.width = throttlePct + '%';
        dom.brakeBar.style.width = brakePct + '%';
        dom.throttleVal.textContent = throttlePct + '%';
        dom.brakeVal.textContent = brakePct + '%';

        // Steering: -127 to +127, map to 0% - 100% (50% = center)
        var steerPct = 50 + (steer / 127) * 50;
        steerPct = Math.max(0, Math.min(100, steerPct));
        dom.steerIndicator.style.left = steerPct + '%';
        dom.steerVal.textContent = Math.round(steer) + '\u00B0';

        // Compact mode
        dom.compactThrottle.style.width = throttlePct + '%';
        dom.compactBrake.style.width = brakePct + '%';
    }

    // ── Gear + Speed (DOM overlay) ───────────────────────────────────────
    function updateGearSpeed() {
        if (!latestData) return;

        var gear = latestData.gear || 0;
        var gearStr = gear === 0 ? 'R' : gear === 11 ? 'N' : String(gear);
        var speedKmh = Math.round((latestData.speed || 0) * 3.6);

        dom.gearDisplay.textContent = gearStr;
        dom.speedDisplay.textContent = speedKmh;

        // Compact
        dom.compactGear.textContent = gearStr;
        dom.compactSpeed.textContent = speedKmh;
    }

    // ── Coach Feed (DOM) ─────────────────────────────────────────────────
    function addCoachAlert(alert) {
        var li = document.createElement('li');

        // Severity class
        if (alert.severity === 'critical') {
            li.className = 'critical';
        } else if (alert.severity === 'warning') {
            li.className = 'warning';
        }

        // Timestamp
        var timeSpan = document.createElement('span');
        timeSpan.className = 'coach-time';
        var now = new Date();
        timeSpan.textContent = now.toTimeString().slice(0, 8);

        // Rule badge
        var badge = '';
        if (alert.rule) {
            badge = '[' + alert.rule + '] ';
        }

        li.appendChild(timeSpan);
        li.appendChild(document.createTextNode(badge + (alert.message || alert.msg || '')));

        // Prepend (newest first)
        dom.coachFeed.insertBefore(li, dom.coachFeed.firstChild);

        // Trim to max items
        while (dom.coachFeed.children.length > MAX_COACH_ITEMS) {
            dom.coachFeed.removeChild(dom.coachFeed.lastChild);
        }

        // Update compact coach
        dom.compactCoachMsg.textContent = badge + (alert.message || alert.msg || '');
    }

    // ── Telemetry Data Handler ───────────────────────────────────────────
    function onTelemetryData(data) {
        latestData = data;

        // Detect session change (clear track)
        var sessionId = data.session_id || data.race_id || null;
        if (sessionId && sessionId !== lastSessionId) {
            trackPoints = [];
            bestLapTime = Infinity;
            lastSessionId = sessionId;
        }

        // Accumulate track points (throttle to avoid memory bloat)
        if (data.position_x != null && data.position_z != null) {
            var lastPt = trackPoints.length > 0 ? trackPoints[trackPoints.length - 1] : null;
            var dx = lastPt ? data.position_x - lastPt.x : Infinity;
            var dz = lastPt ? data.position_z - lastPt.z : Infinity;
            var dist = Math.sqrt(dx * dx + dz * dz);
            // Only add if moved at least 2m
            if (dist > 2) {
                trackPoints.push({
                    x: data.position_x,
                    z: data.position_z,
                    speed: data.speed || 0,
                });
                // Cap at 10000 points
                if (trackPoints.length > 10000) {
                    trackPoints = trackPoints.slice(-8000);
                }
            }
        }

        // G-force trail
        if (data.acceleration_x != null && data.acceleration_z != null) {
            gForceTrail.push({
                x: data.acceleration_x,
                z: data.acceleration_z,
            });
            if (gForceTrail.length > MAX_GFORCE_TRAIL) {
                gForceTrail.shift();
            }
        }

        // Detect new lap for best time tracking
        var lapNum = data.lap_number || 0;
        if (lapNum > lastLapNumber && lastLapNumber > 0) {
            var lastLapTime = data.last_lap || 0;
            if (lastLapTime > 0 && lastLapTime < bestLapTime) {
                bestLapTime = lastLapTime;
            }
        }
        lastLapNumber = lapNum;

        // Update DOM elements (these are cheap, do on every packet)
        updateGearSpeed();
        updateTires();
        updateDelta();
        updateInputs();
    }

    // ── Coach Data Handler ───────────────────────────────────────────────
    function onCoachData(data) {
        // Could be a single alert or an array
        if (Array.isArray(data)) {
            for (var i = 0; i < data.length; i++) {
                addCoachAlert(data[i]);
            }
        } else {
            addCoachAlert(data);
        }
    }

    // ── 60fps Render Loop ────────────────────────────────────────────────
    function renderLoop() {
        drawRPM();
        drawSpeed();
        drawGForce();
        drawTrackMap();
        requestAnimationFrame(renderLoop);
    }

    // ── Mode Toggle ──────────────────────────────────────────────────────
    function toggleMode() {
        var body = document.body;
        if (body.dataset.mode === 'full') {
            body.dataset.mode = 'compact';
        } else {
            body.dataset.mode = 'full';
        }
    }

    function initMode() {
        var params = new URLSearchParams(window.location.search);
        var mode = params.get('mode');
        if (mode === 'compact' || mode === 'full') {
            document.body.dataset.mode = mode;
        }
    }

    // ── Keyboard Shortcuts ───────────────────────────────────────────────
    document.addEventListener('keydown', function (e) {
        if (e.key === 'm' || e.key === 'M') {
            // Don't toggle if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            toggleMode();
        }
    });

    // ── Initialize ───────────────────────────────────────────────────────
    function init() {
        initMode();

        // Mode toggle button
        dom.modeToggle.addEventListener('click', toggleMode);

        // Connect WebSockets
        new TelemetrySocket('/ws/telemetry', onTelemetryData);
        new TelemetrySocket('/ws/coach', onCoachData);

        // Start render loop
        requestAnimationFrame(renderLoop);
    }

    // Wait for DOM if needed (script is deferred, so this is a safety net)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
