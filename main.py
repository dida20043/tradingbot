import time
import requests
import hmac
import hashlib
import json
import pandas as pd
import urllib3
from flask import Flask
from threading import Thread

# تعطيل تحذيرات SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# إعدادات API و السوق
API_KEY = "3538bf2b3821422baebb7918d33ec7ab"
API_SECRET = "ef2b4b2ec004c96e5c85127e99c10a14a33df9d8fe14a1a52a1095471f03a58c"
BASE_URL = "https://api.gateio.ws"
SYMBOL = "PEPE_USDT"
AMOUNT = "5"
position_open = False

# سيرفر Flask لإبقاء البوت نشطًا
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running and healthy!"

# توليد توقيع API
def generate_signature(secret, method, url_path, query_string='', body=''):
    hashed_payload = hashlib.sha512(body.encode('utf-8')).hexdigest()
    timestamp = str(int(time.time()))
    sign_string = f"{method}\n{url_path}\n{query_string}\n{hashed_payload}\n{timestamp}"
    signature = hmac.new(secret.encode(), sign_string.encode(), hashlib.sha512).hexdigest()
    return signature, timestamp

# تنفيذ أوامر الشراء/البيع
def place_order(side):
    url_path = "/api/v4/spot/orders"
    url = BASE_URL + url_path
    method = "POST"

    order_data = {
        "currency_pair": SYMBOL,
        "type": "market",
        "side": side,
        "amount": AMOUNT if side == "buy" else get_balance(),
        "account": "spot",
        "time_in_force": "ioc"
    }

    body = json.dumps(order_data, separators=(',', ':'), sort_keys=True)
    signature, timestamp = generate_signature(API_SECRET, method, url_path, '', body)

    headers = {
        "KEY": API_KEY,
        "SIGN": signature,
        "Timestamp": timestamp,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=body, verify=False)
    result = response.json()

    if "status" in result and result["status"] == "closed":
        print(f"✅ الصفقة ({side}) تمت: {result['filled_amount']} بسعر {result['avg_deal_price']}")
        return True
    else:
        print(f"❌ فشل في تنفيذ الصفقة ({side}): {result}")
        return False

# جلب الرصيد
def get_balance():
    url_path = "/api/v4/spot/accounts"
    method = "GET"
    signature, timestamp = generate_signature(API_SECRET, method, url_path)
    headers = {"KEY": API_KEY, "SIGN": signature, "Timestamp": timestamp}
    url = BASE_URL + url_path
    response = requests.get(url, headers=headers, verify=False)
    for acc in response.json():
        if acc['currency'] == 'PEPE':
            return acc['available']
    return "0"

# جلب بيانات الشموع
def get_ohlcv():
    url = f"{BASE_URL}/api/v4/spot/candlesticks"
    params = {"currency_pair": SYMBOL, "interval": "5m", "limit": 100}
    response = requests.get(url, params=params, verify=False)
    data = response.json()
    df = pd.DataFrame(data, columns=["timestamp", "volume", "close", "high", "low", "open", "ignore1", "ignore2"])
    df = df[["timestamp", "open", "high", "low", "close", "volume"]].astype(float)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

# تحليل إشارة تقاطع EMA
def get_ema_signal(df):
    df["ema10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if prev["ema10"] < prev["ema20"] and last["ema10"] > last["ema20"]:
        return "buy"
    elif prev["ema10"] > prev["ema20"] and last["ema10"] < last["ema20"]:
        return "sell"
    else:
        return "none"

# الوظيفة الأساسية لتشغيل البوت
def run_bot():
    global position_open
    print("🚀 تشغيل بوت التداول (PEPE/USDT) عبر Gate.io...\n")
    while True:
        try:
            df = get_ohlcv()
            if df.empty:
                print("❌ لا توجد بيانات شموع.")
                time.sleep(60)
                continue

            signal = get_ema_signal(df)
            price = df["close"].iloc[-1]
            print(f"📉 السعر الحالي: {price}")
            print(f"📊 إشارة EMA: {signal}")

            if signal == "buy" and not position_open:
                print("🟢 تنفيذ صفقة شراء...")
                if place_order("buy"):
                    position_open = True

            elif signal == "sell" and position_open:
                print("🔴 تنفيذ صفقة بيع...")
                if place_order("sell"):
                    position_open = False

        except Exception as e:
            print(f"❌ حدث خطأ أثناء تنفيذ البوت: {e}")

        print("⏳ تحديث خلال 7 ثواني...\n")
        time.sleep(7)

# تشغيل البوت مع حماية تلقائية من التوقف
def start_bot_with_restart():
    while True:
        try:
            run_bot()
        except Exception as e:
            print(f"⚠️ البوت توقف بشكل غير متوقع: {e}")
            print("🔁 إعادة التشغيل خلال 10 ثواني...")
            time.sleep(10)

# بدء التشغيل (سيرفر + البوت)
Thread(target=start_bot_with_restart).start()
