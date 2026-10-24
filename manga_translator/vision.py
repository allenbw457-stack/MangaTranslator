"""Vision-assisted translation: send the actual comic page alongside OCR regions."""
from __future__ import annotations
import base64
import io
import json
import re
from PIL import Image

def translate_page_vision(image: Image.Image, regions: list[dict], api_key: str,
                          model: str, previous: str = "") -> list[str]:
    if not regions:
        return []
    from openai import OpenAI
    page = image.convert("RGB")
    page.thumbnail((1800, 2400))
    buffer = io.BytesIO()
    page.save(buffer, format="JPEG", quality=86)
    data_url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    entries = [{"id": i, "box": list(map(int, r["box"])), "ocr": r["jp"]}
               for i, r in enumerate(regions)]
    prompt = (
        "你是日文漫畫專業譯者。請同時觀察漫畫畫面與下方 OCR 文字，"
        "理解人物表情、分鏡、對話順序及上下文，修正明顯的 OCR 錯字。"
        "翻譯成自然的台灣繁體中文，保留角色語氣、稱呼、敬語和情緒。"
        "不要自行增添劇情。只翻譯本頁列出的 id，"
        "回傳 JSON 物件，格式為 {\"translations\":[{\"id\":0,\"zh\":\"...\"}]}。"
        "每個 id 恰好一次；無法辨認時仍保留該 id 並給空字串。\n"
        "前頁參考（僅作語境，不可輸出）：\n" + previous[-2500:] +
        "\n本頁 OCR 區域（box 為原圖座標）：\n" + json.dumps(entries, ensure_ascii=False)
    )
    response = OpenAI(api_key=api_key).responses.create(
        model=model,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": data_url}
        ]}]
    )
    raw = response.output_text.strip()
    raw = re.sub(r"^\x60\x60\x60(?:json)?\s*|\s*\x60\x60\x60$", "", raw, flags=re.I)
    parsed = json.loads(raw)
    items = parsed["translations"] if isinstance(parsed, dict) else parsed
    result = {}
    for item in items:
        idx = int(item["id"])
        if idx in result or not 0 <= idx < len(regions):
            raise ValueError("AI 回傳了重複或不合法的翻譯 id")
        result[idx] = str(item["zh"])
    if len(result) != len(regions):
        raise ValueError("AI 未回傳所有 OCR 區域，請重試")
    return [result[i] for i in range(len(regions))]
