const jwt = require('jsonwebtoken');
const config = require('../config/auth');

function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'Missing Bearer token' });
  }
  jwt.verify(token, config.bearerTokenSecret, (err, user) => {
    if (err) {
      return res.status(401).json({ error: 'Invalid or expired token' });
    }
    req.user = user;
    next();
  });
}

function apiKeyMiddleware(req, res, next) {
  const apiKey = req.headers['x-api-key'];
  if (config.apiKeys.length && !config.apiKeys.includes(apiKey)) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  next();
}

module.exports = { authenticateToken, apiKeyMiddleware };
