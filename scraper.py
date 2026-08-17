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
            table = soup.find("table")
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
    print(f"對照表筆數：{len(market_map)}")

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
