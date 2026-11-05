// Shared GitHub helper for /api/sync and /api/status. Needs Vercel env GH_TOKEN (fine-grained, Actions read/write on GH_REPO).
const REPO = process.env.GH_REPO || 'dubaiincairo/swissblue-rates-bot';
const WF = process.env.GH_WORKFLOW || 'rates.yml';
async function gh(path, opt = {}) {
  const r = await fetch('https://api.github.com/repos/' + REPO + path, { ...opt, headers: { Authorization: 'Bearer ' + process.env.GH_TOKEN, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'swissblue-rates', ...(opt.headers || {}) } });
  if (!r.ok && r.status !== 204) throw new Error('github ' + r.status);
  return r.status === 204 ? null : r.json();
}
async function latest() { const j = await gh('/actions/workflows/' + WF + '/runs?per_page=1'); return (j.workflow_runs || [])[0] || null; }
function state(run) {
  if (!run) return { state: 'idle' };
  if (run.status !== 'completed') return { state: 'running', started: run.run_started_at || run.created_at };
  return { state: run.conclusion === 'success' ? 'idle' : 'failed', finished: run.updated_at, started: run.run_started_at };
}
module.exports = { gh, latest, state, WF };
