import os
import time
import json
import uuid
import requests
import subprocess
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
MIN_PROFIT_USD = 0.5                    # نصف دولار كحد أدنى
TAKER_FEE_PERCENT = 0.001               # 0.1% رسوم السوق

# ---- إعدادات البروكسي ----
# تم تعطيل البروكسي لضمان استقرار الاتصال بشبكة Testnet أثناء الاختبار
USE_PROXY = False                        
PROXY_LIST = []
client = None

# ================= إعدادات إعادة المحاولة =================
MAX_RETRIES = 3                         # الحد الأقصى لإعادة المحاولة لكل بروكسي
RETRY_DELAY_SECONDS = 5                 # التأخير بين المحاولات
PROXY_ROTATION_DELAY = 10               # التأخير عند تبديل البروكسي

# ================= جلب البروكسيات المجانية =================

def fetch_free_proxies():
    """جلب بروكسيات مجانية من مصادر عامة."""
    proxies = []
    sources = [
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]

    print("🔍 جاري جلب قائمة البروكسيات المجانية...")

    for source in sources:
        try:
            response = requests.get(source, timeout=15)
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line and len(line) < 30:
                        proxy_url = f"http://{line}"
                        if proxy_url not in proxies:
                            proxies.append(proxy_url)
                print(f"  ✅ {source.split('/')[2]}: {len(lines)} بروكسي")
        except Exception as e:
            print(f"  ❌ فشل جلب {source}: {e}")

    proxies = list(dict.fromkeys(proxies))[:100]
    print(f"📊 إجمالي بروكسيات فريدة: {len(proxies)}")
    return proxies

def test_proxy(proxy_url):
    """اختبار البروكسي مع شبكة Binance Testnet"""
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        start = time.time()
        # تم تعديل الرابط ليتوافق مع Testnet الوهمية
        response = requests.get(
            "https://testnet.binance.vision/api/v3/ping",
            proxies=proxies,
            timeout=8
        )
        latency = time.time() - start
        if response.status_code == 200:
            return latency
        return None
    except:
        return None

def get_best_proxy():
    """اختبار البروكسيات وإرجاع الأفضل"""
    global PROXY_LIST

    if not PROXY_LIST:
        PROXY_LIST = fetch_free_proxies()

    if not PROXY_LIST:
        return None

    print("⚡ جاري اختبار سرعة البروكسيات...")
    working = []

    for proxy in PROXY_LIST[:20]:
        latency = test_proxy(proxy)
        if latency:
            working.append((proxy, latency))
            print(f"  ✅ {proxy.split('@')[-1] if '@' in proxy else proxy} - {latency:.2f}s")
        else:
            print(f"  ❌ فاشل")

    if working:
        working.sort(key=lambda x: x[1])
        best = working[0][0]
        print(f"🏆 أفضل بروكسي: {best.split('@')[-1] if '@' in best else best} ({working[0][1]:.2f}s)")
        return {"http": best, "https": best}

    print("❌ لا يوجد بروكسي يعمل!")
    return None

