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
<title>TWSExTPEX_籌碼集中度排行</title>
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
  /* 表格外層包一層可以橫向滑動的容器，手機螢幕太窄時可以左右滑，
     欄位不會被硬擠壓變形、看不清楚 */
  .table-scroll {{
    width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  table {{
    width: 100%;
    min-width: 720px;
    border-collapse: collapse;
    font-size: 14px;
    table-layout: fixed;
  }}
  th, td {{
    padding: 8px 10px;
    text-align: right;
    border-bottom: 1px solid #eee;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
  th:nth-child(1), td:nth-child(1),
  th:nth-child(2), td:nth-child(2),
  th:nth-child(3), td:nth-child(3) {{ text-align: left; }}
  .stock-link {{
    color: #2d5be3;
    text-decoration: none;
  }}
  .stock-link:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block;
    margin-left: 4px;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    line-height: 1.5;
    vertical-align: middle;
    color: #fff;
  }}
  .badge-futures {{ background: #d9822b; }}
  .badge-mini {{ background: #7a5ec9; }}
  .highlight-col {{ background: rgba(0,0,0,0.06); }}
  th {{ background: #fafafa; font-weight: 600; color: #555; }}
  tr:hover {{ background: #f0f4ff; }}
  .positive {{ color: #d23; }}
  .negative {{ color: #197; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .scroll-hint {{
    display: none;
    font-size: 12px;
    color: #999;
    margin: 4px 0 8px;
  }}
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

  /* 手機/小螢幕（寬度小於600px）：縮小字體跟間距，並顯示「左右滑動可看更多」提示 */
  @media (max-width: 600px) {{
    body {{ padding: 12px; }}
    h1 {{ font-size: 18px; }}
    .meta {{ font-size: 11px; }}
    .tab-btn {{ padding: 6px 12px; font-size: 13px; }}
    table {{ font-size: 12px; }}
    th, td {{ padding: 6px 8px; }}
    .scroll-hint {{ display: block; }}
  }}
</style>
</head>
<body>

<h1>TWSExTPEX_籌碼集中度排行</h1>
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
  <td><a class="stock-link" href="https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={code}" target="_blank" rel="noopener">{name}</a>{badges}</td>
  <td>{close_price}</td>
  <td class="{c1} {hl1}">{d1}</td>
  <td class="{c5} {hl5}">{d5}</td>
  <td class="{c10} {hl10}">{d10}</td>
  <td class="{c20} {hl20}">{d20}</td>
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


def build_badges(futures_info):
    """
    根據該股票有沒有期貨/小型期貨，組成要貼在名稱旁邊的小徽章 HTML。
    滑鼠移上去會顯示完整說明文字（title 屬性）。
    """
    badges = ""
    if futures_info.get("futures"):
        badges += '<span class="badge badge-futures" title="有股票期貨">期</span>'
    if futures_info.get("mini_futures"):
        badges += '<span class="badge badge-mini" title="有小型股票期貨">小</span>'
    return badges


def build_panel(period, rows, futures_map, price_map):
    # 依照目前分頁是哪個週期，決定要幫「1日/5日/10日/20日」哪一欄加上灰底樣式，
    # 例如目前是 5日排行，就只有 5日 那欄（含表頭）會有 highlight-col
    hl1 = "highlight-col" if period == "1" else ""
    hl5 = "highlight-col" if period == "5" else ""
    hl10 = "highlight-col" if period == "10" else ""
    hl20 = "highlight-col" if period == "20" else ""

    trs = []
    for r in rows:
        code = r["code"]
        close_price = price_map.get(code, "-")
        futures_info = futures_map.get(code, {"futures": False, "mini_futures": False})

        trs.append(ROW_TEMPLATE.format(
            rank=r["rank"], code=r["code"], name=r["name"],
            close_price=close_price,
            badges=build_badges(futures_info),
            d1=r["d1"], d5=r["d5"], d10=r["d10"], d20=r["d20"],
            d60=r["d60"], d120=r["d120"], avg_vol_10d=r["avg_vol_10d"],
            c1=cls(r["d1"]), c5=cls(r["d5"]), c10=cls(r["d10"]),
            c20=cls(r["d20"]), c60=cls(r["d60"]), c120=cls(r["d120"]),
            hl1=hl1, hl5=hl5, hl10=hl10, hl20=hl20,
        ))
    table = f"""
<div id="panel-{period}" class="panel">
  <div class="scroll-hint">← 可左右滑動查看更多欄位 →</div>
  <div class="table-scroll">
  <table>
    <colgroup>
      <col style="width:5%">
      <col style="width:8%">
      <col style="width:15%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:9%">
      <col style="width:14%">
    </colgroup>
    <thead>
      <tr>
        <th>排名</th><th>代碼</th><th>名稱</th>
        <th>收盤價</th>
        <th class="{hl1}">1日</th><th class="{hl5}">5日</th><th class="{hl10}">10日</th><th class="{hl20}">20日</th><th>60日</th><th>120日</th>
        <th>10日均量</th>
      </tr>
    </thead>
    <tbody>
      {''.join(trs)}
    </tbody>
  </table>
  </div>
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

    # 讀取股票期貨標的清單、收盤價（scraper.py 產生），找不到就當空字典
    try:
        with open("data/futures_map.json", "r", encoding="utf-8") as f:
            futures_map = json.load(f)
    except FileNotFoundError:
        futures_map = {}

    try:
        with open("data/price_map.json", "r", encoding="utf-8") as f:
            price_map = json.load(f)
    except FileNotFoundError:
        price_map = {}

    tab_buttons = "\n".join(
        f'<button class="tab-btn" id="btn-{p}" onclick="showTab(\'{p}\')">{PERIOD_LABELS[p]}排行</button>'
        for p in PERIOD_LABELS
    )

    panels = "\n".join(
        build_panel(p, data["data"].get(p, []), futures_map, price_map) for p in PERIOD_LABELS
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
