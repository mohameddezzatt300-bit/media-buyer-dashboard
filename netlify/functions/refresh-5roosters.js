// Netlify Function — proxies workflow_dispatch to GitHub.
// The GitHub PAT lives in Netlify env var GITHUB_PAT, not in the public dashboard.

exports.handler = async (event) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: cors, body: '' };
  }
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: { ...cors, 'Content-Type': 'application/json' },
             body: JSON.stringify({ error: 'POST only' }) };
  }

  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    return { statusCode: 500, headers: { ...cors, 'Content-Type': 'application/json' },
             body: JSON.stringify({ error: 'server missing GITHUB_PAT' }) };
  }

  let body = {};
  try { body = JSON.parse(event.body || '{}'); } catch (e) {}
  const inputs = {
    date_preset: body.date_preset || 'last_30d',
    time_range_since: body.time_range_since || '',
    time_range_until: body.time_range_until || '',
  };

  const dispatch = await fetch(
    'https://api.github.com/repos/mohameddezzatt300-bit/media-buyer-dashboard/actions/workflows/refresh-5roosters.yml/dispatches',
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      body: JSON.stringify({ ref: 'main', inputs }),
    }
  );

  if (dispatch.status === 204) {
    return { statusCode: 200, headers: { ...cors, 'Content-Type': 'application/json' },
             body: JSON.stringify({ ok: true, inputs }) };
  }
  const errText = await dispatch.text();
  return { statusCode: 502, headers: { ...cors, 'Content-Type': 'application/json' },
           body: JSON.stringify({ error: `GitHub ${dispatch.status}: ${errText.slice(0, 300)}` }) };
};
