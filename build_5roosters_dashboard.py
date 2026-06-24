#!/usr/bin/env python3
"""Build the 5 Roosters performance dashboard from pulled Meta data."""
import html
import json
from datetime import datetime
from pathlib import Path

DATA = Path(__file__).parent / "5roosters_data.json"
OUT = Path(__file__).parent / "5roosters_media_dashboard.html"


def fmt_num(n, decimals=0):
    if n is None: return "—"
    try: n = float(n)
    except: return "—"
    if abs(n) >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if abs(n) >= 10_000:    return f"{n/1000:.0f}K"
    if abs(n) >= 1000:      return f"{n:,.{decimals}f}"
    if decimals == 0:       return f"{int(round(n)):,}"
    return f"{n:,.{decimals}f}"


def fmt_full(n, decimals=0):
    if n is None: return "—"
    try: return f"{float(n):,.{decimals}f}"
    except: return "—"


def safe_div(a, b):
    try: return a/b if b else 0
    except: return 0


def categorize(c):
    """Bucket by objective + name."""
    obj = (c.get("objective") or "").upper()
    name = (c.get("name") or "").lower()
    if obj == "OUTCOME_SALES":
        return "sales"
    if obj == "LINK_CLICKS":
        return "traffic"
    # OUTCOME_ENGAGEMENT — split by name signal
    if name.startswith("msg") or "what" in name or "msg-" in name or "msg_" in name:
        return "messages"
    if "pagelike" in name or "page like" in name:
        return "pagelike"
    return "engagement"


def kpis(rows, key):
    return sum(r.get(key, 0) or 0 for r in rows)


def section_kpis(camps):
    spend = kpis([c["insights"] for c in camps], "spend")
    impr  = kpis([c["insights"] for c in camps], "impressions")
    clicks= kpis([c["insights"] for c in camps], "clicks")
    pur   = kpis([c["insights"] for c in camps], "purchases")
    rev   = kpis([c["insights"] for c in camps], "revenue")
    msgs  = kpis([c["insights"] for c in camps], "messages_started")
    atc   = kpis([c["insights"] for c in camps], "add_to_cart")
    reach = kpis([c["insights"] for c in camps], "reach")
    eng   = kpis([c["insights"] for c in camps], "post_engagement")
    return {
        "spend": spend, "impressions": impr, "clicks": clicks,
        "purchases": pur, "revenue": rev, "messages": msgs,
        "add_to_cart": atc, "reach": reach, "post_engagement": eng,
        "ctr": safe_div(clicks*100, impr),
        "cpm": safe_div(spend*1000, impr),
        "cpc": safe_div(spend, clicks),
        "cpp": safe_div(spend, pur) if pur else 0,
        "roas": safe_div(rev, spend),
        "cpm_msg": safe_div(spend, msgs) if msgs else 0,
    }


def row_camp(c, show_msg=True):
    i = c["insights"]
    cpp_cls = ""
    if i.get("purchases"):
        cpp = safe_div(i["spend"], i["purchases"])
        cpp_cls = "good" if cpp < 200 else ("bad" if cpp > 400 else "")
    roas_cls = ""
    if i.get("revenue") and i.get("spend"):
        roas = safe_div(i["revenue"], i["spend"])
        roas_cls = "good" if roas > 3 else ("bad" if roas < 1.5 else "")
    return f"""<tr>
<td class="name-col">{html.escape(c.get('name','')[:60])}</td>
<td>{fmt_full(i.get('spend',0))}</td>
<td>{i.get('ctr',0):.1f}%</td>
<td>{i.get('cpm',0):.0f}</td>
<td>{i.get('frequency',0):.2f}</td>
<td>{fmt_num(i.get('purchases',0))}</td>
<td>{fmt_num(i.get('add_to_cart',0))}</td>
{"<td>"+fmt_num(i.get('messages_started',0))+"</td>" if show_msg else ""}
<td class="{cpp_cls}">{fmt_full(safe_div(i.get('spend',0), i.get('purchases',0))) if i.get('purchases') else '—'}</td>
<td class="{roas_cls}">{(safe_div(i.get('revenue',0), i.get('spend',0))):.2f}x</td>
</tr>"""


def row_ad(a):
    cpp = safe_div(a.get("spend",0), a.get("purchases",0)) if a.get("purchases") else 0
    roas= safe_div(a.get("revenue",0), a.get("spend",0))
    cpp_cls = "good" if cpp and cpp < 200 else ("bad" if cpp > 400 else "")
    roas_cls = "good" if roas > 3 else ("bad" if roas < 1.5 and roas > 0 else "")
    return f"""<tr>
<td class="name-col">{html.escape((a.get('name') or '')[:50])}</td>
<td class="xs">{html.escape((a.get('campaign_name') or '')[:40])}</td>
<td>{fmt_full(a.get('spend',0))}</td>
<td class="{ 'good' if (a.get('purchases') or 0) > 5 else ''}">{fmt_num(a.get('purchases',0))}</td>
<td class="{roas_cls}">{roas:.2f}x</td>
<td class="{cpp_cls}">{fmt_full(cpp) if cpp else '—'}</td>
<td>{fmt_num(a.get('messages_started',0))}</td>
<td>{fmt_num(a.get('add_to_cart',0))}</td>
<td>{fmt_num(a.get('video_views',0))}</td>
</tr>"""


