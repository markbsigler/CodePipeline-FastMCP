const { OpenAPI } = require('openapi-types');
const Ajv = require('ajv');
const ajv = new Ajv({ allErrors: true });

function generateMCPToolsFromOpenAPI(openapiSpec) {
  const tools = {};
  for (const [path, methods] of Object.entries(openapiSpec.paths)) {
    for (const [method, operation] of Object.entries(methods)) {
      const toolName = `${method.toUpperCase()} ${path}`;
      tools[toolName] = {
        validate: ajv.compile(operation.requestBody?.content?.['application/json']?.schema || {}),
        responseSchema: operation.responses?.['200']?.content?.['application/json']?.schema || {},
        operation,
        method,
        path,
      };
    }
  }
  return tools;
}

module.exports = { generateMCPToolsFromOpenAPI };
