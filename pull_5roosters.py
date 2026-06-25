#!/usr/bin/env python3
"""Pull Meta Ads data for 5 Roosters and emit JSON for the dashboard."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).parent / "5roosters_meta.env"
OUT_FILE = Path(__file__).parent / "5roosters_data.json"
API_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{API_VERSION}"

DATE_PRESET = os.environ.get("DATE_PRESET", "last_30d")
TIME_RANGE_SINCE = os.environ.get("TIME_RANGE_SINCE", "").strip()
TIME_RANGE_UNTIL = os.environ.get("TIME_RANGE_UNTIL", "").strip()


def date_params():
    """Return Meta API date params — custom range overrides preset."""
    if TIME_RANGE_SINCE and TIME_RANGE_UNTIL:
        return {"time_range": json.dumps({"since": TIME_RANGE_SINCE, "until": TIME_RANGE_UNTIL})}
    return {"date_preset": DATE_PRESET}


def load_env():
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def fetch(path, params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} on {path}: {body[:500]}") from None
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def post(path, params):
    url = f"{BASE}/{path}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} on POST {path}: {body[:500]}") from None


def async_submit(acct, params, token, label="async"):
    """Submit an async insights job, return its run_id."""
    params = {**params, "access_token": token}
    print(f"   submitting {label} async job…")
    r = post(f"{acct}/insights", params)
    run_id = r.get("report_run_id")
    if not run_id:
        raise RuntimeError(f"no report_run_id in {r}")
    return run_id


def async_fetch(run_id, token, label="async"):
    """Poll an async job until complete and return all rows."""
    for i in range(180):  # up to ~9 min at 3s
        time.sleep(3)
        status = fetch(run_id, {"access_token": token})
        st = status.get("async_status")
        pct = status.get("async_percent_completion", 0)
        print(f"   [{label}] {st} {pct}%")
        if st == "Job Completed":
            break
        if st in ("Job Failed", "Job Skipped"):
            raise RuntimeError(f"{label} {st}")
    else:
        raise RuntimeError(f"{label} polling timed out")
    out = []
    params_get = {"access_token": token, "limit": 500}
    path = f"{run_id}/insights"
    while True:
        d = fetch(path, params_get)
        out.extend(d.get("data", []))
        nxt = d.get("paging", {}).get("next")
        if not nxt:
            return out
        from urllib.parse import urlparse, parse_qsl
        u = urlparse(nxt)
        path = u.path.lstrip("/").split("/", 1)[1]
        params_get = dict(parse_qsl(u.query))


def async_insights(acct, params, token, label="async"):
    """One-shot wrapper: submit + fetch."""
    run_id = async_submit(acct, params, token, label)
    return async_fetch(run_id, token, label)


def paged(path, params):
    out = []
    while True:
        d = fetch(path, params)
        out.extend(d.get("data", []))
        nxt = d.get("paging", {}).get("next")
        if not nxt:
            return out
        # parse next URL into path + params
        from urllib.parse import urlparse, parse_qsl
        u = urlparse(nxt)
        path = u.path.lstrip("/").split("/", 1)[1]
        params = dict(parse_qsl(u.query))


def action_value(actions, key, field="value"):
    if not actions:
        return 0
    for a in actions:
        if a.get("action_type") == key:
            try:
                return float(a.get(field, 0))
            except (TypeError, ValueError):
                return 0
    return 0


def normalize_insight(row):
    """Flatten an insights row into a flat dict for the dashboard."""
    actions = row.get("actions", []) or []
    values = row.get("action_values", []) or []
    return {
        "spend": float(row.get("spend", 0) or 0),
        "impressions": int(row.get("impressions", 0) or 0),
        "clicks": int(row.get("clicks", 0) or 0),
        "ctr": float(row.get("ctr", 0) or 0),
        "cpm": float(row.get("cpm", 0) or 0),
        "cpc": float(row.get("cpc", 0) or 0),
        "reach": int(row.get("reach", 0) or 0),
        "frequency": float(row.get("frequency", 0) or 0),
        "purchases": int(action_value(actions, "omni_purchase") or action_value(actions, "purchase") or 0),
        "revenue": action_value(values, "omni_purchase") or action_value(values, "purchase") or 0,
        "leads": int(action_value(actions, "lead") or 0),
        "messages_started": int(action_value(actions, "onsite_conversion.messaging_conversation_started_7d") or 0),
        "messages_replied": int(action_value(actions, "onsite_conversion.messaging_conversation_replied_7d") or 0),
        "post_engagement": int(action_value(actions, "post_engagement") or 0),
        "video_views": int(action_value(actions, "video_view") or 0),
        "add_to_cart": int(action_value(actions, "add_to_cart") or 0),
        "view_content": int(action_value(actions, "view_content") or 0),
        "landing_page_view": int(action_value(actions, "landing_page_view") or 0),
        "link_clicks": int(action_value(actions, "link_click") or 0),
        "date_start": row.get("date_start"),
        "date_stop": row.get("date_stop"),
    }


def main():
    env = load_env()
    token = env["META_ACCESS_TOKEN"]
    acct = env["META_AD_ACCOUNT_ID"]
    dp = date_params()
    range_label = f"since={TIME_RANGE_SINCE}, until={TIME_RANGE_UNTIL}" if "time_range" in dp else f"preset={DATE_PRESET}"
    print(f"→ Pulling {acct} for {range_label}")

    common_insight_fields = (
        "spend,impressions,clicks,ctr,cpm,cpc,reach,frequency,"
        "actions,action_values,purchase_roas"
    )

    # 1. Account summary
    print("1/5 account summary…")
    acct_info = fetch(acct, {
        "fields": "name,currency,timezone_name,amount_spent,balance",
        "access_token": token,
    })
    acct_ins = fetch(f"{acct}/insights", {
        "fields": common_insight_fields,
        **dp,
        "access_token": token,
    })
    summary = normalize_insight(acct_ins["data"][0]) if acct_ins.get("data") else {}

    # 2+3. Submit both async jobs upfront, then fetch results in parallel
    print("2-3/5 submitting parallel async jobs (campaigns + ads)…")
    camp_run_id = async_submit(acct, {
        "fields": common_insight_fields + ",campaign_id,campaign_name,objective",
        "level": "campaign",
        **dp,
        "filtering": json.dumps([{"field": "spend", "operator": "GREATER_THAN", "value": 0}]),
    }, token, label="campaigns")
    ad_run_id = async_submit(acct, {
        "fields": common_insight_fields + ",campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name",
        "level": "ad",
        **dp,
        "filtering": json.dumps([{"field": "spend", "operator": "GREATER_THAN", "value": 0}]),
    }, token, label="ads")

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_camp = ex.submit(async_fetch, camp_run_id, token, "campaigns")
        f_ad   = ex.submit(async_fetch, ad_run_id, token, "ads")
        camp_ins = f_camp.result()
        ad_ins   = f_ad.result()

    print(f"   {len(camp_ins)} campaigns spent > 0")
    campaigns = []
    for r in camp_ins:
        campaigns.append({
            "id": r.get("campaign_id"),
            "name": r.get("campaign_name"),
            "objective": r.get("objective"),
            "insights": normalize_insight(r),
        })
    print(f"   {len(ad_ins)} ad rows")
    ads = []
    for r in ad_ins:
        ads.append({
            "id": r.get("ad_id"),
            "name": r.get("ad_name"),
            "campaign_id": r.get("campaign_id"),
            "campaign_name": r.get("campaign_name"),
            "adset_name": r.get("adset_name"),
            **normalize_insight(r),
        })

    # 4. Daily breakdown (account level)
    print("4/5 daily breakdown…")
    daily = paged(f"{acct}/insights", {
        "fields": common_insight_fields,
        "time_increment": 1,
        **dp,
        "limit": 200,
        "access_token": token,
    })
    daily_norm = [normalize_insight(r) for r in daily]
    print(f"   {len(daily_norm)} days")

    # 5. Save
    out = {
        "account": acct_info,
        "date_range": {
            "start": summary.get("date_start"),
            "stop": summary.get("date_stop"),
            "preset": DATE_PRESET if "time_range" not in dp else "custom",
            "since": TIME_RANGE_SINCE,
            "until": TIME_RANGE_UNTIL,
        },
        "summary": summary,
        "campaigns": campaigns,
        "ads": ads,
        "daily": daily_norm,
    }
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"✓ wrote {OUT_FILE}")
    print(f"  spend={summary.get('spend'):,.0f} EGP  purchases={summary.get('purchases')}  revenue={summary.get('revenue'):,.0f} EGP")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
