const express = require('express');
const http = require('http');
const WebSocket = require('ws');
const helmet = require('helmet');
const cors = require('cors');
const jwt = require('jsonwebtoken');
const { OAuth2Server } = require('oauth2-server');
const config = require('./config/auth');
const { loadOpenAPISpec } = require('./config/openapi');
const { authenticateToken, oauth2Middleware } = require('./middleware/auth');
const logger = require('./middleware/logging');
const { generateMCPToolsFromOpenAPI } = require('./utils/openapi-parser');
const { StreamingResponse } = require('./utils/streaming');

const app = express();
const server = http.createServer(app);

// WebSocket server configuration
const wss = new WebSocket.Server({
  server,
  path: '/ws',
  perMessageDeflate: true,
  maxPayload: 1024 * 1024, // 1MB
  clientTracking: true,
  verifyClient: (info) => {
    // Verify OAuth 2.1 token from WebSocket headers
    const authHeader = info.req.headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return false;
    }

    const token = authHeader.slice(7);
    try {
      jwt.verify(token, process.env.JWT_SECRET || 'default-secret');
      return true;
    } catch (err) {
      console.error('WebSocket authentication failed:', err.message);
      return false;
    }
  }
});

// Middleware setup
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      connectSrc: ["'self'", "ws:", "wss:"],
      scriptSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"]
    }
  }
}));

app.use(cors({
  origin: config.corsOrigin,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Requested-With']
}));

app.use(express.json({ limit: '10mb' }));
app.use(logger);

// OAuth 2.1 endpoints
app.post('/oauth/token', oauth2Middleware, (req, res) => {
  // OAuth 2.1 token endpoint with PKCE support
  res.json({
    access_token: 'sample_access_token',
    token_type: 'Bearer',
    expires_in: 3600,
    refresh_token: 'sample_refresh_token',
    scope: 'code-pipeline.read code-pipeline.write'
  });
});

app.post('/oauth/introspect', authenticateToken, (req, res) => {
  // Token introspection endpoint
  const { token } = req.body;

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'default-secret');
    res.json({
      active: true,
      scope: decoded.scope || 'code-pipeline.read',
      client_id: decoded.client_id || 'default-client',
      exp: decoded.exp,
      iat: decoded.iat
    });
  } catch (err) {
    res.json({ active: false });
  }
});

// Health check endpoints
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    transport: ['http', 'websocket'],
    authentication: 'oauth2.1',
    features: ['streaming', 'real-time', 'mcp'],
    websocket: {
      clients: wss.clients.size,
      path: '/ws'
    }
  });
});

// Server-Sent Events endpoint for streaming
app.get('/events/progress', authenticateToken, (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Cache-Control'
  });

  // Send initial connection event
  res.write(`data: ${JSON.stringify({
    type: 'connection',
    message: 'Connected to progress stream',
    timestamp: new Date().toISOString()
  })}\n\n`);

  // Simulate progress updates
  let progress = 0;
  const interval = setInterval(() => {
    progress += Math.random() * 10;
    if (progress >= 100) {
      progress = 100;
      res.write(`data: ${JSON.stringify({
        type: 'complete',
        progress: 100,
        message: 'Operation completed',
        timestamp: new Date().toISOString()
      })}\n\n`);
      clearInterval(interval);
      res.end();
    } else {
      res.write(`data: ${JSON.stringify({
        type: 'progress',
        progress: Math.round(progress),
        message: `Processing... ${Math.round(progress)}%`,
        timestamp: new Date().toISOString()
      })}\n\n`);
    }
  }, 1000);

  // Handle client disconnect
  req.on('close', () => {
    clearInterval(interval);
  });
});

// Streaming endpoint for large datasets
app.get('/stream/large-dataset', authenticateToken, async (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'application/json',
    'Transfer-Encoding': 'chunked',
    'X-Content-Type-Options': 'nosniff'
  });

  // Simulate streaming large dataset
  const totalItems = 1000;
  const chunkSize = 50;

  res.write('{"items":[');

  for (let i = 0; i < totalItems; i += chunkSize) {
    const chunk = [];
    for (let j = i; j < Math.min(i + chunkSize, totalItems); j++) {
      chunk.push({
        id: j,
        name: `Item ${j}`,
        timestamp: new Date().toISOString(),
        data: `Sample data for item ${j}`
      });
    }

    const chunkData = chunk.map(item => JSON.stringify(item)).join(',');
    res.write(i === 0 ? chunkData : ',' + chunkData);

    // Small delay to simulate processing time
    await new Promise(resolve => setTimeout(resolve, 100));
  }

  res.write(']}');
  res.end();
});

// WebSocket connection handling
const clientConnections = new Map();

