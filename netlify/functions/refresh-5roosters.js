// Proxies a workflow_dispatch call to GitHub so we don't have to embed a PAT
// in the public dashboard. The PAT is stored as a Netlify env var (GITHUB_PAT).

export default async (req) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST only' }), {
      status: 405, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    return new Response(JSON.stringify({ error: 'server missing GITHUB_PAT env var' }), {
      status: 500, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  let body;
  try { body = await req.json(); } catch { body = {}; }
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
    return new Response(JSON.stringify({ ok: true, inputs }), {
      status: 200, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }
  const errText = await dispatch.text();
  return new Response(JSON.stringify({ error: `GitHub ${dispatch.status}: ${errText.slice(0, 300)}` }), {
    status: 502, headers: { ...cors, 'Content-Type': 'application/json' },
  });
};

export const config = { path: '/api/refresh-5roosters' };
