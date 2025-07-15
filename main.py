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

# بيانات الحساب
API_KEY = "3538bf2b3821422baebb7918d33ec7ab"
API_SECRET = "ef2b4b2ec004c96e5c85127e99c10a14a33df9d8fe14a1a52a1095471f03a58c"
BASE_URL = "https://api.gateio.ws"
SYMBOL = "PEPE_USDT"
AMOUNT = "5"  # شراء بـ 5 دولار

# حالة الصفقة
position_open = False

# إبقاء البوت شغال على Replit
app = Flask('')


@app.route('/')
def home():
    return "✅ Bot is alive."


def run():
    app.run(host='0.0.0.0', port=8080)


# توليد التوقيع
def generate_signature(secret, method, url_path, query_string='', body=''):
    hashed_payload = hashlib.sha512(body.encode('utf-8')).hexdigest()
    timestamp = str(int(time.time()))
    sign_string = f"{method}\n{url_path}\n{query_string}\n{hashed_payload}\n{timestamp}"
    signature = hmac.new(secret.encode(), sign_string.encode(),
                         hashlib.sha512).hexdigest()
    return signature, timestamp


# تنفيذ أمر شراء أو بيع
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
    signature, timestamp = generate_signature(API_SECRET, method, url_path, '',
                                              body)

    headers = {
        "KEY": API_KEY,
        "SIGN": signature,
        "Timestamp": timestamp,
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, data=body, verify=False)
    result = response.json()

    if "status" in result and result["status"] == "closed":
        print(
            f"✅ الصفقة ({side}) تمت: {result['filled_amount']} بسعر {result['avg_deal_price']}"
        )
        return True
    else:
        print(f"❌ فشل في تنفيذ الصفقة ({side}): {result}")
        return False


# جلب رصيد PEPE
def get_balance():
    url_path = "/api/v4/spot/accounts"
    method = "GET"
    body = ''
    signature, timestamp = generate_signature(API_SECRET, method, url_path, '',
                                              body)

    headers = {"KEY": API_KEY, "SIGN": signature, "Timestamp": timestamp}
    url = BASE_URL + url_path
    response = requests.get(url, headers=headers, verify=False)
    accounts = response.json()

    for acc in accounts:
        if acc['currency'] == 'PEPE':
            return acc['available']
    return "0"


# جلب بيانات الشموع
def get_ohlcv():
    url = f"https://api.gateio.ws/api/v4/spot/candlesticks"
    params = {"currency_pair": SYMBOL, "interval": "5m", "limit": 100}
    response = requests.get(url, params=params, verify=False)
    data = response.json()
    df = pd.DataFrame(data,
                      columns=[
                          "timestamp", "volume", "close", "high", "low",
                          "open", "ignore1", "ignore2"
                      ])
    df = df[["timestamp", "open", "high", "low", "close",
             "volume"]].astype(float)
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# استراتيجية تقاطع EMA
def get_ema_signal(df):
    df["ema10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # إشارة شراء: تقاطع ema10 صعودًا فوق ema20
    if prev["ema10"] < prev["ema20"] and last["ema10"] > last["ema20"]:
        return "buy"
    # إشارة بيع: تقاطع ema10 هبوطًا تحت ema20
    elif prev["ema10"] > prev["ema20"] and last["ema10"] < last["ema20"]:
        return "sell"
    else:
        return "none"


# التشغيل الرئيسي
def main():
    global position_open
    print("📈 Gate.io EMA Cross Bot (PEPE/USDT) started...\n")
    while True:
        try:
            df = get_ohlcv()
            if df is None or df.empty:
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
            print(f"❌ حدث خطأ: {e}")

        print("⏳ تحديث خلال 7 ثانية...\n")
        time.sleep(7)


# التشغيل مع Flask في الخلفية
if __name__ == "__main__":
    Thread(target=run).start()
    main()
