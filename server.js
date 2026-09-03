// Local development server — Vercel uses api/index.js instead
const app = require('./app');

const PORT = process.env.PORT || 3001;

app.listen(PORT, '0.0.0.0', () => {
  console.log(`detasawy-backend listening on port ${PORT}`);
});
