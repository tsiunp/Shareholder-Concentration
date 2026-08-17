# -*- coding: utf-8 -*-
"""
peicheng.com.tw 籌碼集中度排行 爬蟲
抓取 1日 / 5日 / 10日 / 20日 排行資料，存成 data/latest.json
同時把每天的資料附加到 data/history.csv，方便未來查歷史。
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import csv
from datetime import datetime

BASE_URL = "https://www.peicheng.com.tw/asp/main/report/dream_report/"

# 四個分頁對應的頁面檔名（中文檔名，requests 會自動處理編碼）
PAGES = {
    "1": "籌碼集中度1日排行.htm",
    "5": "籌碼集中度5日排行.htm",
    "10": "籌碼集中度10日排行.htm",
    "20": "籌碼集中度20日排行.htm",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 表格欄位順序（依實際觀察到的網頁結構）
COLUMNS = [
    "rank", "code", "name",
    "d1", "d5", "d10", "d20", "d60", "d120",
    "avg_vol_10d",
]

TOP_N = 20  # 使用者只需要前20名

# 台灣證交所公開的「上市/上櫃證券清單」，用來判斷每檔股票該用 TWSE 還是 TPEX
MARKET_LIST_URLS = {
    "TWSE": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",  # 上市
    "TPEX": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4",  # 上櫃
}


def build_market_map():
    """
    抓取證交所公開清單，回傳 {股票代碼: "TWSE" 或 "TPEX"} 的對照表。
    如果證交所網站一時抓不到，回傳空字典，之後會 fallback 用 TWSE 當預設值。
    """
    market_map = {}
    for market, url in MARKET_LIST_URLS.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            resp.encoding = "big5"
            soup = BeautifulSoup(resp.text, "html.parser")
            # 這個頁面上有多個 table（含版面用的），真正的股票清單表格是 class="h4"，
            # 一定要精準指定，否則會抓到錯的表格（例如版頭），導致清單是空的
            table = soup.find("table", {"class": "h4"})
            if table is None:
                table = soup.find("table")  # 備用：萬一網站改版拿掉 class，退而求其次
            if table is None:
                print(f"警告：{market} 清單頁面找不到表格，略過")
                continue

            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                first_cell = tds[0].get_text()
                # 資料列格式是「代碼\u3000名稱」（中間是全形空白），
                # 分類標題列（如「股票」、「ETF」）沒有這個全形空白，會被跳過
                if "\u3000" not in first_cell:
                    continue
                code = first_cell.split("\u3000", 1)[0].strip()
                if code.isdigit():
                    market_map[code] = market
        except requests.RequestException as e:
            print(f"警告：抓取 {market} 清單失敗（{e}），略過")

    return market_map


# 期交所「股票期貨/股票選擇權 交易標的」清單網址
FUTURES_LIST_URL = "https://www.taifex.com.tw/cht/2/stockLists"


def build_futures_map():
    """
    抓取期交所股票期貨標的清單，回傳：
    {股票代碼: {"futures": True/False, "mini_futures": True/False}}
    判斷方式：清單裡每個商品有「標準型證券股數」欄位，
    2,000（一般股票）或 10,000（ETF）代表一般期貨；
    100（一般股票）或 1,000（ETF）代表小型期貨。
    """
    futures_map = {}
    try:
        resp = requests.get(FUTURES_LIST_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # 頁面上有多個 table，用欄位關鍵字找到真正的標的清單表格
        target_table = None
        for t in soup.find_all("table"):
            header_text = t.get_text()
            if "證券代號" in header_text and "標準型" in header_text:
                target_table = t
                break

        if target_table is None:
            print("警告：找不到期交所股票期貨標的表格，略過")
            return futures_map

        for tr in target_table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 12:
                continue
            code = tds[2].get_text(strip=True)
            if not code or not code[0].isdigit():
                continue  # 跳過標題列、合計列
            unit = tds[11].get_text(strip=True).replace(",", "")
            entry = futures_map.setdefault(code, {"futures": False, "mini_futures": False})
            if unit in ("2000", "10000"):
                entry["futures"] = True
            elif unit in ("100", "1000"):
                entry["mini_futures"] = True
    except requests.RequestException as e:
        print(f"警告：抓取股票期貨標的清單失敗（{e}），略過")

    return futures_map


def build_price_map():
    """
    抓取上市（TWSE）+ 上櫃（TPEX）官方每日收盤價，回傳 {股票代碼: 收盤價字串}
    同時回傳資料實際對應的日期字串，方便驗證是否真的是「今天」的收盤價。
 
    注意：上市部分原本用 openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL，
    但實測發現這個端點固定會延遲一個交易日（不管多晚打都一樣），
    改用證交所「每日收盤行情」端點 www.twse.com.tw/exchangeReport/MI_INDEX，
    這個才會在收盤後即時更新成當天的資料。
    """
    price_map = {}
    price_dates = {}
    today_compact = datetime.now().strftime("%Y%m%d")  # 例如 20260817

    # 上市：證交所 OpenAPI
    try:
        resp = requests.get(
            "https://www.twse.com.tw/exchangeReport/MI_INDEX",
            params={"response": "json", "date": today_compact, "type": "ALLBUT0999"},
            headers=HEADERS, timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
 
        if body.get("stat") == "OK":
            # 這份報表裡有好幾張表格（指數、個股行情等），
            # 用欄位名稱找出「證券代號、收盤價」在哪一張表，不寫死索引避免格式變動就壞掉
            fields_list, rows = [], []
            for key in body:
                if key.startswith("fields"):
                    idx = key[len("fields"):]
                    f = body.get(f"fields{idx}") or []
                    d = body.get(f"data{idx}") or []
                    if "證券代號" in f and "收盤價" in f:
                        fields_list, rows = f, d
                        break
 
            if fields_list and rows:
                code_idx = fields_list.index("證券代號")
                close_idx = fields_list.index("收盤價")
                for row in rows:
                    if len(row) > max(code_idx, close_idx):
                        code = row[code_idx].strip()
                        close = row[close_idx].strip()
                        if code:
                            price_map[code] = close
                price_dates["TWSE"] = (
                    f"{today_compact[:4]}/{today_compact[4:6]}/{today_compact[6:]}"
                )
            else:
                print("警告：TWSE 每日收盤行情回傳格式不如預期，找不到收盤價欄位，略過")
        else:
            print(f"警告：TWSE 今天（{today_compact}）尚無資料，"
                  f"可能是非交易日或資料還沒更新（stat={body.get('stat')}）")
    except Exception as e:
        print(f"警告：抓取上市收盤價失敗（{e}），略過")

    # 上櫃：櫃買中心 OpenAPI
    try:
        resp = requests.get(
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
            headers=HEADERS, timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            code = (item.get("SecuritiesCompanyCode") or "").strip()
            close = (item.get("Close") or "").strip()
            if code:
                price_map[code] = close
        if data:
            price_dates["TPEX"] = (data[0].get("Date") or "").strip()
    except Exception as e:
        print(f"警告：抓取上櫃收盤價失敗（{e}），略過")

    return price_map, price_dates


def fetch_table(period: str):
    """抓取單一分頁（1/5/10/20日）的排行表格"""
    url = BASE_URL + PAGES[period]
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    # 網站是 Big5 編碼（繁體中文舊編碼），一定要指定，否則會變亂碼
    resp.encoding = "big5"

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError(f"找不到表格，網站結構可能改變了：{url}")

    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 9:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # 跳過標題列 / 說明列：資料列的第一格應該是純數字排名
        if not texts[0].isdigit():
            continue

        row = dict(zip(COLUMNS, texts))
        rows.append(row)

        if len(rows) >= TOP_N:
            break

    return rows


def find_update_time(period: str) -> str:
    """從網頁下方文字擷取更新時間戳記（格式如 2026/8/15 23:02）"""
    url = BASE_URL + PAGES[period]
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "big5"
    text = resp.text
    # 簡單抓取時間格式，若抓不到就用現在時間代替
    import re
    m = re.search(r"\d{4}/\d{1,2}/\d{1,2}\s*\d{1,2}:\d{2}", text)
    return m.group(0) if m else datetime.now().strftime("%Y/%m/%d %H:%M")


def main():
    result = {
        "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_updated_at": None,
        "data": {},
    }

    for period in PAGES:
        print(f"抓取 {period} 日排行中...")
        rows = fetch_table(period)
        result["data"][period] = rows
        if result["source_updated_at"] is None:
            result["source_updated_at"] = find_update_time(period)

    os.makedirs("data", exist_ok=True)

    # 1) 存最新一份完整資料（給網頁讀取用）
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 1b) 抓取上市/上櫃對照表，存成 data/market_map.json（給產生 TradingView 清單用）
    print("抓取上市/上櫃對照表中...")
    market_map = build_market_map()
    with open("data/market_map.json", "w", encoding="utf-8") as f:
        json.dump(market_map, f, ensure_ascii=False)

    # 印出各市場筆數，方便從執行紀錄檢查有沒有抓漏（正常應該兩邊都有上千筆）
    twse_count = sum(1 for v in market_map.values() if v == "TWSE")
    tpex_count = sum(1 for v in market_map.values() if v == "TPEX")
    print(f"對照表筆數：TWSE={twse_count}, TPEX={tpex_count}, 總計={len(market_map)}")
    if tpex_count == 0:
        print("警告：TPEX（上櫃）清單筆數為 0，可能抓取失敗，該分類股票會 fallback 用 TWSE")

    # 1c) 抓取股票期貨/小型股票期貨標的清單，存成 data/futures_map.json
    print("抓取股票期貨標的清單中...")
    futures_map = build_futures_map()
    with open("data/futures_map.json", "w", encoding="utf-8") as f:
        json.dump(futures_map, f, ensure_ascii=False)
    futures_count = sum(1 for v in futures_map.values() if v["futures"])
    mini_count = sum(1 for v in futures_map.values() if v["mini_futures"])
    print(f"股票期貨標的筆數：一般={futures_count}, 小型={mini_count}")

    # 1d) 抓取上市+上櫃官方收盤價，存成 data/price_map.json
    print("抓取收盤價中...")
    price_map, price_dates = build_price_map()
    with open("data/price_map.json", "w", encoding="utf-8") as f:
        json.dump(price_map, f, ensure_ascii=False)
    print(f"收盤價筆數：{len(price_map)}")
    print(f"收盤價資料日期 → TWSE: {price_dates.get('TWSE', '未知')}　"
          f"TPEX: {price_dates.get('TPEX', '未知')}")
    today_str = datetime.now().strftime("%Y/%m/%d")
    if price_dates.get("TWSE") and price_dates["TWSE"] != today_str:
        print(f"⚠️ 注意：TWSE 收盤價日期（{price_dates['TWSE']}）跟今天（{today_str}）不同，"
              f"可能是證交所資料還沒更新，或今天非交易日")

    # 2) 附加寫入歷史紀錄 CSV（方便之後想做趨勢分析）
    history_path = "data/history.csv"
    file_exists = os.path.isfile(history_path)
    with open(history_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["fetch_date", "period", "rank", "code", "name",
                              "d1", "d5", "d10", "d20", "d60", "d120", "avg_vol_10d"])
        fetch_date = result["fetched_at"][:10]
        for period, rows in result["data"].items():
            for r in rows:
                writer.writerow([
                    fetch_date, period, r["rank"], r["code"], r["name"],
                    r["d1"], r["d5"], r["d10"], r["d20"], r["d60"], r["d120"],
                    r["avg_vol_10d"],
                ])

    print("完成！資料已存到 data/latest.json 與 data/history.csv")


if __name__ == "__main__":
    main()
