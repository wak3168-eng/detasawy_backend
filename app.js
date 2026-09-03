const express = require('express');

const app = express();

// Runs behind Vercel's edge / a forwarding proxy
app.set('trust proxy', true);
app.disable('x-powered-by');

app.get('/', (req, res) => {
  res.json({ service: 'detasawy-backend', status: 'under construction' });
});

app.get('/health', (req, res) => {
  res.json({ service: 'detasawy-backend', status: 'ok', uptime: process.uptime() });
});

app.use((req, res) => {
  res.status(404).json({ error: 'Not found' });
});

module.exports = app;
