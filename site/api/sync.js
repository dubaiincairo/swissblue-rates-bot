const { gh, latest, state, WF } = require('./_gh');
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  if (!process.env.GH_TOKEN) return res.status(200).json({ state: 'not_configured' });
  try {
    const run = await latest(); const s = state(run);
    if (s.state === 'running') return res.status(200).json(s);
    const mins = run ? Math.round((Date.now() - new Date(run.updated_at).getTime()) / 60000) : 999;
    if (mins < 20) return res.status(200).json({ state: 'recent', minutes: mins });
    await gh('/actions/workflows/' + WF + '/dispatches', { method: 'POST', body: JSON.stringify({ ref: 'main' }), headers: { 'Content-Type': 'application/json' } });
    res.status(200).json({ state: 'started', started: new Date().toISOString() });
  } catch (e) { res.status(200).json({ state: 'error' }); }
};
