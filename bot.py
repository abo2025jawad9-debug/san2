import os
import time
import json
import uuid
import requests
import subprocess
import concurrent.futures
from datetime import datetime
from dataclasses import dataclass
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ==========================================
# CONFIGURATION
# ==========================================

@dataclass
class Config:
    api_key: str = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'
    secret: str = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'
    telegram_token: str = '8777604170:AAGVQWj7KtRZWKjZQ0BuyIZCHJ3FCmFgQP4'
    telegram_chat_id: str = '6390985342'

cfg = Config()

# ================= إعدادات البوت =================
API_KEY = cfg.api_key
API_SECRET = cfg.secret
TELEGRAM_TOKEN = cfg.telegram_token
TELEGRAM_CHAT_ID = cfg.telegram_chat_id

SYMBOL = 'BTCUSDT'
BUY_AMOUNT_USD = 20.0
PRICE_DROP_THRESHOLD = 40.0
MAX_BUYS_PER_DAY = 7
RUN_DURATION_HOURS = 6
SLEEP_INTERVAL_MINUTES = 0.05
JSON_FILE = 'sh.json'

# ---- إعدادات الربح ----
MIN_PROFIT_USD = 0.001                    
TAKER_FEE_PERCENT = 0.001               

# ---- إعدادات البروكسي ----
USE_PROXY = True                        
PROXY_LIST = []
CURRENT_PROXY = None
client = None

# ================= إعدادات إعادة المحاولة =================
MAX_RETRIES = 3                         
RETRY_DELAY_SECONDS = 2                 

# ================= جلب واختبار البروكسيات =================

def fetch_free_proxies():
    proxies = []
    sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=de,fr,gb,nl,it,es,ch,se,no,dk,fi,pl&ssl=all&anonymity=elite,anonymous",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ]
    print("🔍 جاري جلب قائمة البروكسيات...")
    for source in sources:
        try:
            response = requests.get(source, timeout=10)
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line and len(line) < 30:
                        proxy_url = f"http://{line}"
                        if proxy_url not in proxies:
                            proxies.append(proxy_url)
        except Exception:
            pass
    proxies = list(dict.fromkeys(proxies))
    print(f"📊 إجمالي البروكسيات التي تم جلبها: {len(proxies)}")
    return proxies

def test_proxy(proxy_url):
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        start = time.time()
        response = requests.get("https://testnet.binance.vision/api/v3/ping", proxies=proxies, timeout=2)
        if response.status_code == 200:
            return time.time() - start
        return None
    except:
        return None

