const fs = require('fs');
const path = require('path');
const swaggerParser = require('swagger-parser');

const openapiPath = path.resolve(__dirname, '../../config/openapi.json');

async function loadOpenAPISpec() {
  if (!fs.existsSync(openapiPath)) {
    throw new Error('OpenAPI spec not found at ' + openapiPath);
  }
  return swaggerParser.dereference(openapiPath);
}

module.exports = { loadOpenAPISpec };
