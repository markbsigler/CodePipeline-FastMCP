const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const config = require('./config/auth');
const { loadOpenAPISpec } = require('./config/openapi');
const { authenticateToken, apiKeyMiddleware } = require('./middleware/auth');
const logger = require('./middleware/logging');
const { generateMCPToolsFromOpenAPI } = require('./utils/openapi-parser');

const app = express();
app.use(helmet());
app.use(cors({ origin: config.corsOrigin }));
app.use(express.json());
app.use(logger);

// Health check endpoint
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Load OpenAPI and generate routes
(async () => {
  try {
    const openapiSpec = await loadOpenAPISpec();
    const tools = generateMCPToolsFromOpenAPI(openapiSpec);
    for (const [toolName, tool] of Object.entries(tools)) {
      const [method, route] = toolName.split(' ');
      app[method.toLowerCase()](route, authenticateToken, apiKeyMiddleware, async (req, res) => {
        try {
          if (tool.validate && !tool.validate(req.body)) {
            return res.status(400).json({ error: 'Invalid request', details: tool.validate.errors });
          }
          // Simulate tool execution (replace with actual logic)
          res.status(200).json({ message: `Executed ${toolName}` });
        } catch (err) {
          res.status(500).json({ error: 'Server error', details: err.message });
        }
      });
    }
  } catch (err) {
    console.error('Failed to load OpenAPI spec:', err);
    process.exit(1);
  }
})();

const port = config.port;
app.listen(port, () => {
  console.log(`FastMCP server running on port ${port}`);
});