wss.on('connection', (ws, req) => {
  const clientId = `client_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  clientConnections.set(clientId, ws);

  console.log(`WebSocket client connected: ${clientId}`);

  // Send welcome message
  ws.send(JSON.stringify({
    type: 'welcome',
    clientId: clientId,
    timestamp: new Date().toISOString(),
    features: ['mcp', 'streaming', 'real-time']
  }));

  // Handle messages
  ws.on('message', async (message) => {
    try {
      const data = JSON.parse(message);

      switch (data.type) {
        case 'ping':
          ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
          break;

        case 'mcp_request':
          // Handle MCP requests via WebSocket
          const response = await handleMCPRequest(data);
          ws.send(JSON.stringify({
            id: data.id,
            type: 'mcp_response',
            ...response,
            timestamp: new Date().toISOString()
          }));
          break;

        case 'stream_request':
          // Handle streaming data requests
          await handleStreamRequest(ws, data);
          break;

        default:
          ws.send(JSON.stringify({
            type: 'error',
            message: `Unknown message type: ${data.type}`,
            timestamp: new Date().toISOString()
          }));
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
      ws.send(JSON.stringify({
        type: 'error',
        message: 'Invalid message format',
        timestamp: new Date().toISOString()
      }));
    }
  });

  // Handle disconnection
  ws.on('close', () => {
    console.log(`WebSocket client disconnected: ${clientId}`);
    clientConnections.delete(clientId);
  });

  // Handle errors
  ws.on('error', (err) => {
    console.error(`WebSocket error for client ${clientId}:`, err);
    clientConnections.delete(clientId);
  });

  // Heartbeat mechanism
  const heartbeat = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.ping();
    } else {
      clearInterval(heartbeat);
    }
  }, 30000); // 30 second heartbeat
});

// MCP request handler for WebSocket
async function handleMCPRequest(data) {
  try {
    // This would integrate with the MCP tools
    return {
      result: `Processed MCP request: ${data.method}`,
      success: true
    };
  } catch (err) {
    return {
      error: err.message,
      success: false
    };
  }
}

// Stream request handler for WebSocket
async function handleStreamRequest(ws, data) {
  const streamId = data.streamId || `stream_${Date.now()}`;

  // Start streaming data
  for (let i = 0; i < 100; i++) {
    if (ws.readyState !== WebSocket.OPEN) break;

    ws.send(JSON.stringify({
      type: 'stream_data',
      streamId: streamId,
      sequence: i,
      data: {
        item: i,
        timestamp: new Date().toISOString(),
        content: `Streaming item ${i}`
      },
      isLast: i === 99
    }));

    await new Promise(resolve => setTimeout(resolve, 100));
  }
}

// Load OpenAPI and generate routes
(async () => {
  try {
    const openapiSpec = await loadOpenAPISpec();
    const tools = generateMCPToolsFromOpenAPI(openapiSpec);

    for (const [toolName, tool] of Object.entries(tools)) {
      const [method, route] = toolName.split(' ');

      app[method.toLowerCase()](route, oauth2Middleware, async (req, res) => {
        try {
          if (tool.validate && !tool.validate(req.body)) {
            return res.status(400).json({
              error: 'Invalid request',
              details: tool.validate.errors
            });
          }

          // Check if client requests streaming response
          const acceptsStream = req.headers.accept &&
            (req.headers.accept.includes('text/event-stream') ||
             req.headers.accept.includes('application/stream+json'));

          if (acceptsStream) {
            // Return streaming response
            const streaming = new StreamingResponse(res);
            await streaming.sendProgress(`Executing ${toolName}...`, 0);

            // Simulate work with progress updates
            for (let i = 10; i <= 100; i += 10) {
              await new Promise(resolve => setTimeout(resolve, 200));
              await streaming.sendProgress(`Processing... ${i}%`, i);
            }

            await streaming.sendComplete({
              message: `Executed ${toolName}`,
              timestamp: new Date().toISOString(),
              tool: toolName
            });
          } else {
            // Return regular response
            res.status(200).json({
              message: `Executed ${toolName}`,
              timestamp: new Date().toISOString(),
              tool: toolName
            });
          }
        } catch (err) {
          console.error(`Error executing ${toolName}:`, err);
          res.status(500).json({
            error: 'Server error',
            details: err.message,
            tool: toolName
          });
        }
      });
    }

    console.log(`Generated ${Object.keys(tools).length} MCP tools from OpenAPI spec`);
  } catch (err) {
    console.error('Failed to load OpenAPI spec:', err);
    process.exit(1);
  }
})();

const port = config.port || process.env.PORT || 8080;
server.listen(port, () => {
  console.log(`BMC AMI DevX Code Pipeline MCP Server running on port ${port}`);
  console.log(`HTTP endpoint: http://localhost:${port}`);
  console.log(`WebSocket endpoint: ws://localhost:${port}/ws`);
  console.log(`Health check: http://localhost:${port}/health`);
});