def get_working_proxy():
    global PROXY_LIST
    if not PROXY_LIST:
        PROXY_LIST = fetch_free_proxies()
    print(f"⚡ جاري فحص سرعة {len(PROXY_LIST)} بروكسيات بالتوازي...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {executor.submit(test_proxy, p): p for p in PROXY_LIST}
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            latency = future.result()
            if latency:
                print(f"🏆 تم العثور على بروكسي ممتاز: {proxy} (السرعة: {latency:.2f}ث)")
                return {"http": proxy, "https": proxy}
            else:
                if proxy in PROXY_LIST:
                    PROXY_LIST.remove(proxy)
    return None

def init_client():
    global client, PROXY_LIST, CURRENT_PROXY
    print("🚀 بدء تهيئة الاتصال بشبكة Binance Testnet...")
    while True:
        proxy = get_working_proxy()
        if proxy:
            try:
                print("🔄 جاري محاولة تسجيل الدخول الفعلي وتخطي الحظر الجغرافي...")
                client = Client(API_KEY, API_SECRET, testnet=True, requests_params={"proxies": proxy})
                client.get_account()
                CURRENT_PROXY = proxy
                print(f"✅ الاتصال وتسجيل الدخول ناجح! (البروكسي: {proxy['http']})")
                return True
            except BinanceAPIException as e:
                print(f"  ⚠️ رفضت باينانس البروكسي: {e}")
                if proxy['http'] in PROXY_LIST:
                    PROXY_LIST.remove(proxy['http'])
            except Exception:
                if proxy['http'] in PROXY_LIST:
                    PROXY_LIST.remove(proxy['http'])
        else:
            print("🔄 القائمة نفدت. إعادة جلب البروكسيات...")
            PROXY_LIST = []
            time.sleep(3)

# ================= إشعارات التليجرام =================

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        if attempt < MAX_RETRIES:
            time.sleep(3)
    return False

# ================= إدارة الملفات (الهيكلة الجديدة المستقرة) =================

def load_history():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                pass
    return {} # قاموس مسطح لحفظ العمليات بشكل مباشر ومستقل

def save_history(history):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

def git_commit_and_push():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            subprocess.run(['git', '--work-tree=' + os.getcwd(), 'config', '--global', 'user.name', 'Bot'], check=True)
            subprocess.run(['git', '--work-tree=' + os.getcwd(), 'config', '--global', 'user.email', 'bot@bot.com'], check=True)
            subprocess.run(['git', '--work-tree=' + os.getcwd(), 'add', JSON_FILE], check=True)
            status = subprocess.run(['git', '--work-tree=' + os.getcwd(), 'diff', '--staged', '--quiet'])
            if status.returncode != 0:
                subprocess.run(['git', '--work-tree=' + os.getcwd(), 'commit', '-m', 'تحديث عمليات التداول المفتوحة والمغلقة'], check=True)
                subprocess.run(['git', '--work-tree=' + os.getcwd(), 'push'], check=True)
            return True
        except Exception as e:
            print(f"⚠️ فشل تحديث Git: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
    return False

# ================= حسابات التكلفة والربح =================

def calculate_sell_thresholds(buy_price, qty, buy_fee_usd):
    buy_cost = buy_price * qty
    estimated_sell_fee = buy_cost * TAKER_FEE_PERCENT
    total_fees = buy_fee_usd + estimated_sell_fee
    total_cost = buy_cost + total_fees

    break_even = total_cost / qty
    min_profit_price = (total_cost + MIN_PROFIT_USD) / qty

    return {
        "buy_cost": buy_cost,
        "buy_fee_usd": buy_fee_usd,
        "estimated_sell_fee": estimated_sell_fee,
        "total_fees": total_fees,
        "total_cost": total_cost,
        "break_even_price": break_even,
        "min_sell_price": min_profit_price
    }

# ================= التحقق من السعر الحقيقي (مُصلح) =================

def get_real_price_direct():
    """جلب السعر مباشرة من Binance Testnet للتحقق - يحاول بدون بروكسي ثم مع البروكسي"""
    # محاولة 1: بدون بروكسي
    try:
        response = requests.get(
            "https://testnet.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
            timeout=5
        )
        if response.status_code == 200:
            return float(response.json()['price'])
    except Exception:
        pass

    # محاولة 2: مع البروكسي الحالي
    try:
        if CURRENT_PROXY:
            response = requests.get(
                "https://testnet.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
                proxies=CURRENT_PROXY,
                timeout=5
            )
            if response.status_code == 200:
                return float(response.json()['price'])
    except Exception:
        pass

    return None

def verify_proxy_price():
    """التحقق من السعر وإصلاح البروكسي إذا كان قديمًا"""
    global client, PROXY_LIST, CURRENT_PROXY

    # جلب السعر من البروكسي دائمًا (لا يفشل)
    try:
        bot_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
    except Exception as e:
        print(f"⚠️ فشل جلب سعر البروكسي: {e}")
        return None

    # محاولة التحقق من السعر الحقيقي
    real_price = get_real_price_direct()

    if real_price is not None:
        diff = abs(real_price - bot_price)
        print(f"🤖 سعر البروكسي: {bot_price:.2f} | 🌐 السعر الحقيقي: {real_price:.2f} | 📊 الفرق: {diff:.2f}")

        if diff > 5.0:
            print(f"❌ البروكسي قديم! الفرق {diff:.2f} > 5.0")
            send_telegram_message(f"⚠️ <b>البروكسي قديم!</b>\n🤖 سعر البروكسي: {bot_price:.2f}\n🌐 السعر الحقيقي: {real_price:.2f}\n📊 الفرق: {diff:.2f}\n🔄 جاري تغيير البروكسي...")
            init_client()
            return real_price
        else:
            print("✅ البروكسي متزامن")
            return bot_price
    else:
        # إذا فشل التحقق المباشر، استخدم سعر البروكسي على أي حال
        print(f"⚠️ لم يتم جلب السعر الحقيقي، استخدام سعر البروكسي: {bot_price:.2f}")
        return bot_price

# ================= عمليات السوق =================

def get_prices():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # التحقق من البروكسي - لا يُرجع None بسبب فشل التحقق المباشر
            current = verify_proxy_price()

            if current is None:
                print("⏳ فشل جلب السعر من البروكسي، إعادة المحاولة...")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECONDS)
                continue

            klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_5MINUTE, limit=2)
            past = float(klines[0][4])
            return current, past

        except Exception as e:
            print(f"⚠️ خطأ في get_prices (محاولة {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    return None, None

def execute_buy():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            current_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            order = client.order_market_buy(symbol=SYMBOL, quoteOrderQty=BUY_AMOUNT_USD)

            fills = order.get('fills', [])
            total_fee_usd = 0.0
            total_qty = 0.0
            total_cost = 0.0
            btc_fee = 0.0

            for fill in fills:
                fee = float(fill['commission'])
                fee_asset = fill['commissionAsset']
                qty = float(fill['qty'])
                price = float(fill['price'])

                total_qty += qty
                total_cost += qty * price

                if fee_asset == 'USDT':
                    total_fee_usd += fee
                elif fee_asset == 'BTC':
                    total_fee_usd += fee * current_price
                    btc_fee += fee
                elif fee_asset == 'BNB':
                    try:
                        bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                        total_fee_usd += fee * bnb
                    except:
                        pass 

            actual_price = total_cost / total_qty if total_qty > 0 else current_price
            sellable_qty = total_qty - btc_fee

            return order, total_fee_usd, total_qty, actual_price, total_cost, sellable_qty

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                send_telegram_message(f"❌ <b>فشل الشراء بعد محاولات!</b>\nالخطأ: {str(e)[:200]}")
                return None, 0, 0, 0, 0, 0
    return None, 0, 0, 0, 0, 0

def execute_sell(qty):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            info = client.get_symbol_info(SYMBOL)
            step = float([f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
            prec = len(str(step).split('.')[-1].rstrip('0')) if '.' in str(step) else 0
            qty = round(qty - (qty % step), prec)

            if qty <= 0:
                print("⚠️ كمية البيع المحسوبة بعد التقريب تساوي صفر أو أقل.")
                return None, 0, 0, 0

            order = client.order_market_sell(symbol=SYMBOL, quantity=qty)
            fills = order.get('fills', [])
            total_fee = 0.0
            total_received = 0.0

            for fill in fills:
                fee = float(fill['commission'])
                fee_asset = fill['commissionAsset']
                qty_f = float(fill['qty'])
                price = float(fill['price'])
                total_received += qty_f * price

                if fee_asset == 'USDT':
                    total_fee += fee
                elif fee_asset == 'BTC':
                    total_fee += fee * price
                elif fee_asset == 'BNB':
                    try:
                        bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                        total_fee += fee * bnb
                    except:
                        pass

            actual_price = total_received / qty if qty > 0 else 0
            return order, total_received, total_fee, actual_price

        except Exception as e:
            print(f"⚠️ فشل تنفيذ أمر البيع في المحاولة {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    return None, 0, 0, 0

# ================= الاستعلام والمقارنة والبيع الذكي المنفصل =================

def check_and_sell(history, current_price):
    sold_any = False

    for op_id in list(history.keys()):
        pos = history[op_id]

        if pos.get('status') != "معلقة - جاري الانتظار":
            continue

        buy_price = pos['buy_price']
        qty = pos.get('sellable_qty', pos['qty'])
        min_sell = pos['min_sell_price']
        total_cost = pos['total_cost']
        buy_fee = pos['buy_fee_usd']

        print(f"🔍 فحص العملية المستقلة [{op_id}]: شراء@{buy_price:.2f} | حالي@{current_price:.2f} | هدف البيع@{min_sell:.2f}")

        if current_price >= min_sell:
            print(f"🎯 السعر يتناسب مع العملية [{op_id}]! جاري تنفيذ أمر البيع...")

            order, received, sell_fee, sell_price = execute_sell(qty)

            if order:
                actual_profit = received - total_cost - sell_fee
                sold_any = True

                pos['status'] = "تم البيع"
                pos['sell_details'] = {
                    "sell_id": f"sell_{uuid.uuid4().hex[:8]}",
                    "sell_price": round(sell_price, 2),
                    "received_usd": round(received, 4),
                    "sell_fee_usd": round(sell_fee, 4),
                    "profit_usd": round(actual_profit, 4),
                    "profit_percent": round((actual_profit / total_cost) * 100, 3),
                    "sell_date": datetime.utcnow().date().isoformat(),
                    "sell_time": datetime.utcnow().time().isoformat()
                }

                msg = (
                    f"✅ <b>تم البيع بنجاح بربح! (TESTNET)</b>\n\n"
                    f"🆔 العملية المشحونة: <code>{op_id}</code>\n"
                    f"📊 الحالة الحالية: <b>تم البيع 💚</b>\n"
                    f"💰 سعر الشراء: <code>{buy_price:.2f}</code>\n"
                    f"💵 سعر البيع الفعلي: <code>{sell_price:.2f}</code>\n"
                    f"📊 كمية مبيعة: <code>{qty:.6f} BTC</code>\n"
                    f"💸 إجمالي التكلفة: <code>{total_cost:.2f}</code>\n"
                    f"💵 العائد الإجمالي: <code>{received:.2f}</code>\n"
                    f"📉 رسوم العملية كاملة: <code>{(buy_fee + sell_fee):.4f}</code>\n"
                    f"💚 <b>الربح الصافي المستلم: {actual_profit:.4f} USDT</b>\n"
                    f"📈 نسبة الربح الصافي: <code>{(actual_profit/total_cost)*100:.2f}%</code>"
                )
                send_telegram_message(msg)
            else:
                print(f"❌ فشل السكربت في تنفيذ عملية البيع للمعرف [{op_id}] على المنصة.")

    return sold_any, history

# ================= الدالة الرئيسية =================

def main():
    if not API_KEY or not API_SECRET:
        print("❌ لا توجد مفاتيح API!")
        return

    print("🚀 بدء السكربت المطور على بيئة التجربة (Testnet)...")
    init_client()

    start_time = time.time()
    end_time = start_time + (RUN_DURATION_HOURS * 3600)

    send_telegram_message(
        f"🚀 <b>البوت المطور يعمل الآن بكفاءة على الـ Testnet!</b>\n"
        f"⏱ مدة التشغيل: {RUN_DURATION_HOURS} ساعات\n"
        f"💰 مستهدف الربح الصافي: {MIN_PROFIT_USD} USDT لكل عملية منفصلة\n"
        f"⚙️ <b>تم تحديث نظام فرز ومقارنة العمليات داخل sh.json بنجاح وبشكل فريد.</b>"
    )

    while time.time() < end_time:
        loop_start = time.time()

        try:
            history = load_history()
            current_price, price_1h_ago = get_prices()

            if current_price is None or price_1h_ago is None:
                print("⏳ تخطي الدورة الحالية بسبب فشل مؤقت في جلب الأسعار...")
                time.sleep(10)
                continue

            sold, history = check_and_sell(history, current_price)
            if sold:
                save_history(history)
                git_commit_and_push()
                history = load_history()

            today = datetime.utcnow().date().isoformat()
            todays_buys = sum(1 for op in history.values() 
                              if isinstance(op, dict) and op.get('date') == today and op.get('type') == 'buy')

            if todays_buys >= MAX_BUYS_PER_DAY:
                print(f"⏳ تم استنفاد الحد الأقصى للمشتريات اليومية لهذا اليوم ({MAX_BUYS_PER_DAY}).")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            diff = price_1h_ago - current_price
            print(f"📊 السعر الحالي: {current_price:.2f} | قبل ساعة: {price_1h_ago:.2f} | الفارق الحالي: {diff:.2f}")

            if diff >= PRICE_DROP_THRESHOLD:
                print(f"🎯 هبوط مالي قدره {diff:.2f}$ محقق! جاري الشراء لإنشاء عملية جديدة...")

                order, fee, qty, actual_price, total_cost, sellable_qty = execute_buy()

                if order is None or qty <= 0:
                    print("⏳ تخطي عملية الشراء وتأجيلها بسبب فشل في الطلب...")
                    time.sleep(5)
                    continue

                calc = calculate_sell_thresholds(actual_price, qty, fee)
                op_id = f"buy_{uuid.uuid4().hex[:8]}"
                now = datetime.utcnow()

                buy_data = {
                    "type": "buy",
                    "status": "معلقة - جاري الانتظار",
                    "date": now.date().isoformat(),
                    "time": now.time().isoformat(),
                    "buy_price": round(actual_price, 2),
                    "qty": round(qty, 8),
                    "sellable_qty": round(sellable_qty, 8),
                    "buy_amount_usd": BUY_AMOUNT_USD,
                    "buy_fee_usd": round(fee, 4),
                    "total_cost": round(calc['total_cost'], 4),
                    "break_even_price": round(calc['break_even_price'], 2),
                    "min_sell_price": round(calc['min_sell_price'], 2),
                    "sell_details": {}
                }

                history[op_id] = buy_data
                save_history(history)
                git_commit_and_push()

                msg = (
                    f"✅ <b>تم إنشاء عملية شراء فريدة! (TESTNET)</b>\n\n"
                    f"🆔 المعرف الفريد للعملية: <code>{op_id}</code>\n"
                    f"📊 الحالة: <b>معلقة - جاري الانتظار ⏳</b>\n"
                    f"💰 سعر الدخول: <code>{actual_price:.2f}</code>\n"
                    f"📊 كمية الشراء الإجمالية: <code>{qty:.6f} BTC</code>\n"
                    f"📉 الكمية الصافية للبيع: <code>{sellable_qty:.6f} BTC</code>\n"
                    f"💵 تكلفة الصفقة شاملة: <code>{calc['total_cost']:.2f}</code>\n"
                    f"⚖️ سعر التعادل: <code>{calc['break_even_price']:.2f}</code>\n"
                    f"🎯 البيع المستهدف عند: <code>{calc['min_sell_price']:.2f}</code>\n"
                    f"💚 صافي ربح الصفقة: <code>{MIN_PROFIT_USD} USDT</code>"
                )
                send_telegram_message(msg)

        except Exception as e:
            error_str = str(e)
            print(f"⚠️ خطأ أثناء دورة العمل: {error_str[:200]}")
            if any(k in error_str.lower() for k in ["connection", "proxy", "read", "timeout"]):
                print("🔄 خطأ في اتصال البروكسي الحاسم، جاري تغيير البروكسي فوراً...")
                init_client()

        elapsed = time.time() - loop_start
        sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
        time.sleep(sleep_time)

    send_telegram_message("🛑 انتهت الـ 6 ساعات المحددة لدورة عمل السكربت الحالية.")

if __name__ == "__main__":
    main()

