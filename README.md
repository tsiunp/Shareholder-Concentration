# 籌碼集中度排行 自動爬蟲＋網頁

專案會**一至五23:30**自動抓取 peicheng.com.tw 的籌碼集中度排行（1日/5日/10日/20日），
並自動更新成一個網頁，你隨時打開連結就能看到最新資料。全程免費、不需要開自己的電腦。

---

## 完成後你會得到什麼

一個網址（類似 `https://你的帳號.github.io/peicheng-scraper/`），
打開就能看到 4 個分頁（1日/5日/10日/20日）的前20名排行表，每天自動更新一次。

---

## 設定步驟（第一次設定大約 15-20 分鐘，之後完全自動）

### 步驟 1：註冊 GitHub 帳號
如果還沒有帳號，到 https://github.com/signup 免費註冊一個。

### 步驟 2：建立一個新的 Repository（專案倉庫）
1. 登入後點右上角 **+** → **New repository**
2. Repository name 填 `peicheng-scraper`（或你喜歡的名字）
3. 選 **Public**（GitHub Pages 免費版需要 Public）
4. 不用勾選任何初始化選項，直接點 **Create repository**

### 步驟 3：把這些檔案上傳上去
在剛建立好的空 repository 頁面，會看到 "uploading an existing file" 的連結：
1. 點 **uploading an existing file**
2. 把我準備好的整個資料夾（`peicheng-scraper` 內的所有檔案，**包含 `.github` 這個隱藏資料夾**）拖曳上傳
   - 如果網頁介面不方便一次拖整個資料夾結構，也可以改用「步驟 3b」的 GitHub Desktop 方式（見下方）
3. 下方填寫 commit message，例如「初始上傳」，點 **Commit changes**

> ⚠️ 注意：`.github/workflows/daily-update.yml` 這個檔案路徑一定要保留，
> 不能把 `.github` 資料夾內容跟其他檔案混在一起上傳，路徑結構要維持原樣。
> 如果網頁拖曳上傳對資料夾結構支援不好，建議改用下面的 GitHub Desktop。

#### 步驟 3b（推薦，更不會出錯）：使用 GitHub Desktop
1. 下載安裝 GitHub Desktop：https://desktop.github.com/
2. 登入你的 GitHub 帳號
3. File → Clone repository，選你剛建立的 `peicheng-scraper`，複製到你電腦一個資料夾
4. 把我給你的所有檔案（保留原本的資料夾結構）複製貼到那個資料夾裡，覆蓋掉裡面的空內容
5. 回到 GitHub Desktop，下方會顯示變更的檔案，填寫 commit 訊息，點 **Commit to main**
6. 點右上角 **Push origin**，檔案就上傳到 GitHub 了

### 步驟 4：開啟 GitHub Pages
1. 到你的 repository 頁面 → 上方選單 **Settings**
2. 左側選單找到 **Pages**
3. 在 **Build and deployment** → Source 選 **Deploy from a branch**
4. Branch 選 `main`，資料夾選 `/docs`，點 **Save**
5. 等 1-2 分鐘，畫面上方會出現你的網址，例如：
   `https://你的帳號.github.io/peicheng-scraper/`

### 步驟 5：手動先跑一次，確認有資料
因為排程是設定在每天固定時間才自動跑，第一次要手動觸發一次：
1. 到 repository 頁面 → 上方選單 **Actions**
2. 左側會看到 **每日更新籌碼集中度排行**，點進去
3. 右上角有 **Run workflow** 按鈕，點下去 → 再點綠色的 **Run workflow** 確認
4. 等 1-2 分鐘，跑完後綠勾勾代表成功
5. 回到步驟 4 拿到的網址打開，應該就能看到資料了

完成！之後**每個交易日台灣時間下午 3:10** 會自動重新執行一次，網頁會自動更新，你完全不用管它。

---

## 之後想要調整時間怎麼辦？

打開 `.github/workflows/daily-update.yml`，修改這一行：

```yaml
- cron: '10 7 * * 1-5'
```

格式是「分 時 日 月 星期」，**時間是 UTC 標準時間，要減掉台灣時間 8 小時**。
例如想要台灣時間晚上 6:00 執行，就改成 `0 10 * * 1-5`（UTC 10:00 = 台灣 18:00）。

---

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `scraper.py` | 爬蟲主程式，抓取 4 個分頁的排行資料，存成 `data/latest.json` 和 `data/history.csv` |
| `generate_html.py` | 讀取資料，產生 `docs/index.html` 網頁 |
| `requirements.txt` | 需要安裝的 Python 套件清單 |
| `.github/workflows/daily-update.yml` | GitHub Actions 排程設定，每天自動跑爬蟲+更新網頁+上傳 |
| `data/history.csv` | 每天執行後會累積歷史資料，未來可以拿來做趨勢分析 |

---

## 重要提醒

- 這個爬蟲只是「讀取」網頁上公開顯示的資料，並不會做任何登入或繞過保護的行為，
  抓取頻率設定為**一天一次**，對原網站沒有負擔。
- 網站的頁面結構如果未來改版，`scraper.py` 可能需要跟著調整，
  屆時可以把新的網頁原始碼貼給我，我再幫你更新程式。
- 資料僅供參考，不構成投資建議。
