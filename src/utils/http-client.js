const axios = require('axios');

async function httpRequest({ method, url, headers, data }) {
  try {
    const response = await axios({ method, url, headers, data });
    return response.data;
  } catch (error) {
    throw error.response ? error.response.data : error;
  }
}

module.exports = { httpRequest };
