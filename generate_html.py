# -*- coding: utf-8 -*-
"""
讀取 data/latest.json，產生 docs/index.html
docs/ 資料夾是為了配合 GitHub Pages 的預設發佈路徑。
"""

import json
from datetime import datetime

PERIOD_LABELS = {"1": "1日", "5": "5日", "10": "10日", "20": "20日"}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股籌碼集中度排行</title>
<style>
  body {{
    font-family: -apple-system, "Microsoft JhengHei", sans-serif;
    background: #f5f6fa;
    margin: 0;
    padding: 20px;
    color: #222;
  }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .meta {{ color: #777; font-size: 13px; margin-bottom: 16px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
  .tab-btn {{
    padding: 8px 18px;
    border: 1px solid #ccc;
    border-radius: 6px;
    background: #fff;
    cursor: pointer;
    font-size: 14px;
  }}
  .tab-btn.active {{ background: #2d5be3; color: #fff; border-color: #2d5be3; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    font-size: 14px;
  }}
  th, td {{ padding: 8px 10px; text-align: right; border-bottom: 1px solid #eee; }}
  th:nth-child(1), td:nth-child(1),
  th:nth-child(2), td:nth-child(2),
  th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
  th {{ background: #fafafa; font-weight: 600; color: #555; }}
  tr:hover {{ background: #f0f4ff; }}
  .positive {{ color: #d23; }}
  .negative {{ color: #197; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .download-bar {{ margin-top: 10px; }}
  .download-btn {{
    display: inline-block;
    padding: 8px 16px;
    background: #197b3e;
    color: #fff;
    text-decoration: none;
    border-radius: 6px;
    font-size: 13px;
  }}
  .download-btn:hover {{ background: #145c2e; }}
</style>
</head>
<body>

<h1>台股籌碼集中度排行（前20名）</h1>
<div class="meta">
  資料來源更新時間：{source_updated_at}　|　爬蟲擷取時間：{fetched_at}
</div>

<div class="tabs">
  {tab_buttons}
</div>

{panels}

<script>
function showTab(period) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('btn-' + period).classList.add('active');
  document.getElementById('panel-' + period).classList.add('active');
}}
showTab('1');
</script>

</body>
</html>
"""

ROW_TEMPLATE = """<tr>
  <td>{rank}</td>
  <td>{code}</td>
  <td>{name}</td>
  <td class="{c1}">{d1}</td>
  <td class="{c5}">{d5}</td>
  <td class="{c10}">{d10}</td>
  <td class="{c20}">{d20}</td>
  <td class="{c60}">{d60}</td>
  <td class="{c120}">{d120}</td>
  <td>{avg_vol_10d}</td>
</tr>"""


def cls(v):
    try:
        return "positive" if float(v) > 0 else ("negative" if float(v) < 0 else "")
    except ValueError:
        return ""


def build_watchlist_text(rows, market_map):
    """把該分頁的股票代碼組成 TradingView 可匯入的觀察清單格式"""
    # 優先查對照表判斷是上市(TWSE)還是上櫃(TPEX)；
    # 如果對照表裡查不到（極少數情況），預設用 TWSE。
    symbols = [f"{market_map.get(r['code'], 'TWSE')}:{r['code']}" for r in rows]
    return ",".join(symbols)


def build_panel(period, rows):
    trs = []
    for r in rows:
        trs.append(ROW_TEMPLATE.format(
            rank=r["rank"], code=r["code"], name=r["name"],
            d1=r["d1"], d5=r["d5"], d10=r["d10"], d20=r["d20"],
            d60=r["d60"], d120=r["d120"], avg_vol_10d=r["avg_vol_10d"],
            c1=cls(r["d1"]), c5=cls(r["d5"]), c10=cls(r["d10"]),
            c20=cls(r["d20"]), c60=cls(r["d60"]), c120=cls(r["d120"]),
        ))
    table = f"""
<div id="panel-{period}" class="panel">
  <table>
    <thead>
      <tr>
        <th>排名</th><th>代碼</th><th>名稱</th>
        <th>1日</th><th>5日</th><th>10日</th><th>20日</th><th>60日</th><th>120日</th>
        <th>10日均量</th>
      </tr>
    </thead>
    <tbody>
      {''.join(trs)}
    </tbody>
  </table>
  <div class="download-bar">
    <a class="download-btn" href="watchlist_{period}.txt" download>
      ⬇ 下載 TradingView 觀察清單（{PERIOD_LABELS[period]}排行 .txt）
    </a>
  </div>
</div>"""
    return table


def main():
    with open("data/latest.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 讀取上市/上櫃對照表（scraper.py 產生），找不到就當作空字典（全部 fallback 用 TWSE）
    try:
        with open("data/market_map.json", "r", encoding="utf-8") as f:
            market_map = json.load(f)
    except FileNotFoundError:
        market_map = {}

    tab_buttons = "\n".join(
        f'<button class="tab-btn" id="btn-{p}" onclick="showTab(\'{p}\')">{PERIOD_LABELS[p]}排行</button>'
        for p in PERIOD_LABELS
    )

    panels = "\n".join(
        build_panel(p, data["data"].get(p, [])) for p in PERIOD_LABELS
    )

    html = HTML_TEMPLATE.format(
        source_updated_at=data.get("source_updated_at", "未知"),
        fetched_at=data.get("fetched_at", "未知"),
        tab_buttons=tab_buttons,
        panels=panels,
    )

    import os
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 為每個分頁產生 TradingView 觀察清單 txt 檔
    for p in PERIOD_LABELS:
        watchlist_text = build_watchlist_text(data["data"].get(p, []), market_map)
        with open(f"docs/watchlist_{p}.txt", "w", encoding="utf-8") as f:
            f.write(watchlist_text)

    print("已產生 docs/index.html 與各分頁 watchlist txt 檔")


if __name__ == "__main__":
    main()
