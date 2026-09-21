# MangaTranslator

Windows 日文漫畫 → 繁體中文批次翻譯工具。

## 功能
- 整個漫畫資料夾加入
- 自動排序 JPG / JPEG / PNG / WebP / BMP
- OpenCV 自動偵測候選文字區
- Manga OCR 驗證日文
- OpenAI AI 整頁與跨頁上下文翻譯
- 清除原日文並自動嵌入繁體中文
- 批次輸出到 `translated_zh-TW`
- `progress.json` 斷點續跑
- GitHub Actions 自動建立 Windows 可攜版

## Windows 可攜版
到 GitHub 的 **Actions → Build Windows Portable → Run workflow**。
建置完成後，在該次 workflow 的 Artifacts 下載 `MangaTranslatorPortable`，
解壓縮後執行 `MangaTranslatorPortable.exe`。

OpenAI API Key 不要放進 GitHub；請在程式內的「API 設定」輸入。
