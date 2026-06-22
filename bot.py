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
BUY_AMOUNT_USD = 10.0
PRICE_DROP_THRESHOLD = 80.0
MAX_BUYS_PER_DAY = 7
RUN_DURATION_HOURS = 6
SLEEP_INTERVAL_MINUTES = 1
JSON_FILE = 'sh.json'

# ---- إعدادات الربح ----
MIN_PROFIT_USD = 0.05                    
TAKER_FEE_PERCENT = 0.001               

# ---- إعدادات البروكسي ----
# تم تفعيله إجبارياً لأن خوادم GitHub Actions في أمريكا وباينانس تحظرها
USE_PROXY = True                        
PROXY_LIST = []
client = None

# ================= إعدادات إعادة المحاولة =================
MAX_RETRIES = 3                         
RETRY_DELAY_SECONDS = 2                 

# ================= جلب واختبار البروكسيات =================

def fetch_free_proxies():
    """جلب بروكسيات مجانية والتركيز على الدول المسموح بها في باينانس (مثل أوروبا)"""
    proxies = []
    sources = [
        # جلب بروكسيات من دول أوروبية لتجنب الحظر الأمريكي
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
    """اختبار البروكسي مع شبكة Binance Testnet وتخطي المحظور"""
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        start = time.time()
        # فحص استجابة باينانس المباشرة (إذا كان بروكسي أمريكي سيعطي خطأ ولن يعود بـ 200)
        response = requests.get(
            "https://testnet.binance.vision/api/v3/ping",
            proxies=proxies,
            timeout=2
        )
        if response.status_code == 200:
            return time.time() - start
        return None
    except:
        return None

def get_working_proxy():
    """استخدام تقنية المسارات المتوازية لفحص عشرات البروكسيات في نفس اللحظة للسرعة"""
    global PROXY_LIST

    if not PROXY_LIST:
        PROXY_LIST = fetch_free_proxies()

    print(f"⚡ جاري فحص سرعة {len(PROXY_LIST)} بروكسيات بالتوازي...")
    
    # فحص 20 بروكسي في نفس الوقت بدلاً من واحد تلو الآخر
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {executor.submit(test_proxy, p): p for p in PROXY_LIST}
        for future in concurrent.futures.as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            latency = future.result()
            
            if latency:
                print(f"🏆 تم العثور على بروكسي ممتاز: {proxy.split('@')[-1] if '@' in proxy else proxy} (السرعة: {latency:.2f}ث)")
                return {"http": proxy, "https": proxy}
            else:
                if proxy in PROXY_LIST:
                    PROXY_LIST.remove(proxy)
                    
    return None

def init_client():
    """تهيئة عميل Binance وضمان تجاوز حظر الموقع الجغرافي"""
    global client, PROXY_LIST

    print("🚀 بدء تهيئة الاتصال بشبكة Binance Testnet...")

    while True:
        proxy = get_working_proxy()
        
        if proxy:
            try:
                print("🔄 جاري محاولة تسجيل الدخول الفعلي وتخطي الحظر الجغرافي...")
                client = Client(API_KEY, API_SECRET, testnet=True, requests_params={"proxies": proxy})
                
                # فحص قوي: محاولة جلب بيانات الحساب للتأكد من أن البروكسي مسموح به تماماً
                client.get_account()
                
                print(f"✅ الاتصال وتسجيل الدخول بـ Binance Testnet ناجح! (البروكسي: {proxy['http']})")
                return True

            except BinanceAPIException as e:
                print(f"  ⚠️ رفضت باينانس هذا البروكسي (السبب: {e}) - جاري حذفه وتجربة غيره.")
                if proxy['http'] in PROXY_LIST:
                    PROXY_LIST.remove(proxy['http'])
            except Exception as e:
                print(f"  ⚠️ البروكسي ضعيف أو انقطع الاتصال - جاري حذفه.")
                if proxy['http'] in PROXY_LIST:
                    PROXY_LIST.remove(proxy['http'])
        else:
            print("🔄 القائمة نفدت. جاري جلب بروكسيات جديدة...")
            PROXY_LIST = []
            time.sleep(3)

# ================= إشعارات التليجرام =================

def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

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

# ================= إدارة الملفات =================

def load_history():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                pass
    return {"operations": {}, "open_positions": []}

def save_history(history):
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)

def git_commit_and_push():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            subprocess.run(['git', 'config', '--global', 'user.name', 'Bot'], check=True)
            subprocess.run(['git', 'config', '--global', 'user.email', 'bot@bot.com'], check=True)
            subprocess.run(['git', 'add', JSON_FILE], check=True)
            status = subprocess.run(['git', 'diff', '--staged', '--quiet'])
            if status.returncode != 0:
                subprocess.run(['git', 'commit', '-m', 'update'], check=True)
                subprocess.run(['git', 'push'], check=True)
            return True
        except Exception:
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

