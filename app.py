from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage
import requests, re, base64, json
import google.generativeai as genai
from PIL import Image
import io

app = Flask(__name__)

CHANNEL_SECRET = "b93724c6fd5dddee1495932a4367a5ce"
CHANNEL_ACCESS_TOKEN = "GPL9lvUqlBA0IKDRFSAf0fiN9gJX035jQa7FsO8LsFJelISR4vEJAnI7BSeHWHArO9pSkWuKVf+0Fx4bzikxHuwZKWSPrKNcu6M5fwKYoZLw/TIEgbtpWUMicO5+1vo+qIIm+UB64B3GRT6HqYz2lAdB04t89/1O/w1cDnyilFU="
SHEET_URL = "https://script.google.com/macros/s/AKfycbyl8XUm35tvJbpHrNk9SIwDI1yXgc_37B08GleMdWeJb8ZI8irJMC9s2shyxYpbLbXw/exec"
GEMINI_API_KEY = "AIzaSyBcMeqPNROTo2KaR3ZgPeHuNk_Fc5SnVs8"

genai.configure(api_key=GEMINI_API_KEY)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def parse_text(text):
    result = {"bank": "", "amount": "", "store": "", "card": ""}

    if "Richart" in text:
        result["bank"] = "台新"
        m = re.search(r'約NT\$([\d,]+)', text)
        if m: result["amount"] = m.group(1).replace(",", "")
        m = re.search(r'卡號末四碼：(\d+)', text)
        if m: result["card"] = m.group(1)

    elif "信用卡交易通知" in text and "商店名稱" in text:
        result["bank"] = "聯邦"
        m = re.search(r'NT\$\s*([\d,]+)', text)
        if m: result["amount"] = m.group(1).replace(",", "")
        m = re.search(r'商店名稱\s*(.+)', text)
        if m: result["store"] = m.group(1).strip()
        m = re.search(r'交易卡號末四碼\s*(\d+)', text)
        if m: result["card"] = m.group(1)

    elif "信用卡付款" in text:
        result["bank"] = "富邦"
        m = re.search(r'NT\$\s*([\d,]+)', text)
        if m: result["amount"] = m.group(1).replace(",", "")
        m = re.search(r'商店名稱\s*(.+)', text)
        if m: result["store"] = m.group(1).strip()
        m = re.search(r'卡號末四碼\s*(\d+)', text)
        if m: result["card"] = m.group(1)

    return result

def analyze_image(image_data):
    model = genai.GenerativeModel("gemini-1.5-flash")
    image = Image.open(io.BytesIO(image_data))
    
    prompt = """這是一張銀行刷卡通知截圖，請提取以下資訊並以JSON格式回覆：
{
  "bank": "銀行名稱（台新/聯邦/富邦/其他）",
  "amount": "金額數字（只要數字，不要NT$符號和逗號）",
  "store": "商店名稱（沒有的話留空字串）",
  "card": "卡號末四碼（沒有的話留空字串）"
}
只回覆JSON，不要其他文字。"""

    response = model.generate_content([prompt, image])
    raw = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(raw)

@app.route("/webhook", methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return 'OK', 200
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception:
        pass
    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    text = event.message.text
    data = parse_text(text)

    if data["amount"]:
        requests.post(SHEET_URL, json=data)
        reply = f"✅ 記帳成功！\n🏦 {data['bank']}\n💰 NT${data['amount']}\n🏪 {data['store'] or '未知商店'}\n💳 末四碼：{data['card']}"
    else:
        reply = "⚠️ 無法辨識格式"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    image_data = b''.join(chunk for chunk in message_content.iter_content())

    try:
        data = analyze_image(image_data)
        if data.get("amount"):
            requests.post(SHEET_URL, json=data)
            reply = f"✅ 記帳成功！\n🏦 {data.get('bank', '未知')}\n💰 NT${data['amount']}\n🏪 {data.get('store') or '未知商店'}\n💳 末四碼：{data.get('card', '')}"
        else:
            reply = "⚠️ 圖片中找不到金額，請確認是刷卡通知截圖"
    except Exception:
        reply = "⚠️ 圖片辨識失敗，請重試"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(port=5000)