def main():
    d = json.loads(DATA.read_text())
    acct = d["account"]
    dr = d["date_range"]
    s = d["summary"]
    camps = d["campaigns"]
    ads = d["ads"]
    daily = sorted(d["daily"], key=lambda r: r.get("date_start") or "")

    # Bucket campaigns
    buckets = {"sales": [], "engagement": [], "messages": [], "pagelike": [], "traffic": []}
    for c in camps:
        buckets[categorize(c)].append(c)

    # Roll up "engagement" + "pagelike" into a single engagement section, keep messages separate
    sales_camps = sorted(buckets["sales"], key=lambda c: -c["insights"].get("spend",0))
    msg_camps   = sorted(buckets["messages"], key=lambda c: -c["insights"].get("spend",0))
    eng_camps   = sorted(buckets["engagement"] + buckets["pagelike"] + buckets["traffic"],
                         key=lambda c: -c["insights"].get("spend",0))

    sales_k = section_kpis(sales_camps)
    msg_k   = section_kpis(msg_camps)
    eng_k   = section_kpis(eng_camps)

    total_spend = s.get("spend", 0)

    # Group ads by bucket (use ad's campaign_id → bucket)
    camp_bucket = {c["id"]: categorize(c) for c in camps}
    ads_by_bucket = {"sales": [], "engagement": [], "messages": []}
    for a in ads:
        b = camp_bucket.get(a.get("campaign_id"), "engagement")
        if b in ("pagelike", "traffic"): b = "engagement"
        ads_by_bucket[b].append(a)
    for k in ads_by_bucket: ads_by_bucket[k].sort(key=lambda r: -r.get("purchases",0) or -r.get("spend",0))

    # Daily charts data
    labels = [r.get("date_start","")[5:] for r in daily]  # MM-DD
    spends = [round(r.get("spend",0), 1) for r in daily]
    ctrs   = [round(r.get("ctr",0), 2) for r in daily]
    purs   = [r.get("purchases",0) for r in daily]

    # Funnel
    impressions = s.get("impressions", 0)
    clicks      = s.get("clicks", 0)
    vc          = s.get("view_content", 0)
    atc         = s.get("add_to_cart", 0)
    pur         = s.get("purchases", 0)
    msgs        = s.get("messages_started", 0)
    rev         = s.get("revenue", 0)

    # Insight generation
    insights_overview = []
    roas = safe_div(rev, total_spend)
    if roas >= 3:
        insights_overview.append(("good", "✅ ROAS قوية", f"ROAS {roas:.2f}x ممتازة لمطعم QSR. كل ١ EGP بيرجع {roas:.1f} EGP — استمر في الكامبينز الناجحة وزود البودجت تدريجياً."))
    elif roas >= 1.5:
        insights_overview.append(("warn", "⚠️ ROAS متوسطة", f"ROAS {roas:.2f}x — مقبولة بس عندنا فرصة نطلعها. ركّز على الكامبينز اللي ROAS أعلى من 4x وقلل اللي تحت 1.5x."))
    else:
        insights_overview.append(("bad", "🔴 ROAS منخفضة", f"ROAS {roas:.2f}x — أقل من الـ break-even للـ delivery commission. لازم وقفة سريعة للكامبينز اللي بتخسر."))
    cpp = safe_div(total_spend, pur) if pur else 0
    if cpp and cpp < 200:
        insights_overview.append(("good", "✅ CPO صحي", f"تكلفة الطلب {cpp:.0f} EGP — قوية. متوسط الطلب ~{safe_div(rev,pur):.0f} EGP، فيه هامش."))
    elif cpp:
        insights_overview.append(("warn", "⚠️ CPO عالي", f"تكلفة الطلب {cpp:.0f} EGP — راجع متوسط الطلب والديليفري."))
    freq = s.get("frequency", 0)
    if freq > 3:
        insights_overview.append(("warn", "⚠️ Frequency عالية", f"التكرار {freq:.2f}x — الجمهور بيشوف الإعلان كذا مرة. خاطر إعلاني fatigue. جدد الـ creatives أو وسّع الـ audience."))
    if msgs > 1000:
        insights_overview.append(("good", "💬 محادثات WhatsApp قوية", f"{msgs:,} محادثة بدأت في الفترة. لو فريق الـ sales بيقفل ١٠٪ ده {int(msgs*0.1):,} طلب إضافي."))
    if atc and pur:
        atc_to_pur = safe_div(pur*100, atc)
        if atc_to_pur < 25:
            insights_overview.append(("bad", "🔴 ATC → Order ضعيفة", f"معدل التحويل من Add-to-Cart إلى Order {atc_to_pur:.1f}٪ — Benchmark ٣٠–٥٠٪. راجع تجربة الـ checkout والـ delivery options."))

    # Winners and losers for sales section
    winners = [c for c in sales_camps if (c['insights'].get('purchases',0) >= 10 and safe_div(c['insights'].get('revenue',0), c['insights'].get('spend',0)) >= 3)]
    losers  = [c for c in sales_camps if c['insights'].get('spend',0) > 1000 and safe_div(c['insights'].get('revenue',0), c['insights'].get('spend',0)) < 1.5]
    msg_winners = sorted(msg_camps, key=lambda c: -c['insights'].get('messages_started',0))[:5]

    # HTML
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>5 Roosters – Performance Report ({dr['start']} → {dr['stop']})</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{
  --bg:#14110b;--card:#1f1b12;--card2:#2a2418;
  --accent:#F5B82E;--accent2:#E63946;--accent3:#ffffff;
  --green:#22c55e;--red:#ef4444;--yellow:#F5B82E;
  --sw:#F5B82E;--pe:#E63946;--sm:#ffffff;
  --text:#f5ecd5;--muted:#a89878;--border:#3a3220;
  --font:'Segoe UI',Tahoma,Arial,sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px}}