# ================= عمليات السوق =================

def get_prices():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            current = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1HOUR, limit=2)
            past = float(klines[0][4])
            return current, past
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return None, None
    return None, None

def execute_buy():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            current_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            order = client.order_market_buy(symbol=SYMBOL, quoteOrderQty=BUY_AMOUNT_USD)

            fills = order.get('fills', [])
            total_fee = 0.0
            total_qty = 0.0
            total_cost = 0.0

            for fill in fills:
                fee = float(fill['commission'])
                fee_asset = fill['commissionAsset']
                qty = float(fill['qty'])
                price = float(fill['price'])

                total_qty += qty
                total_cost += qty * price

                if fee_asset == 'USDT':
                    total_fee += fee
                elif fee_asset == 'BTC':
                    total_fee += fee * current_price
                elif fee_asset == 'BNB':
                    try:
                        bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                        total_fee += fee * bnb
                    except:
                        pass 

            actual_price = total_cost / total_qty if total_qty > 0 else current_price
            return order, total_fee, total_qty, actual_price, total_cost

        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                send_telegram_message(f"❌ <b>فشل الشراء بعد محاولات!</b>\nالخطأ: {str(e)[:200]}")
                return None, 0, 0, 0, 0

    return None, 0, 0, 0, 0

def execute_sell(qty):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            info = client.get_symbol_info(SYMBOL)
            step = float([f for f in info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
            prec = len(str(step).split('.')[-1].rstrip('0')) if '.' in str(step) else 0
            qty = round(qty - (qty % step), prec)

            if qty <= 0:
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
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                return None, 0, 0, 0
    return None, 0, 0, 0

# ================= فحص وبيع المراكز =================

def check_and_sell(history, current_price):
    positions = history.get("open_positions", [])
    if not positions:
        return False, history

    remaining = []
    sold = False

    for pos in positions:
        pos_id = pos['id']
        buy_price = pos['buy_price']
        qty = pos['qty']
        buy_fee = pos['buy_fee_usd']
        break_even = pos['break_even_price']
        min_sell = pos['min_sell_price']
        total_cost = pos['total_cost']

        print(f"  📊 {pos_id}: شراء@{buy_price:.2f} | حالي@{current_price:.2f} | بيع@{min_sell:.2f}")

        if current_price < break_even:
            print(f"     ⛔ تحت التعادل ({break_even:.2f}) - انتظار")
            remaining.append(pos)
            continue

        if current_price >= min_sell:
            print(f"     🎯 ربح متحقق! جاري البيع...")

            order, received, sell_fee, sell_price = execute_sell(qty)

            if order:
                actual_profit = received - total_cost - buy_fee - sell_fee

                sold = True
                now = datetime.utcnow()
                sell_id = f"sell_{uuid.uuid4().hex[:8]}"

                history['operations'][sell_id] = {
                    "type": "sell",
                    "date": now.date().isoformat(),
                    "time": now.time().isoformat(),
                    "related_buy_id": pos_id,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "qty": qty,
                    "received_usd": round(received, 4),
                    "buy_fee_usd": round(buy_fee, 4),
                    "sell_fee_usd": round(sell_fee, 4),
                    "profit_usd": round(actual_profit, 4),
                    "profit_percent": round((actual_profit / total_cost) * 100, 3)
                }

                msg = (
                    f"✅ <b>تم البيع بربح! (TESTNET)</b>\n\n"
                    f"🆔 الشراء: <code>{pos_id}</code>\n"
                    f"💰 شراء بـ: <code>{buy_price:.2f}</code>\n"
                    f"💵 بيع بـ: <code>{sell_price:.2f}</code>\n"
                    f"📊 كمية: <code>{qty:.6f} BTC</code>\n"
                    f"💸 تكلفة: <code>{total_cost:.2f}</code>\n"
                    f"💵 استلم: <code>{received:.2f}</code>\n"
                    f"📉 رسوم شراء: <code>{buy_fee:.4f}</code>\n"
                    f"📉 رسوم بيع: <code>{sell_fee:.4f}</code>\n"
                    f"💚 <b>ربح صافي: {actual_profit:.4f} USDT</b>\n"
                    f"📈 نسبة: <code>{(actual_profit/total_cost)*100:.2f}%</code>"
                )
                send_telegram_message(msg)
            else:
                remaining.append(pos)
        else:
            remaining.append(pos)

    history['open_positions'] = remaining
    return sold, history

# ================= الدالة الرئيسية =================

def main():
    if not API_KEY or not API_SECRET:
        print("❌ لا توجد مفاتيح API!")
        return

    print("🚀 بدء السكربت على بيئة التجربة (Testnet)...")
    init_client()

    start_time = time.time()
    end_time = start_time + (RUN_DURATION_HOURS * 3600)

    send_telegram_message(
        f"🚀 <b>السكربت يعمل الآن على الشبكة الوهمية Testnet!</b>\n"
        f"⏱ المدة: {RUN_DURATION_HOURS} ساعات\n"
        f"💰 الحد الأدنى للربح: {MIN_PROFIT_USD} USDT\n"
        f"🛡 <b>لا بيع بخسارة أبداً!</b>\n"
        f"🌐 <b>تم تفعيل بروكسي لتجاوز حظر GitHub Actions.</b>"
    )

    while time.time() < end_time:
        loop_start = time.time()

        try:
            history = load_history()
            current_price, price_1h_ago = get_prices()

            if current_price is None or price_1h_ago is None:
                print("⏳ تخطي الدورة الحالية بسبب فشل جلب الأسعار...")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            sold, history = check_and_sell(history, current_price)
            if sold:
                save_history(history)
                git_commit_and_push()
                history = load_history()

            today = datetime.utcnow().date().isoformat()
            todays_buys = sum(1 for d in history.get('operations', {}).values() 
                            if d.get('date') == today and d.get('type') == 'buy')

            if todays_buys >= MAX_BUYS_PER_DAY:
                print(f"⏳ الحد اليومي للمشتريات ({MAX_BUYS_PER_DAY}) تم استنفاده.")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            diff = price_1h_ago - current_price
            print(f"📊 الحالي: {current_price:.2f} | قبل ساعة: {price_1h_ago:.2f} | الفارق: {diff:.2f}")

            if diff >= PRICE_DROP_THRESHOLD:
                print(f"🎯 هبوط {diff:.2f}$! جاري الشراء...")

                order, fee, qty, actual_price, total_cost = execute_buy()

                if order is None or qty <= 0:
                    print("⏳ تخطي الشراء بسبب الفشل...")
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                    time.sleep(sleep_time)
                    continue

                calc = calculate_sell_thresholds(actual_price, qty, fee)
                op_id = f"buy_{uuid.uuid4().hex[:8]}"
                now = datetime.utcnow()

                buy_data = {
                    "type": "buy",
                    "date": now.date().isoformat(),
                    "time": now.time().isoformat(),
                    "buy_price": round(actual_price, 2),
                    "qty": round(qty, 8),
                    "buy_amount_usd": BUY_AMOUNT_USD,
                    "buy_fee_usd": round(fee, 4),
                    "total_cost": round(calc['total_cost'], 4),
                    "break_even_price": round(calc['break_even_price'], 2),
                    "min_sell_price": round(calc['min_sell_price'], 2)
                }

                history['operations'][op_id] = buy_data

                if 'open_positions' not in history:
                    history['open_positions'] = []

                history['open_positions'].append({
                    "id": op_id,
                    "buy_price": actual_price,
                    "qty": qty,
                    "buy_fee_usd": fee,
                    "total_cost": calc['total_cost'],
                    "break_even_price": calc['break_even_price'],
                    "min_sell_price": calc['min_sell_price'],
                    "date": now.date().isoformat(),
                    "time": now.time().isoformat()
                })

                save_history(history)
                git_commit_and_push()

                msg = (
                    f"✅ <b>تم الشراء! (TESTNET)</b>\n\n"
                    f"🆔 <code>{op_id}</code>\n"
                    f"💰 سعر: <code>{actual_price:.2f}</code>\n"
                    f"📊 كمية: <code>{qty:.6f} BTC</code>\n"
                    f"💸 رسوم: <code>{fee:.4f}</code>\n"
                    f"💵 تكلفة: <code>{calc['total_cost']:.2f}</code>\n"
                    f"⚖️ تعادل: <code>{calc['break_even_price']:.2f}</code>\n"
                    f"🎯 بيع عند: <code>{calc['min_sell_price']:.2f}</code>\n"
                    f"💚 ربح أدنى: <code>{MIN_PROFIT_USD} USDT</code>"
                )
                send_telegram_message(msg)

        except Exception as e:
            error_str = str(e)
            print(f"⚠️ خطأ أثناء دورة العمل: {error_str[:200]}")
            
            # إذا تعطل البروكسي فجأة أثناء التداول، نقوم بجلبه مرة أخرى
            if "connection" in error_str.lower() or "proxy" in error_str.lower() or "read" in error_str.lower():
                print("🔄 فقدان الاتصال بالبروكسي. إعادة التهيئة...")
                init_client()

        elapsed = time.time() - loop_start
        sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
        time.sleep(sleep_time)

    send_telegram_message("🛑 انتهت الـ 6 ساعات للسكربت.")

if __name__ == "__main__":
    main()
