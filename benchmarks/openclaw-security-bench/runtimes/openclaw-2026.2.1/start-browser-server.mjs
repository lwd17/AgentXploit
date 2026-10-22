#!/usr/bin/env node
// Start OpenClaw browser control HTTP server directly (for security testing)
// This bypasses the gateway and exposes the vulnerable /act endpoint via HTTP

import express from "../openclaw-source/node_modules/express/index.js";
import { loadConfig } from "../openclaw-source/dist/config/config.js";
import { resolveBrowserConfig, resolveProfile } from "../openclaw-source/dist/browser/config.js";
import { ensureChromeExtensionRelayServer } from "../openclaw-source/dist/browser/extension-relay.js";
import { registerBrowserRoutes } from "../openclaw-source/dist/browser/routes/index.js";
import { createBrowserRouteContext } from "../openclaw-source/dist/browser/server-context.js";

console.log("========================================");
console.log("OpenClaw Browser Control HTTP Server");
console.log("========================================");
console.log("");
console.log("[*] Starting browser control HTTP server...");
console.log("[!] WARNING: evaluateEnabled=true (VULNERABLE)");
console.log("");

// Create custom server that binds to 0.0.0.0 instead of 127.0.0.1
async function startBrowserServerOnAllInterfaces() {
  const cfg = loadConfig();
  const resolved = resolveBrowserConfig(cfg.browser, cfg);
  if (!resolved.enabled) {
    throw new Error("Browser not enabled");
  }

  const app = express();
  app.use(express.json({ limit: "1mb" }));

  let state = null;
  const ctx = createBrowserRouteContext({
    getState: () => state,
  });
  registerBrowserRoutes(app, ctx);

  const port = resolved.controlPort;
  const bindHost = "0.0.0.0"; // Bind to all interfaces for cross-container access

  const server = await new Promise((resolve, reject) => {
    const s = app.listen(port, bindHost, () => resolve(s));
    s.once("error", reject);
  });

  state = {
    server,
    port,
    resolved,
    profiles: new Map(),
  };

  // Initialize extension relay if needed
  for (const name of Object.keys(resolved.profiles)) {
    const profile = resolveProfile(resolved, name);
    if (profile && profile.driver === "extension") {
      await ensureChromeExtensionRelayServer({ cdpUrl: profile.cdpUrl }).catch(() => {});
    }
  }

  console.log(`[browser/server] Browser control listening on http://${bindHost}:${port}/`);
  return state;
}

try {
  const state = await startBrowserServerOnAllInterfaces();

  if (state && state.server) {
    const port = state.port;
    console.log(`[✓] Browser control HTTP server started on port ${port}`);
    console.log(`[✓] Vulnerable endpoint: POST http://localhost:${port}/act`);
    console.log(`[✓] Test command: curl -X POST http://localhost:${port}/act \\`);
    console.log(`      -H "Content-Type: application/json" \\`);
    console.log(`      -d '{"kind":"evaluate","fn":"1+1"}'`);
    console.log("");
    console.log("========================================");
    console.log("Server ready - Press Ctrl+C to stop");
    console.log("========================================");

    // Keep process running
    process.on('SIGTERM', () => {
      console.log("\n[*] Shutting down...");
      process.exit(0);
    });

    process.on('SIGINT', () => {
      console.log("\n[*] Shutting down...");
      process.exit(0);
    });
  } else {
    console.error("[✗] Failed to start browser control server");
    process.exit(1);
  }
} catch (error) {
  console.error("[✗] Error starting server:", error);
  process.exit(1);
}
