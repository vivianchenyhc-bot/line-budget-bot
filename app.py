from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests, re

app = Flask(__name__)

CHANNEL_SECRET = "4f5d5dcb18c8002bf86eddc20b90f256"
CHANNEL_ACCESS_TOKEN = "GPL9lvUqlBA0IKDRFSAf0fiN9gJX035jQa7FsO8LsFJelISR4vEJAnI7BSeHWHArO9pSkWuKVf+0Fx4bzikxHuwZKWSPrKNcu6M5fwKYoZLw/TIEgbtpWUMicO5+1vo+qIIm+UB64B3GRT6HqYz2lAdB04t89/1O/w1cDnyilFU="
SHEET_URL = "https://script.google.com/macros/s/AKfycbyl8XUm35tvJbpHrNk9SIwDI1yXgc_37B08GleMdWeJb8ZI8irJMC9s2shyxYpbLbXw/exec"

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

def parse_message(text):
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

@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    data = parse_message(text)

    if data["amount"]:
        requests.post(SHEET_URL, json=data)
        reply = f"✅ 記帳成功！\n🏦 {data['bank']}\n💰 NT${data['amount']}\n🏪 {data['store'] or '未知商店'}\n💳 末四碼：{data['card']}"
    else:
        reply = "⚠️ 無法辨識格式，請確認是銀行刷卡通知"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(port=5000)
