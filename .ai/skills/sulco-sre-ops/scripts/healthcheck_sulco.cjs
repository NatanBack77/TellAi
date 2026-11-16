#!/usr/bin/env node
/**
 * healthcheck_sulco.cjs - SRE automated health check and latency inspector for SULCO services
 * Usage: node healthcheck_sulco.cjs [--api-port 8000] [--app-port 8501] [--frontend-port 5173]
 */

const http = require('http');

function parseArgs() {
  const args = process.argv.slice(2);
  const cfg = {
    apiPort: 8000,
    appPort: 8501,
    frontendPort: 5173,
    host: '127.0.0.1'
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--api-port' && args[i + 1]) cfg.apiPort = parseInt(args[++i], 10);
    else if (args[i] === '--app-port' && args[i + 1]) cfg.appPort = parseInt(args[++i], 10);
    else if (args[i] === '--frontend-port' && args[i + 1]) cfg.frontendPort = parseInt(args[++i], 10);
  }
  return cfg;
}

function probeUrl(url, timeoutMs = 4000) {
  const t0 = Date.now();
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let body = '';
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => {
        resolve({
          up: res.statusCode >= 200 && res.statusCode < 400,
          status_code: res.statusCode,
          latency_ms: Date.now() - t0,
          data: body
        });
      });
    });

    req.on('error', (err) => {
      resolve({ up: false, status_code: null, latency_ms: Date.now() - t0, error: err.message });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ up: false, status_code: null, latency_ms: Date.now() - t0, error: 'Connection Timeout' });
    });
  });
}

async function runHealthCheck() {
  const cfg = parseArgs();

  const apiRes = await probeUrl(`http://${cfg.host}:${cfg.apiPort}/saude`);
  const appRes = await probeUrl(`http://${cfg.host}:${cfg.appPort}/_stcore/health`);
  const frontRes = await probeUrl(`http://${cfg.host}:${cfg.frontendPort}`);

  let apiDetails = null;
  if (apiRes.up) {
    try {
      apiDetails = JSON.parse(apiRes.data);
    } catch (_) {
      apiDetails = apiRes.data.slice(0, 100);
    }
  }

  const result = {
    timestamp: new Date().toISOString(),
    overall_status: (apiRes.up && appRes.up) ? 'HEALTHY' : 'DEGRADED',
    services: {
      fastapi_backend: {
        up: apiRes.up,
        port: cfg.apiPort,
        latency_ms: apiRes.latency_ms,
        health_status: apiDetails ? apiDetails.status : (apiRes.error || 'unreachable'),
        points_monitored: apiDetails ? apiDetails.n_pontos : null,
        model_cache_ready: apiDetails ? apiDetails.cache_modelo_previsao : false
      },
      streamlit_app: {
        up: appRes.up,
        port: cfg.appPort,
        latency_ms: appRes.latency_ms,
        health_status: appRes.up ? 'ok' : (appRes.error || 'unreachable')
      },
      maira_frontend: {
        up: frontRes.up,
        port: cfg.frontendPort,
        latency_ms: frontRes.latency_ms,
        status: frontRes.up ? 'ready' : (frontRes.error || 'unreachable')
      }
    }
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(result.overall_status === 'HEALTHY' ? 0 : 1);
}

runHealthCheck();