def init_client():
    """تهيئة عميل Binance لشبكة Testnet"""
    global client, PROXY_LIST

    print("🚀 بدء تهيئة الاتصال بشبكة Binance Testnet...")

    while True:
        proxy = get_best_proxy() if USE_PROXY else None

        if not USE_PROXY or proxy:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    if proxy:
                        session = requests.Session()
                        session.proxies = proxy
                        # إضافة testnet=True هنا
                        client = Client(API_KEY, API_SECRET, testnet=True, requests_params={"proxies": proxy})
                    else:
                        # إضافة testnet=True هنا
                        client = Client(API_KEY, API_SECRET, testnet=True)

                    client.ping()
                    print(f"✅ الاتصال بـ Binance Testnet ناجح! (بروكسي: {proxy['http'] if proxy else 'بدون بروكسي'})")
                    return True

                except Exception as e:
                    print(f"  ⚠️ فشل الاتصال (محاولة {attempt}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES:
                        print(f"  ⏳ إعادة المحاولة بعد {RETRY_DELAY_SECONDS} ثواني...")
                        time.sleep(RETRY_DELAY_SECONDS)
                    else:
                        print(f"  ❌ فشلت الـ {MAX_RETRIES} محاولات بهذا البروكسي.")
        else:
            print("❌ لا يوجد بروكسي يعمل حالياً.")

        print("🔄 جلب بروكسيات جديدة والمحاولة مرة أخرى...")
        PROXY_LIST = []
        time.sleep(PROXY_ROTATION_DELAY)

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
            else:
                print(f"  ⚠️ Telegram محاولة {attempt} فشلت: HTTP {response.status_code}")
        except Exception as e:
            print(f"  ⚠️ Telegram محاولة {attempt} فشلت: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(3)
        else:
            print(f"  ❌ فشل إرسال Telegram بعد {MAX_RETRIES} محاولات. سيتم التخطي.")

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
        except Exception as e:
            print(f"  ⚠️ Git محاولة {attempt} فشلت: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
            else:
                print(f"  ❌ فشل Git بعد {MAX_RETRIES} محاولات. سيتم التخطي.")
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
            print(f"  ⚠️ فشل جلب الأسعار (محاولة {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  ⏳ إعادة المحاولة بعد {RETRY_DELAY_SECONDS} ثواني...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  ❌ فشل جلب الأسعار بعد {MAX_RETRIES} محاولات. سيتم التخطي.")
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
                        pass # التجاهل إذا لم يكن BNB متوفراً في Testnet

            actual_price = total_cost / total_qty if total_qty > 0 else current_price
            return order, total_fee, total_qty, actual_price, total_cost

        except Exception as e:
            print(f"  ⚠️ فشل الشراء (محاولة {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  ⏳ إعادة المحاولة بعد {RETRY_DELAY_SECONDS} ثواني...")
                send_telegram_message(f"⚠️ فشل شراء (محاولة {attempt}/{MAX_RETRIES})، إعادة المحاولة...\nالخطأ: {str(e)[:100]}")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  ❌ فشل الشراء بعد {MAX_RETRIES} محاولات. سيتم التخطي.")
                send_telegram_message(f"❌ <b>فشل الشراء بعد {MAX_RETRIES} محاولات!</b>\nالخطأ: {str(e)[:200]}\nسيتم التخطي والانتقال للدورة التالية.")
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
            print(f"  ⚠️ فشل البيع (محاولة {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  ⏳ إعادة المحاولة بعد {RETRY_DELAY_SECONDS} ثواني...")
                send_telegram_message(f"⚠️ فشل بيع (محاولة {attempt}/{MAX_RETRIES})، إعادة المحاولة...\nالخطأ: {str(e)[:100]}")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  ❌ فشل البيع بعد {MAX_RETRIES} محاولات. سيتم التخطي.")
                send_telegram_message(f"❌ <b>فشل البيع بعد {MAX_RETRIES} محاولات!</b>\nالخطأ: {str(e)[:200]}\nسيتم الاحتفاظ بالمركز للدورة التالية.")
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
                    f"📈 نسبة: <code>{(actual_profit/total_cost)*100:.2f}%</code>\n\n"
                    f"✅ <b>لم يتم البيع بخسارة!</b>"
                )
                send_telegram_message(msg)
            else:
                print(f"     ⚠️ فشل البيع بعد {MAX_RETRIES} محاولات. الاحتفاظ بالمركز.")
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
        f"🔄 الحد الأقصى لإعادة المحاولة: {MAX_RETRIES}\n"
        f"🛡 <b>لا بيع بخسارة أبداً!</b>"
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
                print(f"⏳ الحد اليومي ({MAX_BUYS_PER_DAY})")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            diff = price_1h_ago - current_price
            print(f"📊 الحالي: {current_price:.2f} | قبل ساعة: {price_1h_ago:.2f} | الفارق: {diff:.2f}")

            if diff >= PRICE_DROP_THRESHOLD:
                print(f"🎯 هبوط {diff:.2f}$! شراء...")

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
            error = f"⚠️ خطأ: {str(e)[:200]}"
            print(error)
            send_telegram_message(error)

            if "IP" in str(e) or "banned" in str(e).lower() or "connection" in str(e).lower():
                print("🔄 إعادة تهيئة الاتصال...")
                time.sleep(5)
                init_client()

        elapsed = time.time() - loop_start
        sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
        time.sleep(sleep_time)

    send_telegram_message("🛑 انتهت الـ 6 ساعات.")

if __name__ == "__main__":
    main()
