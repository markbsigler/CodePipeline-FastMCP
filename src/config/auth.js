const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.resolve(__dirname, '../../config/.env') });

module.exports = {
  port: process.env.PORT || 8080,
  nodeEnv: process.env.NODE_ENV || 'development',
  bearerTokenSecret: process.env.BEARER_TOKEN_SECRET,
  apiKeys: (process.env.API_KEYS || '').split(',').map(k => k.trim()).filter(Boolean),
  logLevel: process.env.LOG_LEVEL || 'info',
  corsOrigin: process.env.CORS_ORIGIN || '*',
};
