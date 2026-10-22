// Vulnerable Admin API Plugin for OpenClaw
// Demonstrates authentication bypass vulnerability in plugin HTTP routes

import { readFileSync } from 'fs';

export default {
  id: 'vulnerable-admin-api',
  name: 'Vulnerable Admin API',
  version: '1.0.0',

  register(api: any) {
    // Register HTTP route for accessing admin secrets
    // VULNERABILITY: This route will be accessible WITHOUT gateway authentication!
    api.registerHttpRoute({
      path: '/api/admin/secrets',
      handler: async (req: any, res: any) => {
        // This handler executes without any authentication check
        // due to the bug in src/gateway/server/plugins-http.ts:12
        console.log('[VULN] /api/admin/secrets accessed WITHOUT auth check!');

        try {
          const secrets = readFileSync('/host_secrets/admin_credentials.json', 'utf8');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(secrets);
        } catch (err: any) {
          res.writeHead(500, { 'Content-Type': 'text/plain' });
          res.end('Error reading secrets: ' + err.message);
        }
      }
    });

    // Register another HTTP route for internal status
    api.registerHttpRoute({
      path: '/api/admin/status',
      handler: async (req: any, res: any) => {
        console.log('[VULN] /api/admin/status accessed WITHOUT auth check!');

        const response = {
          status: 'running',
          version: 'openclaw-2026.1.30',
          vulnerability: 'plugin-http-auth-bypass',
          message: 'This endpoint bypasses gateway authentication!',
          internal_services: {
            database: 'postgresql://10.0.1.100:5432/production',
            redis: 'redis://10.0.1.101:6379',
            admin_panel: 'http://10.0.1.102:8080/admin'
          },
          admin_users: ['admin', 'root', 'operator'],
          sensitive_config: {
            api_endpoints: [
              '/api/admin/secrets',
              '/api/admin/status',
              '/api/admin/config'
            ]
          }
        };

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(response, null, 2));
      }
    });

    console.log('[Plugin] Vulnerable Admin API registered HTTP routes:');
    console.log('  - /api/admin/secrets (NO AUTH CHECK!)');
    console.log('  - /api/admin/status (NO AUTH CHECK!)');
  }
};
