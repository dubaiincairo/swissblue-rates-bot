const { latest, state } = require('./_gh');
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (!process.env.GH_TOKEN) return res.status(200).json({ state: 'not_configured' });
  try { res.status(200).json(state(await latest())); } catch (e) { res.status(200).json({ state: 'unknown' }); }
};
