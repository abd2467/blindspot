/* BlindSpot intro: drifting stars, a WebGL Earth, drag to turn it, and the roll-and-dive into the app.
   No dependencies. Exposes window.BlindSpotIntro = { init(opts) }. */
(function () {
  'use strict';

  var TARGET = { lon: 112.6, lat: -2.9 };      // study area, Central Kalimantan
  var HERO_LAT = -40;                          // tilt that shows the upper arc of the planet
  var ROLL_MS = 1300, DIVE_MS = 1500;

  function createGlobe(canvas, urls, onReady) {
    var gl = canvas.getContext('webgl', { premultipliedAlpha: true, alpha: true, antialias: false });
    if (!gl) return null;
    var vs = 'attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }';
    var fs = [
      'precision highp float;',
      'uniform vec2 uC; uniform float uR; uniform float uLon; uniform float uLat; uniform vec3 uSun; uniform float uGlow;',
      'uniform sampler2D uDay; uniform sampler2D uNight; uniform sampler2D uWater;',
      'const float PI = 3.14159265;',
      'void main(){',
      '  vec2 p = (gl_FragCoord.xy - uC) / uR;',
      '  float r2 = dot(p, p); float r = sqrt(r2);',
      '  vec4 outc = vec4(0.0);',
      '  if (r2 < 1.0) {',
      '    float z = sqrt(1.0 - r2); vec3 n = vec3(p, z);',
      '    float cl = cos(uLat), sl = sin(uLat);',
      '    float yp = p.y * cl + z * sl; float zp = -p.y * sl + z * cl;',
      '    float lat = asin(clamp(yp, -1.0, 1.0)); float lon = uLon + atan(p.x, zp);',
      '    vec2 uv = vec2(fract(lon / (2.0 * PI) + 0.5), 0.5 - lat / PI);',
      '    vec3 day = texture2D(uDay, uv).rgb; vec3 night = texture2D(uNight, uv).rgb;',
      '    float water = texture2D(uWater, uv).r;',
      '    float ndl = dot(n, uSun);',
      '    float dayMix = smoothstep(-0.12, 0.22, ndl);',
      '    vec3 lit = day * (0.10 + 1.12 * pow(max(ndl, 0.0), 0.85));',
      '    vec3 nightc = night * vec3(1.0, 0.82, 0.55) * 1.6 + day * 0.025;',
      '    vec3 col = mix(nightc, lit, dayMix);',
      '    vec3 h = normalize(uSun + vec3(0.0, 0.0, 1.0));',
      '    float spec = pow(max(dot(n, h), 0.0), 140.0) * water * 0.32 * dayMix;',
      '    col += vec3(0.95, 0.97, 1.0) * spec;',
      '    float fres = pow(1.0 - z, 2.6);',
      '    col = mix(col, vec3(0.42, 0.66, 1.0) * (0.25 + 0.9 * clamp(ndl + 0.35, 0.0, 1.0)), fres * 0.75);',
      '    col = pow(col, vec3(0.92));',
      '    float aa = clamp((1.0 - r) * uR, 0.0, 1.0);',
      '    outc = vec4(col * aa, aa);',
      '  }',
      '  if (r > 0.995) {',
      '    float g = exp(-(r - 1.0) * uR / uGlow);',
      '    float side = clamp(dot(normalize(p), normalize(uSun.xy)) * 0.55 + 0.55, 0.12, 1.0);',
      '    float a = min(1.0, g) * 0.75 * side * step(1.0, r + 0.004);',
      '    outc += vec4(vec3(0.33, 0.62, 1.0) * a, a) * (1.0 - outc.a);',
      '  }',
      '  gl_FragColor = outc;',
      '}'
    ].join('\n');
    function sh(type, src) { var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; }
    var pr = gl.createProgram();
    gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
    gl.useProgram(pr);
    var buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var U = {};
    ['uC', 'uR', 'uLon', 'uLat', 'uSun', 'uGlow', 'uDay', 'uNight', 'uWater'].forEach(function (k) { U[k] = gl.getUniformLocation(pr, k); });
    var pending = 3;
    ['uDay', 'uNight', 'uWater'].forEach(function (k, unit) {
      var t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));
      gl.uniform1i(U[k], unit);
      var img = new Image();
      img.onload = function () {
        gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        pending--; if (!pending && onReady) onReady();
      };
      img.onerror = function () { pending--; if (!pending && onReady) onReady(); };
      img.src = urls[k];
    });
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    return {
      draw: function (o, cssH, dpr) {
        gl.viewport(0, 0, canvas.width, canvas.height); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.uniform2f(U.uC, o.cx * dpr, (cssH - o.cy) * dpr);
        gl.uniform1f(U.uR, o.r * dpr);
        gl.uniform1f(U.uLon, o.lon * Math.PI / 180); gl.uniform1f(U.uLat, o.lat * Math.PI / 180);
        var s = o.sun, n = Math.hypot(s[0], s[1], s[2]);
        gl.uniform3f(U.uSun, s[0] / n, s[1] / n, s[2] / n);
        gl.uniform1f(U.uGlow, 26 * dpr);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
      }
    };
  }

  function init(opts) {
    var root = opts.root, starsEl = opts.stars, globeEl = opts.globe, dragEl = opts.drag;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    var size = { w: 1, h: 1 };
    var g = { cx: 0, cy: 0, r: 1, lon: 20, lat: HERO_LAT, sun: [0, 0.62, 0.78] };
    var fly = null, spin = null, vel = { lon: 0, lat: 0 }, ready = false, running = false, raf = 0;
    var sctx = starsEl.getContext('2d');

    function heroGeom() {
      var W = size.w, H = size.h, r = Math.max(0.46 * W, 0.42 * H);
      return { cx: W / 2, cy: 0.52 * H + r, r: r };
    }
    function resize() {
      size = { w: root.clientWidth || window.innerWidth, h: root.clientHeight || window.innerHeight };
      [starsEl, globeEl].forEach(function (c) { c.width = Math.round(size.w * dpr); c.height = Math.round(size.h * dpr); });
      if (!fly) { var hg = heroGeom(); g.cx = hg.cx; g.cy = hg.cy; g.r = hg.r; }
    }
    window.addEventListener('resize', resize);
    resize();

    var globe = createGlobe(globeEl, opts.textures, function () { ready = true; });

    var seed = 7;
    function rnd() { seed = (seed * 16807) % 2147483647; return seed / 2147483647; }
    var stars = [];
    for (var i = 0; i < 560; i++) {
      var bright = rnd() > 0.985;
      stars.push({ x: rnd(), y: rnd(), r: bright ? 0.9 + rnd() * 0.4 : 0.25 + rnd() * 0.45,
        a: bright ? 0.9 : 0.18 + rnd() * 0.55, v: 0.000004 + rnd() * 0.000014, p: rnd() * 6.28,
        c: rnd() < 0.12 ? '#C8D8FF' : (rnd() < 0.08 ? '#FFE9C8' : '#FFFFFF') });
    }

    function drawStars(now) {
      var W = size.w, H = size.h;
      sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      sctx.clearRect(0, 0, W, H);
      var boost = fly ? 1 + 14 * (fly.zoom || 0) : 1;
      for (var k = 0; k < stars.length; k++) {
        var s = stars[k];
        if (!reduce) { s.x -= s.v * boost * 16; if (s.x < 0) s.x += 1; }
        sctx.globalAlpha = s.a * (0.8 + 0.2 * Math.sin(now / 1100 + s.p));
        sctx.fillStyle = s.c;
        sctx.beginPath(); sctx.arc(s.x * W, s.y * H, s.r, 0, 6.2832); sctx.fill();
      }
      sctx.globalAlpha = 1;
    }

    function ease(u) { return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; }

    function tick(now) {
      if (!running) return;
      var W = size.w, H = size.h;
      drawStars(now);
      if (fly) {
        var t = now - fly.t0, hg = heroGeom();
        if (t < fly.rollMs) {
          var e = ease(t / fly.rollMs);
          g.lon = fly.lon0 + fly.dLon * e; g.lat = fly.lat0 + (-49 - fly.lat0) * e;
          g.cx = hg.cx; g.cy = hg.cy; g.r = hg.r;
        } else {
          var u = Math.min(1, (t - fly.rollMs) / fly.diveMs);
          var ePos = 1 - Math.pow(1 - Math.min(1, u / 0.65), 3);
          var eZoom = 0.5 - 0.5 * Math.cos(Math.PI * u);
          var rEnd = Math.max(W, H) * 1.2;
          g.lon = fly.lon0 + fly.dLon; g.lat = -49 + (-49 - TARGET.lat) * -ePos;
          g.cx = hg.cx; g.cy = hg.cy + (H / 2 - hg.cy) * ePos;
          g.r = hg.r * Math.pow(rEnd / hg.r, eZoom);
          fly.zoom = eZoom;
          if (u > 0.68 && !fly.revealed) { fly.revealed = true; if (opts.onReveal) opts.onReveal(); }
          if (u >= 1) { fly = null; running = false; if (opts.onArrive) opts.onArrive(); return; }
        }
      } else if (!spin) {
        if (!reduce) g.lon += 0.06 + vel.lon;
        vel.lon *= 0.94;
        g.lat += vel.lat + (HERO_LAT - g.lat) * 0.015; vel.lat *= 0.9;
        g.lat = Math.max(-80, Math.min(10, g.lat));
      }
      if (globe && ready) globe.draw(g, H, dpr);
      raf = requestAnimationFrame(tick);
    }

    // drag to turn the globe; it keeps turning on its own otherwise
    dragEl.addEventListener('pointerdown', function (e) {
      if (fly) return;
      var r = dragEl.getBoundingClientRect();
      spin = { x: e.clientX, y: e.clientY, k: (size.w / r.width) * 180 / (Math.PI * g.r), t: performance.now() };
      vel = { lon: 0, lat: 0 };
      try { dragEl.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
      dragEl.classList.add('dragging');
    });
    dragEl.addEventListener('pointermove', function (e) {
      if (!spin) return;
      var now = performance.now(), dt = Math.max(1, now - spin.t);
      var dLon = -(e.clientX - spin.x) * spin.k, dLat = (e.clientY - spin.y) * spin.k;
      g.lon += dLon; g.lat = Math.max(-80, Math.min(10, g.lat + dLat));
      vel = { lon: dLon * 16 / dt, lat: dLat * 16 / dt };
      spin.x = e.clientX; spin.y = e.clientY; spin.t = now;
    });
    function release() {
      if (!spin) return;
      if (performance.now() - spin.t > 80) vel = { lon: 0, lat: 0 };
      spin = null; dragEl.classList.remove('dragging');
    }
    dragEl.addEventListener('pointerup', release);
    dragEl.addEventListener('pointercancel', release);

    function start() {
      if (!running) { running = true; raf = requestAnimationFrame(tick); }
    }
    function stop() { running = false; cancelAnimationFrame(raf); }

    return {
      start: start,
      stop: stop,
      // roll the study area to the top of the arc, then dive into it
      dive: function () {
        if (reduce || !globe) { if (opts.onReveal) opts.onReveal(); if (opts.onArrive) opts.onArrive(); return; }
        var dLon = ((TARGET.lon - g.lon) % 360 + 540) % 360 - 180;
        if (Math.abs(dLon) < 70) dLon += dLon >= 0 ? 360 : -360;
        fly = { t0: performance.now(), rollMs: ROLL_MS, diveMs: DIVE_MS, lon0: g.lon, dLon: dLon, lat0: g.lat };
        start();
      },
      reset: function () {
        fly = null; vel = { lon: 0, lat: 0 };
        g.lon = 20; g.lat = HERO_LAT; g.sun = [0, 0.62, 0.78];
        var hg = heroGeom(); g.cx = hg.cx; g.cy = hg.cy; g.r = hg.r;
        start();
      }
    };
  }

  window.BlindSpotIntro = { init: init };
})();