nav{{position:sticky;top:0;z-index:99;background:#0f0d08;border-bottom:1px solid var(--border);
     padding:9px 22px;display:flex;align-items:center;gap:12px;overflow-x:auto;white-space:nowrap}}
nav a{{color:var(--muted);text-decoration:none;font-size:12px;padding:4px 8px;border-radius:6px;transition:.2s}}
nav a:hover{{color:var(--text);background:var(--card2)}}
nav a.sw{{color:var(--sw)}} nav a.pe{{color:var(--pe)}} nav a.sm{{color:var(--sm)}}
.logo{{font-weight:800;font-size:15px;color:var(--accent);margin-left:auto;display:flex;align-items:center;gap:8px}}
.logo .rooster{{color:var(--accent2);font-size:18px}}
.page{{max-width:1400px;margin:0 auto;padding:24px 16px}}
section{{margin-bottom:52px}}
h2{{font-size:21px;font-weight:700;margin-bottom:18px;padding-bottom:10px;border-bottom:2px solid var(--accent)}}
h3{{font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent2)}}
h2.sw{{border-bottom-color:var(--sw)}} h2.pe{{border-bottom-color:var(--pe)}} h2.sm{{border-bottom-color:var(--sm)}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:13px}}
.kpi{{background:var(--card);border:1px solid var(--border);border-radius:13px;padding:16px 12px;text-align:center;transition:.2s}}
.kpi:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.kpi .label{{font-size:11px;color:var(--muted);margin-bottom:5px}}
.kpi .value{{font-size:22px;font-weight:800}}
.kpi .sub{{font-size:10px;color:var(--muted);margin-top:3px}}
.kpi.g .value{{color:var(--green)}} .kpi.r .value{{color:var(--red)}}
.kpi.y .value{{color:var(--yellow)}} .kpi.b .value{{color:var(--accent)}}
.kpi.c .value{{color:var(--accent2)}}
.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:768px){{.charts-row{{grid-template-columns:1fr}}}}
.chart-wrap{{background:var(--card);border:1px solid var(--border);border-radius:13px;padding:16px}}
.funnel-wrap{{display:flex;gap:12px;flex-wrap:wrap;align-items:center}}
.funnel-step{{flex:1;min-width:130px;background:var(--card);border:1px solid var(--border);border-radius:13px;padding:16px;text-align:center}}
.funnel-step .f-num{{font-size:22px;font-weight:800;color:var(--accent)}}
.funnel-step .f-label{{font-size:11px;color:var(--muted);margin-top:4px}}
.funnel-arrow{{display:flex;flex-direction:column;align-items:center;font-size:20px;color:var(--muted)}}
.funnel-arrow .f-rate{{font-size:11px;font-weight:700;margin-top:2px}}
.fbadge{{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:700;margin-top:6px}}
.tbl-wrap{{overflow-x:auto;border-radius:11px;border:1px solid var(--border);margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;background:var(--card)}}
thead tr{{background:var(--card2)}}
th{{padding:10px 9px;font-size:11px;color:var(--muted);text-align:left;font-weight:600;white-space:nowrap}}
td{{padding:9px 9px;border-bottom:1px solid var(--border);font-size:12px;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:rgba(245,184,46,.07)}}
.name-col{{max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.xs{{font-size:10px;color:var(--muted)}}
td.good{{color:var(--green);font-weight:700}} td.bad{{color:var(--red);font-weight:700}}
.insight-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:13px}}
.insight{{background:var(--card);border:1px solid var(--border);border-radius:11px;padding:16px;border-left:4px solid var(--accent)}}
.insight.warn{{border-left-color:var(--yellow)}} .insight.bad{{border-left-color:var(--red)}}
.insight.good{{border-left-color:var(--green)}}
.insight h4{{font-size:13px;font-weight:700;margin-bottom:7px}}
.insight p{{font-size:12px;color:var(--muted);line-height:1.65}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media(max-width:640px){{.two-col{{grid-template-columns:1fr}}}}
.obj-section{{border-radius:16px;padding:24px;margin-bottom:8px}}
.obj-section.sw{{background:rgba(245,184,46,.06);border:1px solid rgba(245,184,46,.25)}}
.obj-section.pe{{background:rgba(230,57,70,.06);border:1px solid rgba(230,57,70,.25)}}
.obj-section.sm{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.15)}}
.obj-kpi-row{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;margin-bottom:18px}}
.obj-kpi{{border-radius:11px;padding:14px;text-align:center}}
.obj-kpi.sw{{background:rgba(245,184,46,.12);border:1px solid rgba(245,184,46,.3)}}
.obj-kpi.pe{{background:rgba(230,57,70,.12);border:1px solid rgba(230,57,70,.3)}}
.obj-kpi.sm{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.2)}}
.obj-kpi .label{{font-size:10px;color:var(--muted);margin-bottom:4px}}
.obj-kpi .value{{font-size:20px;font-weight:800}}
.obj-kpi.sw .value{{color:var(--sw)}} .obj-kpi.pe .value{{color:var(--pe)}} .obj-kpi.sm .value{{color:var(--sm)}}
.obj-kpi .sub{{font-size:10px;color:var(--muted);margin-top:3px}}
.banner{{background:linear-gradient(135deg,#3d2f08,#2a0d0f);border:1px solid var(--accent);
         border-radius:15px;padding:26px 30px;margin-bottom:30px;display:flex;align-items:center;gap:24px}}
.banner-logo{{flex-shrink:0;width:90px;height:90px;background:var(--accent);border-radius:50%;
              display:flex;align-items:center;justify-content:center;font-weight:900;
              font-size:42px;color:#000;position:relative;border:3px solid #000}}
.banner-text{{flex:1}}
.banner h1{{font-size:24px;font-weight:800;color:var(--accent);margin-bottom:6px}}
.banner .sub-brand{{color:var(--accent2);font-size:13px;font-weight:700;letter-spacing:1px;margin-bottom:8px}}
.banner p{{color:var(--muted);font-size:13px;line-height:1.9}}
.sec-badge{{display:inline-block;font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;margin-bottom:10px;color:#000}}
.sec-badge.def{{background:var(--accent)}} .sec-badge.sw{{background:var(--sw)}}
.sec-badge.pe{{background:var(--pe);color:#fff}} .sec-badge.sm{{background:var(--sm);color:#000}}
.badge-pill{{padding:7px 13px;border-radius:7px;font-size:12px;margin-bottom:7px;display:block}}
.badge-pill.good{{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);color:var(--green)}}
.badge-pill.bad{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);color:var(--red)}}
.obj-legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}}
.obj-pill{{padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700}}
.obj-pill.sw{{background:rgba(245,184,46,.2);color:var(--sw);border:1px solid rgba(245,184,46,.4)}}
.obj-pill.pe{{background:rgba(230,57,70,.2);color:var(--pe);border:1px solid rgba(230,57,70,.4)}}
.obj-pill.sm{{background:rgba(255,255,255,.08);color:var(--sm);border:1px solid rgba(255,255,255,.25)}}
</style>
</head>
<body>
<nav>
  <a href="#overview">📊 Overview</a>
  <a href="#daily">📅 Daily</a>
  <a href="#funnel">🔻 Funnel</a>
  <a href="#all-camps">📁 All Campaigns</a>
  <a href="#sw" class="sw">🛒 Sales / Orders</a>
  <a href="#pe" class="pe">💬 Messages / WhatsApp</a>
  <a href="#sm" class="sm">👍 Engagement</a>
  <a href="#problems">⚠️ Problems</a>
  <a href="#insights">💡 Insights</a>
  <span class="logo"><span class="rooster">🐓</span> 5 Roosters · {dr['start']} → {dr['stop']}</span>
</nav>

<div class="page">
<div class="banner">
  <div class="banner-logo">5</div>
  <div class="banner-text">
    <div class="sub-brand">FRIED CHICKEN</div>
    <h1>📋 5 Roosters – Performance Report</h1>
    <p>
      Period: <strong style="color:#fff">{dr['start']} → {dr['stop']}</strong> &nbsp;|&nbsp;
      Spend: <strong style="color:#fff">{fmt_full(total_spend)} EGP</strong> &nbsp;|&nbsp;
      Orders: <strong style="color:#22c55e">{pur:,}</strong> &nbsp;|&nbsp;
      Revenue: <strong style="color:#fff">{fmt_full(rev)} EGP</strong> &nbsp;|&nbsp;
      ROAS: <strong style="color:#22c55e">{roas:.2f}x</strong> &nbsp;|&nbsp;
      CPO: <strong style="color:#F5B82E">{(safe_div(total_spend,pur)):.0f} EGP</strong> &nbsp;|&nbsp;
      CTR: <strong style="color:#22c55e">{s.get('ctr',0):.2f}%</strong>
      <br><br>
      {len(camps)} active campaigns &nbsp;·&nbsp;
      <span style="color:var(--sw)">Sales</span> drives {sales_k['purchases']:,} orders ({sales_k['spend']/total_spend*100:.0f}% of spend) &nbsp;·&nbsp;
      <span style="color:var(--pe)">Messages</span> generates {msg_k['messages']:,} conversations &nbsp;·&nbsp;
      <span style="color:var(--sm)">Engagement</span> {eng_k['post_engagement']:,} interactions
    </p>
  </div>
</div>

<section id="overview">
  <span class="sec-badge def">Section 1</span>
  <h2>📊 Account Overview</h2>
  <div class="kpi-grid">
    <div class="kpi b"><div class="label">Total Spend</div><div class="value">{fmt_full(total_spend)}</div><div class="sub">EGP</div></div>
    <div class="kpi g"><div class="label">Orders</div><div class="value">{pur:,}</div><div class="sub">purchases</div></div>
    <div class="kpi g"><div class="label">Revenue</div><div class="value">{fmt_num(rev)}</div><div class="sub">EGP</div></div>
    <div class="kpi g"><div class="label">ROAS</div><div class="value">{roas:.2f}x</div><div class="sub">return on spend</div></div>
    <div class="kpi g"><div class="label">CPO</div><div class="value">{(safe_div(total_spend,pur)):.0f}</div><div class="sub">EGP / order</div></div>
    <div class="kpi g"><div class="label">CTR</div><div class="value">{s.get('ctr',0):.2f}%</div><div class="sub">click rate</div></div>
    <div class="kpi"><div class="label">CPM</div><div class="value">{s.get('cpm',0):.1f}</div><div class="sub">EGP / 1K imp</div></div>
    <div class="kpi"><div class="label">CPC</div><div class="value">{s.get('cpc',0):.2f}</div><div class="sub">EGP / click</div></div>
    <div class="kpi"><div class="label">Reach</div><div class="value">{fmt_num(s.get('reach',0))}</div><div class="sub">unique people</div></div>
    <div class="kpi y"><div class="label">Frequency</div><div class="value">{s.get('frequency',0):.2f}x</div><div class="sub">avg per person</div></div>
    <div class="kpi c"><div class="label">Add to Cart</div><div class="value">{fmt_num(atc)}</div><div class="sub">events</div></div>
    <div class="kpi c"><div class="label">View Content</div><div class="value">{fmt_num(vc)}</div><div class="sub">product views</div></div>
    <div class="kpi"><div class="label">WhatsApp Msgs</div><div class="value">{fmt_num(msgs)}</div><div class="sub">conversations</div></div>
    <div class="kpi"><div class="label">Leads</div><div class="value">{fmt_num(s.get('leads',0))}</div><div class="sub">form fills</div></div>
    <div class="kpi"><div class="label">Page Engagement</div><div class="value">{fmt_num(s.get('post_engagement',0))}</div><div class="sub">reactions+comments</div></div>
    <div class="kpi"><div class="label">Video Views</div><div class="value">{fmt_num(s.get('video_views',0))}</div><div class="sub"></div></div>
  </div>
  <br>
  <div class="obj-legend">
    <span class="obj-pill sw">🛒 Sales / Orders — {fmt_full(sales_k['spend'])} EGP ({sales_k['spend']/total_spend*100:.0f}%) — {sales_k['purchases']:,} orders</span>
    <span class="obj-pill pe">💬 Messages / WhatsApp — {fmt_full(msg_k['spend'])} EGP ({msg_k['spend']/total_spend*100:.0f}%) — {msg_k['messages']:,} conversations</span>
    <span class="obj-pill sm">👍 Engagement — {fmt_full(eng_k['spend'])} EGP ({eng_k['spend']/total_spend*100:.0f}%)</span>
  </div>
  <div class="insight-grid">
    {''.join(f'<div class="insight {cls}"><h4>{title}</h4><p>{body}</p></div>' for cls,title,body in insights_overview)}
  </div>
</section>

<section id="daily">
  <span class="sec-badge def">Section 2</span>
  <h2>📅 Daily Performance ({len(daily)} days)</h2>
  <div class="charts-row">
    <div class="chart-wrap"><h3>Daily Spend (EGP)</h3><canvas id="spendChart" height="200"></canvas></div>
    <div class="chart-wrap"><h3>Daily Orders</h3><canvas id="purChart" height="200"></canvas></div>
  </div>
  <br>
  <div class="charts-row">
    <div class="chart-wrap"><h3>Budget Split by Objective</h3><canvas id="splitChart" height="200"></canvas></div>
    <div class="chart-wrap"><h3>Daily CTR (%)</h3><canvas id="ctrChart" height="200"></canvas></div>
  </div>
</section>

<section id="funnel">
  <span class="sec-badge def">Section 3</span>
  <h2>🔻 Conversion Funnel</h2>
  <div class="funnel-wrap">
    <div class="funnel-step"><div class="f-num">{fmt_num(impressions)}</div><div class="f-label">Impressions</div></div>
    <div class="funnel-arrow">→<div class="f-rate">{safe_div(clicks*100,impressions):.1f}%</div></div>
    <div class="funnel-step"><div class="f-num">{fmt_num(clicks)}</div><div class="f-label">Clicks</div></div>
    <div class="funnel-arrow">→<div class="f-rate">{safe_div(vc*100,clicks):.0f}%</div></div>
    <div class="funnel-step"><div class="f-num">{fmt_num(vc)}</div><div class="f-label">View Content</div></div>
    <div class="funnel-arrow">→<div class="f-rate">{safe_div(atc*100,vc):.1f}%</div></div>
    <div class="funnel-step"><div class="f-num">{fmt_num(atc)}</div><div class="f-label">Add to Cart</div></div>
    <div class="funnel-arrow">→<div class="f-rate">{safe_div(pur*100,atc):.1f}%</div></div>
    <div class="funnel-step"><div class="f-num" style="color:var(--green)">{fmt_num(pur)}</div><div class="f-label">Orders 🍗</div></div>
  </div>
  <br>
  <div class="insight-grid">
    <div class="insight"><h4>📊 Click → View Content: {safe_div(vc*100,clicks):.0f}%</h4><p>من كل ١٠٠ كليك، {safe_div(vc*100,clicks):.0f} وصلوا لصفحة المنتج. Benchmark للمطاعم ٧٠–٩٠٪.</p></div>
    <div class="insight {'good' if safe_div(atc*100,vc) > 30 else ('bad' if safe_div(atc*100,vc) < 15 else 'warn')}"><h4>{'✅' if safe_div(atc*100,vc) > 30 else ('🔴' if safe_div(atc*100,vc) < 15 else '⚠️')} VC → ATC: {safe_div(atc*100,vc):.1f}%</h4><p>Benchmark للـ food delivery ٣٠–٥٠٪. {'النسبة ممتازة.' if safe_div(atc*100,vc) > 30 else 'تحت Benchmark — راجع تجربة الـ menu / صور المنتج.'}</p></div>
    <div class="insight {'good' if safe_div(pur*100,atc) > 40 else 'bad'}"><h4>{'✅' if safe_div(pur*100,atc) > 40 else '🔴'} ATC → Order: {safe_div(pur*100,atc):.1f}%</h4><p>Benchmark ٤٠–٦٠٪. {atc-pur:,} عميل ضافوا للسلة ومخلصوش — يستاهلوا Remarketing campaign.</p></div>
    <div class="insight"><h4>📊 الفرصة المحتملة</h4><p>لو رفعنا VC→Order من {safe_div(pur*100,vc):.1f}٪ لـ {min(safe_div(pur*100,vc)*1.5, 8):.1f}٪ → ~{int(vc * min(safe_div(pur*100,vc)*1.5, 8) / 100):,} طلب بنفس الصرف.</p></div>
  </div>
</section>

<section id="all-camps">
  <span class="sec-badge def">Section 4</span>
  <h2>📁 All Active Campaigns ({len(camps)})</h2>
  <div class="tbl-wrap"><table>
    <thead><tr><th>Campaign</th><th>Spend (EGP)</th><th>CTR</th><th>CPM</th><th>Freq</th>
      <th>Orders</th><th>ATC</th><th>Messages</th><th>CPO</th><th>ROAS</th></tr></thead>
    <tbody>{''.join(row_camp(c) for c in sorted(camps, key=lambda c:-c['insights'].get('spend',0))[:50])}</tbody>
  </table></div>
  <p style="color:var(--muted);font-size:11px;text-align:center">Showing top 50 of {len(camps)} active campaigns by spend</p>
</section>

<section id="sw">
  <span class="sec-badge sw">Section 5 · Sales / Orders</span>
  <h2 class="sw">🛒 Sales / Orders Campaigns</h2>
  <div class="obj-kpi-row">
    <div class="obj-kpi sw"><div class="label">Total Spend</div><div class="value">{fmt_full(sales_k['spend'])}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi sw"><div class="label">Orders</div><div class="value">{sales_k['purchases']:,}</div><div class="sub"></div></div>
    <div class="obj-kpi sw"><div class="label">Revenue</div><div class="value">{fmt_num(sales_k['revenue'])}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi sw"><div class="label">CPO</div><div class="value">{sales_k['cpp']:.0f}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi sw"><div class="label">ROAS</div><div class="value">{sales_k['roas']:.2f}x</div><div class="sub"></div></div>
    <div class="obj-kpi sw"><div class="label">Campaigns</div><div class="value">{len(sales_camps)}</div><div class="sub">active</div></div>
  </div>
  <div class="obj-section sw">
    <h3 style="color:var(--sw)">Campaign Breakdown</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Campaign</th><th>Spend</th><th>CTR</th><th>CPM</th><th>Freq</th>
        <th>Orders</th><th>ATC</th><th>Messages</th><th>CPO</th><th>ROAS</th></tr></thead>
      <tbody>{''.join(row_camp(c) for c in sales_camps[:30])}</tbody>
    </table></div>
    <div class="two-col" style="margin:16px 0">
      <div><h3 style="color:var(--green)">✅ Winners ({len(winners)})</h3>
        {''.join(f'<div class="badge-pill good">✅ {html.escape(c["name"][:55])} — {c["insights"]["purchases"]} orders · ROAS {safe_div(c["insights"]["revenue"],c["insights"]["spend"]):.2f}x · CPO {safe_div(c["insights"]["spend"],c["insights"]["purchases"]):.0f} EGP</div>' for c in winners[:10]) or '<p style="color:var(--muted);font-size:12px">None yet.</p>'}
      </div>
      <div><h3 style="color:var(--red)">🔴 Budget Drain ({len(losers)})</h3>
        {''.join(f'<div class="badge-pill bad">🔴 {html.escape(c["name"][:55])} — spent {c["insights"]["spend"]:,.0f} EGP · ROAS {safe_div(c["insights"]["revenue"],c["insights"]["spend"]):.2f}x</div>' for c in losers[:10]) or '<p style="color:var(--muted);font-size:12px">None identified.</p>'}
      </div>
    </div>
    <h3 style="color:var(--sw)">Top Performing Ads (by Orders)</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Ad</th><th>Campaign</th><th>Spend</th><th>Orders</th><th>ROAS</th><th>CPO</th><th>Messages</th><th>ATC</th><th>Video Views</th></tr></thead>
      <tbody>{''.join(row_ad(a) for a in ads_by_bucket['sales'][:20])}</tbody>
    </table></div>
  </div>
</section>

<section id="pe">
  <span class="sec-badge pe">Section 6 · WhatsApp / Messages</span>
  <h2 class="pe">💬 WhatsApp & Message Campaigns</h2>
  <div class="obj-kpi-row">
    <div class="obj-kpi pe"><div class="label">Total Spend</div><div class="value">{fmt_full(msg_k['spend'])}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi pe"><div class="label">Conversations</div><div class="value">{msg_k['messages']:,}</div><div class="sub">started</div></div>
    <div class="obj-kpi pe"><div class="label">Cost/Msg</div><div class="value">{msg_k['cpm_msg']:.1f}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi pe"><div class="label">Direct Orders</div><div class="value">{msg_k['purchases']:,}</div><div class="sub"></div></div>
    <div class="obj-kpi pe"><div class="label">Reach</div><div class="value">{fmt_num(msg_k['reach'])}</div><div class="sub"></div></div>
    <div class="obj-kpi pe"><div class="label">Campaigns</div><div class="value">{len(msg_camps)}</div><div class="sub"></div></div>
  </div>
  <div class="obj-section pe">
    <h3 style="color:var(--pe)">Campaign Breakdown</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Campaign</th><th>Spend</th><th>CTR</th><th>CPM</th><th>Freq</th>
        <th>Orders</th><th>ATC</th><th>Messages</th><th>Cost/Msg</th><th>ROAS</th></tr></thead>
      <tbody>{''.join(row_camp(c) for c in msg_camps[:30])}</tbody>
    </table></div>
    <h3 style="color:var(--pe);margin-top:16px">Top Message-Generating Ads</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Ad</th><th>Campaign</th><th>Spend</th><th>Orders</th><th>ROAS</th><th>CPO</th><th>Messages</th><th>ATC</th><th>Video Views</th></tr></thead>
      <tbody>{''.join(row_ad(a) for a in sorted(ads_by_bucket['messages'], key=lambda r:-r.get('messages_started',0))[:20])}</tbody>
    </table></div>
  </div>
</section>

<section id="sm">
  <span class="sec-badge sm">Section 7 · Engagement</span>
  <h2 class="sm">👍 Page Engagement & Branches Campaigns</h2>
  <div class="obj-kpi-row">
    <div class="obj-kpi sm"><div class="label">Total Spend</div><div class="value">{fmt_full(eng_k['spend'])}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi sm"><div class="label">Share</div><div class="value">{eng_k['spend']/total_spend*100:.0f}%</div><div class="sub">of budget</div></div>
    <div class="obj-kpi sm"><div class="label">Engagements</div><div class="value">{fmt_num(eng_k['post_engagement'])}</div><div class="sub"></div></div>
    <div class="obj-kpi sm"><div class="label">Reach</div><div class="value">{fmt_num(eng_k['reach'])}</div><div class="sub"></div></div>
    <div class="obj-kpi sm"><div class="label">CPM</div><div class="value">{eng_k['cpm']:.1f}</div><div class="sub">EGP</div></div>
    <div class="obj-kpi sm"><div class="label">Campaigns</div><div class="value">{len(eng_camps)}</div><div class="sub"></div></div>
  </div>
  <div class="obj-section sm">
    <h3 style="color:var(--sm)">Campaign Breakdown</h3>
    <div class="tbl-wrap"><table>
      <thead><tr><th>Campaign</th><th>Spend</th><th>CTR</th><th>CPM</th><th>Freq</th>
        <th>Orders</th><th>ATC</th><th>Messages</th><th>CPO</th><th>ROAS</th></tr></thead>
      <tbody>{''.join(row_camp(c) for c in eng_camps[:30])}</tbody>
    </table></div>
  </div>
</section>

<section id="problems">
  <span class="sec-badge def">Section 8</span>
  <h2>⚠️ Identified Problems</h2>
  <div class="two-col">
    <div>
      <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:11px;padding:15px 18px;margin-bottom:12px">
        <h4 style="color:var(--red);margin-bottom:8px">🔴 Problem 1: Engagement يستهلك {eng_k['spend']/total_spend*100:.0f}% من الميزانية</h4>
        <ul style="padding-left:16px;color:var(--muted);line-height:2;font-size:12px">
          <li>{fmt_full(eng_k['spend'])} EGP صرف بـ {eng_k['purchases']:,} طلب فقط</li>
          <li>لو 30% منهم اتحولوا لـ Sales = ~{int(eng_k['spend']*0.3/safe_div(sales_k['spend'],sales_k['purchases'] or 1)):,} طلب إضافي</li>
          <li>راجع كل كامبين Engagement لو مش عنده هدف KPI واضح</li>
        </ul>
      </div>
      <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:11px;padding:15px 18px;margin-bottom:12px">
        <h4 style="color:var(--red);margin-bottom:8px">🔴 Problem 2: Funnel Drop-offs</h4>
        <ul style="padding-left:16px;color:var(--muted);line-height:2;font-size:12px">
          <li>VC → ATC: {safe_div(atc*100,vc):.1f}% (Benchmark: 30–50%)</li>
          <li>ATC → Order: {safe_div(pur*100,atc):.1f}% (Benchmark: 40–60%)</li>
          <li>{atc-pur:,} عميل ضافوا للسلة ولم يكملوا</li>
        </ul>
      </div>
    </div>
    <div>
      <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:11px;padding:15px 18px;margin-bottom:12px">
        <h4 style="color:var(--red);margin-bottom:8px">🔴 Problem 3: Frequency {s.get('frequency',0):.2f}x</h4>
        <ul style="padding-left:16px;color:var(--muted);line-height:2;font-size:12px">
          <li>الجمهور بيشوف نفس الإعلانات بمعدل عالي</li>
          <li>خطر creative fatigue → CPM يطلع و CTR ينزل</li>
          <li>جدد creatives شهرياً ووسّع الـ audience</li>
        </ul>
      </div>
      <div style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.3);border-radius:11px;padding:15px 18px;margin-bottom:12px">
        <h4 style="color:var(--red);margin-bottom:8px">🔴 Problem 4: WhatsApp Conversion ضعيف</h4>
        <ul style="padding-left:16px;color:var(--muted);line-height:2;font-size:12px">
          <li>{msg_k['messages']:,} محادثة بدأت، {msg_k['purchases']:,} طلب فقط</li>
          <li>معدل الإغلاق ~{safe_div(msg_k['purchases']*100, msg_k['messages']):.1f}% — Benchmark 10-15%</li>
          <li>راجع responsiveness فريق الـ WhatsApp وقوالب الرد</li>
        </ul>
      </div>
    </div>
  </div>
</section>

<section id="insights">
  <span class="sec-badge def">Section 9</span>
  <h2>💡 Strategic Recommendations</h2>
  <div class="insight-grid">
    <div class="insight good">
      <h4>🚀 Priority 1: Scale Winners</h4>
      <p>أعلى {min(3,len(winners))} كامبينز Sales (ROAS > 3x): زود بودجت كل منهم +30-50% كل 3 أيام طول ما الـ ROAS فوق 3x.</p>
    </div>
    <div class="insight bad">
      <h4>⛔ Priority 2: Pause Budget Drains</h4>
      <p>{len(losers)} كامبين Sales بـ ROAS < 1.5x وصرف +1000 EGP — أوقفهم وحوّل البودجت للـ Winners.</p>
    </div>
    <div class="insight warn">
      <h4>🔁 Priority 3: WhatsApp Funnel</h4>
      <p>اعمل Custom Audience للناس اللي بعتت رسالة + ATC وارجاع لهم بـ Sales campaign مع عرض خاص — أرخص CPO ممكن.</p>
    </div>
    <div class="insight warn">
      <h4>📹 Priority 4: Creative Refresh</h4>
      <p>Frequency {s.get('frequency',0):.2f}x = الجمهور مشبع. اعمل 3-5 creatives جديدة شهرياً (UGC، طلبات حقيقية، before/after أكلات).</p>
    </div>
    <div class="insight">
      <h4>🍗 Priority 5: Peak Hour Spend</h4>
      <p>راجع الـ daily breakdown — لو فيه أيام معينة CTR أعلى، استخدم Day Parting لتركيز البودجت في ساعات الذروة (لانش + ديناير).</p>
    </div>
    <div class="insight">
      <h4>📊 Priority 6: Branch-Level Tracking</h4>
      <p>أضف UTM tags لكل branch / منطقة دلتا حتى تقدر تقيس الـ campaigns لكل فرع لوحده وتعرف فين بالظبط الأكثر تحويل.</p>
    </div>
  </div>
</section>

</div>

<script>
const labels = {json.dumps(labels)};
const spends = {json.dumps(spends)};
const ctrs   = {json.dumps(ctrs)};
const dpurs  = {json.dumps(purs)};
const grid = 'rgba(255,255,255,0.05)';
const base = () => ({{responsive:true,plugins:{{legend:{{display:false}},tooltip:{{mode:'index'}}}},scales:{{x:{{ticks:{{color:'#a89878',maxRotation:45}},grid:{{color:grid}}}},y:{{ticks:{{color:'#a89878'}},grid:{{color:grid}}}}}}}});

new Chart(document.getElementById('spendChart'),{{type:'bar',data:{{labels,datasets:[{{label:'Spend',data:spends,backgroundColor:'rgba(245,184,46,0.7)',borderColor:'#F5B82E',borderWidth:1}}]}},options:base()}});
new Chart(document.getElementById('purChart'),{{type:'bar',data:{{labels,datasets:[{{label:'Orders',data:dpurs,backgroundColor:'rgba(34,197,94,0.7)',borderColor:'#22c55e',borderWidth:1}}]}},options:base()}});
new Chart(document.getElementById('splitChart'),{{type:'doughnut',
  data:{{labels:["Sales / Orders","WhatsApp / Messages","Engagement"],datasets:[{{data:[{sales_k['spend']:.0f},{msg_k['spend']:.0f},{eng_k['spend']:.0f}],backgroundColor:['rgba(245,184,46,0.85)','rgba(230,57,70,0.85)','rgba(255,255,255,0.6)'],borderWidth:0}}]}},
  options:{{responsive:true,plugins:{{legend:{{position:'bottom',labels:{{color:'#f5ecd5',font:{{size:12}}}}}},tooltip:{{callbacks:{{label:function(c){{return c.label+': '+c.raw.toLocaleString()+' EGP'}}}}}}}}}}
}});
new Chart(document.getElementById('ctrChart'),{{type:'line',data:{{labels,datasets:[{{label:'CTR%',data:ctrs,borderColor:'#E63946',backgroundColor:'rgba(230,57,70,0.1)',tension:0.4,fill:true,pointRadius:3}}]}},options:base()}});
</script>
</body>
</html>"""

    OUT.write_text(html_out)
    print(f"✓ wrote {OUT}")
    print(f"  {len(camps)} campaigns · {len(ads)} ads · {len(daily)} days")
    print(f"  Sales: {len(sales_camps)} · Messages: {len(msg_camps)} · Engagement: {len(eng_camps)}")


if __name__ == "__main__":
    main()
