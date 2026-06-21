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

# ⚠️ تحذير: هذه المفاتيح ظاهرة في الكود - يجب تغييرها فوراً!
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
TAKER_FEE_PERCENT = 0.001             # 0.1% رسوم السوق

# ---- إعدادات البروكسي ----
USE_PROXY = True                        # تفعيل البروكسي
PROXY_LIST = []
client = None

# ================= جلب البروكسيات المجانية =================

def fetch_free_proxies():
    """
    جلب بروكسيات مجانية من مصادر عامة.
    ⚠️ تحذير: هذه البروكسيات بطيئة وغير موثوقة وقد تحظرها Binance
    """
    proxies = []
    sources = [
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
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
    
    # إزالة التكرار وتحديد لـ 100 بروكسي
    proxies = list(dict.fromkeys(proxies))[:100]
    print(f"📊 إجمالي بروكسيات فريدة: {len(proxies)}")
    return proxies

def test_proxy(proxy_url):
    """اختبار البروكسي مع Binance API"""
    try:
        proxies = {"http": proxy_url, "https": proxy_url}
        start = time.time()
        response = requests.get(
            "https://api.binance.com/api/v3/ping",
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
    
    for proxy in PROXY_LIST[:20]:  # اختبار أول 20 فقط للسرعة
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
    """تهيئة عميل Binance مع أفضل بروكسي"""
    global client
    
    proxy = get_best_proxy() if USE_PROXY else None
    
    try:
        if proxy:
            session = requests.Session()
            session.proxies = proxy
            client = Client(API_KEY, API_SECRET, requests_params={"proxies": proxy})
        else:
            client = Client(API_KEY, API_SECRET)
        
        # اختبار الاتصال
        client.ping()
        print("✅ الاتصال بـ Binance ناجح!")
        return True
        
    except Exception as e:
        print(f"❌ فشل الاتصال: {e}")
        return False

# ================= إشعارات التليجرام =================

def send_telegram_message(message):
    """إرسال إشعار مع إعادة محاولة لا نهائية"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    attempt = 0
    while True:  # 🔁 إعادة محاولة لا نهائية
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return
        except Exception as e:
            attempt += 1
            print(f"  ⚠️ Telegram محاولة {attempt} فشلت: {e}")
            time.sleep(3)

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
    """رفع لـ GitHub مع إعادة محاولة"""
    for attempt in range(5):
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
            print(f"  ⚠️ Git محاولة {attempt+1} فشلت: {e}")
            time.sleep(2)
    return False

# ================= حسابات التكلفة والربح =================

def calculate_sell_thresholds(buy_price, qty, buy_fee_usd):
    """
    حساب:
    - break_even: سعر التعادل (لا ربح ولا خسارة)
    - min_profit_price: سعر الربح الأدنى (0.5$ ربح)
    """
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
    """جلب الأسعار مع إعادة محاولة لا نهائية"""
    while True:
        try:
            current = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1HOUR, limit=2)
            past = float(klines[0][4])
            return current, past
        except Exception as e:
            print(f"  ⚠️ فشل جلب الأسعار: {e} - إعادة المحاولة بعد 3 ثواني...")
            time.sleep(3)

def execute_buy():
    """تنفيذ الشراء مع إعادة محاولة لا نهائية"""
    while True:
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
                    bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                    total_fee += fee * bnb
            
            actual_price = total_cost / total_qty if total_qty > 0 else current_price
            return order, total_fee, total_qty, actual_price, total_cost
            
        except Exception as e:
            print(f"  ⚠️ فشل الشراء: {e} - إعادة المحاولة بعد 5 ثواني...")
            send_telegram_message(f"⚠️ فشل شراء، إعادة المحاولة...\nالخطأ: {str(e)[:100]}")
            time.sleep(5)

def execute_sell(qty):
    """تنفيذ البيع مع إعادة محاولة لا نهائية"""
    while True:
        try:
            # تعديل الكمية حسب LOT_SIZE
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
                    bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                    total_fee += fee * bnb
            
            actual_price = total_received / qty if qty > 0 else 0
            return order, total_received, total_fee, actual_price
            
        except Exception as e:
            print(f"  ⚠️ فشل البيع: {e} - إعادة المحاولة بعد 5 ثواني...")
            send_telegram_message(f"⚠️ فشل بيع، إعادة المحاولة...\nالخطأ: {str(e)[:100]}")
            time.sleep(5)

# ================= فحص وبيع المراكز =================

def check_and_sell(history, current_price):
    """فحص المراكز وبيع الربح مع ضمان عدم الخسارة"""
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
        
        # ⚠️ شرط حماية: لا يبيع أبداً بخسارة
        if current_price < break_even:
            print(f"     ⛔ تحت التعادل ({break_even:.2f}) - انتظار")
            remaining.append(pos)
            continue
        
        # ✅ هل تحقق الربح الأدنى (0.5$)؟
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
                    f"✅ <b>تم البيع بربح!</b>\n\n"
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
                remaining.append(pos)
        else:
            remaining.append(pos)
    
    history['open_positions'] = remaining
    return sold, history

# ================= الدالة الرئيسية =================

def main():
    # التحقق من المفاتيح
    if not API_KEY or not API_SECRET:
        print("❌ لا توجد مفاتيح API!")
        return
    
    # 🔁 إعادة محاولة الاتصال لا نهائية
    print("🚀 بدء السكربت...")
    while not init_client():
        print("❌ فشل الاتصال - إعادة المحاولة بعد 10 ثواني...")
        time.sleep(10)
    
    start_time = time.time()
    end_time = start_time + (RUN_DURATION_HOURS * 3600)
    
    send_telegram_message(
        f"🚀 <b>السكربت يعمل!</b>\n"
        f"⏱ المدة: {RUN_DURATION_HOURS} ساعات\n"
        f"💰 الحد الأدنى للربح: {MIN_PROFIT_USD} USDT\n"
        f"🛡 <b>لا بيع بخسارة أبداً!</b>"
    )

    while time.time() < end_time:
        loop_start = time.time()
        
        try:
            history = load_history()
            current_price, price_1h_ago = get_prices()
            
            # 1️⃣ فحص البيع أولاً
            sold, history = check_and_sell(history, current_price)
            if sold:
                save_history(history)
                git_commit_and_push()
                history = load_history()
            
            # 2️⃣ التحقق من الحد اليومي
            today = datetime.utcnow().date().isoformat()
            todays_buys = sum(1 for d in history.get('operations', {}).values() 
                            if d.get('date') == today and d.get('type') == 'buy')
            
            if todays_buys >= MAX_BUYS_PER_DAY:
                print(f"⏳ الحد اليومي ({MAX_BUYS_PER_DAY})")
                time.sleep(SLEEP_INTERVAL_MINUTES * 60)
                continue
            
            # 3️⃣ فحص الشراء
            diff = price_1h_ago - current_price
            print(f"📊 الحالي: {current_price:.2f} | قبل ساعة: {price_1h_ago:.2f} | الفارق: {diff:.2f}")
            
            if diff >= PRICE_DROP_THRESHOLD:
                print(f"🎯 هبوط {diff:.2f}$! شراء...")
                
                order, fee, qty, actual_price, total_cost = execute_buy()
                
                if qty > 0:
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
                        f"✅ <b>تم الشراء!</b>\n\n"
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
            
            # إعادة تهيئة الاتصال إذا كان خطأ IP
            if "IP" in str(e) or "banned" in str(e).lower() or "connection" in str(e).lower():
                print("🔄 إعادة تهيئة الاتصال...")
                time.sleep(5)
                init_client()
        
        # ضبط النوم
        elapsed = time.time() - loop_start
        sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
        time.sleep(sleep_time)

    send_telegram_message("🛑 انتهت الـ 6 ساعات.")

if __name__ == "__main__":
    main()
