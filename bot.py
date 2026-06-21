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

# 鈿狅笍 鬲丨匕賷乇: 賴匕賴 丕賱賲賮丕鬲賷丨 馗丕賴乇丞 賮賷 丕賱賰賵丿 - 賷噩亘 鬲睾賷賷乇賴丕 賮賵乇丕賸!
cfg = Config()

# ================= 廿毓丿丕丿丕鬲 丕賱亘賵鬲 =================
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

# ---- 廿毓丿丕丿丕鬲 丕賱乇亘丨 ----
MIN_PROFIT_USD = 0.5                    # 賳氐賮 丿賵賱丕乇 賰丨丿 兀丿賳賶
TAKER_FEE_PERCENT = 0.001             # 0.1% 乇爻賵賲 丕賱爻賵賯

# ---- 廿毓丿丕丿丕鬲 丕賱亘乇賵賰爻賷 ----
USE_PROXY = True                        # 鬲賮毓賷賱 丕賱亘乇賵賰爻賷
PROXY_LIST = []
client = None

# ================= 廿毓丿丕丿丕鬲 廿毓丕丿丞 丕賱賲丨丕賵賱丞 =================
MAX_RETRIES = 3                         # 丕賱丨丿 丕賱兀賯氐賶 賱廿毓丕丿丞 丕賱賲丨丕賵賱丞 賱賰賱 亘乇賵賰爻賷
RETRY_DELAY_SECONDS = 5                 # 丕賱鬲兀禺賷乇 亘賷賳 丕賱賲丨丕賵賱丕鬲
PROXY_ROTATION_DELAY = 10               # 丕賱鬲兀禺賷乇 毓賳丿 鬲亘丿賷賱 丕賱亘乇賵賰爻賷

# ================= 噩賱亘 丕賱亘乇賵賰爻賷丕鬲 丕賱賲噩丕賳賷丞 =================

def fetch_free_proxies():
    """
    噩賱亘 亘乇賵賰爻賷丕鬲 賲噩丕賳賷丞 賲賳 賲氐丕丿乇 毓丕賲丞.
    鈿狅笍 鬲丨匕賷乇: 賴匕賴 丕賱亘乇賵賰爻賷丕鬲 亘胤賷卅丞 賵睾賷乇 賲賵孬賵賯丞 賵賯丿 鬲丨馗乇賴丕 Binance
    """
    proxies = []
    sources = [
        "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&simplified=true",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]

    print("馃攳 噩丕乇賷 噩賱亘 賯丕卅賲丞 丕賱亘乇賵賰爻賷丕鬲 丕賱賲噩丕賳賷丞...")

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
                print(f"  鉁� {source.split('/')[2]}: {len(lines)} 亘乇賵賰爻賷")
        except Exception as e:
            print(f"  鉂� 賮卮賱 噩賱亘 {source}: {e}")

    # 廿夭丕賱丞 丕賱鬲賰乇丕乇 賵鬲丨丿賷丿 賱賭 100 亘乇賵賰爻賷
    proxies = list(dict.fromkeys(proxies))[:100]
    print(f"馃搳 廿噩賲丕賱賷 亘乇賵賰爻賷丕鬲 賮乇賷丿丞: {len(proxies)}")
    return proxies

def test_proxy(proxy_url):
    """丕禺鬲亘丕乇 丕賱亘乇賵賰爻賷 賲毓 Binance API"""
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
    """丕禺鬲亘丕乇 丕賱亘乇賵賰爻賷丕鬲 賵廿乇噩丕毓 丕賱兀賮囟賱"""
    global PROXY_LIST

    if not PROXY_LIST:
        PROXY_LIST = fetch_free_proxies()

    if not PROXY_LIST:
        return None

    print("鈿� 噩丕乇賷 丕禺鬲亘丕乇 爻乇毓丞 丕賱亘乇賵賰爻賷丕鬲...")
    working = []

    for proxy in PROXY_LIST[:20]:  # 丕禺鬲亘丕乇 兀賵賱 20 賮賯胤 賱賱爻乇毓丞
        latency = test_proxy(proxy)
        if latency:
            working.append((proxy, latency))
            print(f"  鉁� {proxy.split('@')[-1] if '@' in proxy else proxy} - {latency:.2f}s")
        else:
            print(f"  鉂� 賮丕卮賱")

    if working:
        working.sort(key=lambda x: x[1])
        best = working[0][0]
        print(f"馃弳 兀賮囟賱 亘乇賵賰爻賷: {best.split('@')[-1] if '@' in best else best} ({working[0][1]:.2f}s)")
        return {"http": best, "https": best}

    print("鉂� 賱丕 賷賵噩丿 亘乇賵賰爻賷 賷毓賲賱!")
    return None

def init_client():
    """
    鬲賴賷卅丞 毓賲賷賱 Binance 賲毓 兀賮囟賱 亘乇賵賰爻賷.
    廿匕丕 賮卮賱鬲 3 賲丨丕賵賱丕鬲 鈫� 賷噩賱亘 亘乇賵賰爻賷 噩丿賷丿 賵賷毓賷丿 丕賱賲丨丕賵賱丞 (賱丕 賳賴丕卅賷).
    """
    global client, PROXY_LIST

    print("馃殌 亘丿亍 鬲賴賷卅丞 丕賱丕鬲氐丕賱 亘賭 Binance...")

    while True:  # 馃攣 賱丕 賷鬲賵賯賮 兀亘丿丕賸 丨鬲賶 賷賳噩丨
        proxy = get_best_proxy() if USE_PROXY else None

        if not USE_PROXY or proxy:
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    if proxy:
                        session = requests.Session()
                        session.proxies = proxy
                        client = Client(API_KEY, API_SECRET, requests_params={"proxies": proxy})
                    else:
                        client = Client(API_KEY, API_SECRET)

                    # 丕禺鬲亘丕乇 丕賱丕鬲氐丕賱
                    client.ping()
                    print(f"鉁� 丕賱丕鬲氐丕賱 亘賭 Binance 賳丕噩丨! (亘乇賵賰爻賷: {proxy['http'] if proxy else '亘丿賵賳 亘乇賵賰爻賷'})")
                    return True

                except Exception as e:
                    print(f"  鈿狅笍 賮卮賱 丕賱丕鬲氐丕賱 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES}): {e}")
                    if attempt < MAX_RETRIES:
                        print(f"  鈴� 廿毓丕丿丞 丕賱賲丨丕賵賱丞 亘毓丿 {RETRY_DELAY_SECONDS} 孬賵丕賳賷...")
                        time.sleep(RETRY_DELAY_SECONDS)
                    else:
                        print(f"  鉂� 賮卮賱鬲 丕賱賭 {MAX_RETRIES} 賲丨丕賵賱丕鬲 亘賴匕丕 丕賱亘乇賵賰爻賷.")
        else:
            print("鉂� 賱丕 賷賵噩丿 亘乇賵賰爻賷 賷毓賲賱 丨丕賱賷丕賸.")

        # 馃攧 鬲亘丿賷賱 丕賱亘乇賵賰爻賷 - 賲爻丨 丕賱賯丕卅賲丞 賵噩賱亘 噩丿賷丿丞
        print("馃攧 噩賱亘 亘乇賵賰爻賷丕鬲 噩丿賷丿丞 賵丕賱賲丨丕賵賱丞 賲乇丞 兀禺乇賶...")
        PROXY_LIST = []  # 賲爻丨 丕賱賯丕卅賲丞 丕賱賯丿賷賲丞
        time.sleep(PROXY_ROTATION_DELAY)

# ================= 廿卮毓丕乇丕鬲 丕賱鬲賱賷噩乇丕賲 =================

def send_telegram_message(message):
    """廿乇爻丕賱 廿卮毓丕乇 賲毓 廿毓丕丿丞 賲丨丕賵賱丞 3 賲乇丕鬲 賮賯胤"""
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
                print(f"  鈿狅笍 Telegram 賲丨丕賵賱丞 {attempt} 賮卮賱鬲: HTTP {response.status_code}")
        except Exception as e:
            print(f"  鈿狅笍 Telegram 賲丨丕賵賱丞 {attempt} 賮卮賱鬲: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(3)
        else:
            print(f"  鉂� 賮卮賱 廿乇爻丕賱 Telegram 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 爻賷鬲賲 丕賱鬲禺胤賷.")

    return False

# ================= 廿丿丕乇丞 丕賱賲賱賮丕鬲 =================

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
    """乇賮毓 賱賭 GitHub 賲毓 廿毓丕丿丞 賲丨丕賵賱丞 3 賲乇丕鬲 賮賯胤"""
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
            print(f"  鈿狅笍 Git 賲丨丕賵賱丞 {attempt} 賮卮賱鬲: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2)
            else:
                print(f"  鉂� 賮卮賱 Git 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 爻賷鬲賲 丕賱鬲禺胤賷.")
    return False

# ================= 丨爻丕亘丕鬲 丕賱鬲賰賱賮丞 賵丕賱乇亘丨 =================

def calculate_sell_thresholds(buy_price, qty, buy_fee_usd):
    """
    丨爻丕亘:
    - break_even: 爻毓乇 丕賱鬲毓丕丿賱 (賱丕 乇亘丨 賵賱丕 禺爻丕乇丞)
    - min_profit_price: 爻毓乇 丕賱乇亘丨 丕賱兀丿賳賶 (0.5$ 乇亘丨)
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

# ================= 毓賲賱賷丕鬲 丕賱爻賵賯 =================

def get_prices():
    """噩賱亘 丕賱兀爻毓丕乇 賲毓 廿毓丕丿丞 賲丨丕賵賱丞 3 賲乇丕鬲 賮賯胤"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            current = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1HOUR, limit=2)
            past = float(klines[0][4])
            return current, past
        except Exception as e:
            print(f"  鈿狅笍 賮卮賱 噩賱亘 丕賱兀爻毓丕乇 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  鈴� 廿毓丕丿丞 丕賱賲丨丕賵賱丞 亘毓丿 {RETRY_DELAY_SECONDS} 孬賵丕賳賷...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  鉂� 賮卮賱 噩賱亘 丕賱兀爻毓丕乇 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 爻賷鬲賲 丕賱鬲禺胤賷.")
                return None, None
    return None, None

def execute_buy():
    """鬲賳賮賷匕 丕賱卮乇丕亍 賲毓 廿毓丕丿丞 賲丨丕賵賱丞 3 賲乇丕鬲 賮賯胤"""
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
                    bnb = float(client.get_symbol_ticker(symbol='BNBUSDT')['price'])
                    total_fee += fee * bnb

            actual_price = total_cost / total_qty if total_qty > 0 else current_price
            return order, total_fee, total_qty, actual_price, total_cost

        except Exception as e:
            print(f"  鈿狅笍 賮卮賱 丕賱卮乇丕亍 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  鈴� 廿毓丕丿丞 丕賱賲丨丕賵賱丞 亘毓丿 {RETRY_DELAY_SECONDS} 孬賵丕賳賷...")
                send_telegram_message(f"鈿狅笍 賮卮賱 卮乇丕亍 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES})貙 廿毓丕丿丞 丕賱賲丨丕賵賱丞...\n丕賱禺胤兀: {str(e)[:100]}")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  鉂� 賮卮賱 丕賱卮乇丕亍 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 爻賷鬲賲 丕賱鬲禺胤賷.")
                send_telegram_message(f"鉂� <b>賮卮賱 丕賱卮乇丕亍 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲!</b>\n丕賱禺胤兀: {str(e)[:200]}\n爻賷鬲賲 丕賱鬲禺胤賷 賵丕賱丕賳鬲賯丕賱 賱賱丿賵乇丞 丕賱鬲丕賱賷丞.")
                return None, 0, 0, 0, 0

    return None, 0, 0, 0, 0

def execute_sell(qty):
    """鬲賳賮賷匕 丕賱亘賷毓 賲毓 廿毓丕丿丞 賲丨丕賵賱丞 3 賲乇丕鬲 賮賯胤"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 鬲毓丿賷賱 丕賱賰賲賷丞 丨爻亘 LOT_SIZE
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
            print(f"  鈿狅笍 賮卮賱 丕賱亘賷毓 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                print(f"  鈴� 廿毓丕丿丞 丕賱賲丨丕賵賱丞 亘毓丿 {RETRY_DELAY_SECONDS} 孬賵丕賳賷...")
                send_telegram_message(f"鈿狅笍 賮卮賱 亘賷毓 (賲丨丕賵賱丞 {attempt}/{MAX_RETRIES})貙 廿毓丕丿丞 丕賱賲丨丕賵賱丞...\n丕賱禺胤兀: {str(e)[:100]}")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print(f"  鉂� 賮卮賱 丕賱亘賷毓 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 爻賷鬲賲 丕賱鬲禺胤賷.")
                send_telegram_message(f"鉂� <b>賮卮賱 丕賱亘賷毓 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲!</b>\n丕賱禺胤兀: {str(e)[:200]}\n爻賷鬲賲 丕賱丕丨鬲賮丕馗 亘丕賱賲乇賰夭 賱賱丿賵乇丞 丕賱鬲丕賱賷丞.")
                return None, 0, 0, 0

    return None, 0, 0, 0

# ================= 賮丨氐 賵亘賷毓 丕賱賲乇丕賰夭 =================

def check_and_sell(history, current_price):
    """賮丨氐 丕賱賲乇丕賰夭 賵亘賷毓 丕賱乇亘丨 賲毓 囟賲丕賳 毓丿賲 丕賱禺爻丕乇丞"""
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

        print(f"  馃搳 {pos_id}: 卮乇丕亍@{buy_price:.2f} | 丨丕賱賷@{current_price:.2f} | 亘賷毓@{min_sell:.2f}")

        # 鈿狅笍 卮乇胤 丨賲丕賷丞: 賱丕 賷亘賷毓 兀亘丿丕賸 亘禺爻丕乇丞
        if current_price < break_even:
            print(f"     鉀� 鬲丨鬲 丕賱鬲毓丕丿賱 ({break_even:.2f}) - 丕賳鬲馗丕乇")
            remaining.append(pos)
            continue

        # 鉁� 賴賱 鬲丨賯賯 丕賱乇亘丨 丕賱兀丿賳賶 (0.5$)責
        if current_price >= min_sell:
            print(f"     馃幆 乇亘丨 賲鬲丨賯賯! 噩丕乇賷 丕賱亘賷毓...")

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
                    f"鉁� <b>鬲賲 丕賱亘賷毓 亘乇亘丨!</b>\n\n"
                    f"馃啍 丕賱卮乇丕亍: <code>{pos_id}</code>\n"
                    f"馃挵 卮乇丕亍 亘賭: <code>{buy_price:.2f}</code>\n"
                    f"馃挼 亘賷毓 亘賭: <code>{sell_price:.2f}</code>\n"
                    f"馃搳 賰賲賷丞: <code>{qty:.6f} BTC</code>\n"
                    f"馃捀 鬲賰賱賮丞: <code>{total_cost:.2f}</code>\n"
                    f"馃挼 丕爻鬲賱賲: <code>{received:.2f}</code>\n"
                    f"馃搲 乇爻賵賲 卮乇丕亍: <code>{buy_fee:.4f}</code>\n"
                    f"馃搲 乇爻賵賲 亘賷毓: <code>{sell_fee:.4f}</code>\n"
                    f"馃挌 <b>乇亘丨 氐丕賮賷: {actual_profit:.4f} USDT</b>\n"
                    f"馃搱 賳爻亘丞: <code>{(actual_profit/total_cost)*100:.2f}%</code>\n\n"
                    f"鉁� <b>賱賲 賷鬲賲 丕賱亘賷毓 亘禺爻丕乇丞!</b>"
                )
                send_telegram_message(msg)
            else:
                # 賮卮賱 丕賱亘賷毓 亘毓丿 3 賲丨丕賵賱丕鬲 - 丕丨鬲賮馗 亘丕賱賲乇賰夭
                print(f"     鈿狅笍 賮卮賱 丕賱亘賷毓 亘毓丿 {MAX_RETRIES} 賲丨丕賵賱丕鬲. 丕賱丕丨鬲賮丕馗 亘丕賱賲乇賰夭.")
                remaining.append(pos)
        else:
            remaining.append(pos)

    history['open_positions'] = remaining
    return sold, history

# ================= 丕賱丿丕賱丞 丕賱乇卅賷爻賷丞 =================

def main():
    # 丕賱鬲丨賯賯 賲賳 丕賱賲賮丕鬲賷丨
    if not API_KEY or not API_SECRET:
        print("鉂� 賱丕 鬲賵噩丿 賲賮丕鬲賷丨 API!")
        return

    # 馃攣 廿毓丕丿丞 賲丨丕賵賱丞 丕賱丕鬲氐丕賱 賱丕 賳賴丕卅賷丞 賲毓 鬲亘丿賷賱 丕賱亘乇賵賰爻賷
    print("馃殌 亘丿亍 丕賱爻賰乇亘鬲...")
    init_client()  # 賱丕 賷鬲賵賯賮 兀亘丿丕賸 丨鬲賶 賷賳噩丨

    start_time = time.time()
    end_time = start_time + (RUN_DURATION_HOURS * 3600)

    send_telegram_message(
        f"馃殌 <b>丕賱爻賰乇亘鬲 賷毓賲賱!</b>\n"
        f"鈴� 丕賱賲丿丞: {RUN_DURATION_HOURS} 爻丕毓丕鬲\n"
        f"馃挵 丕賱丨丿 丕賱兀丿賳賶 賱賱乇亘丨: {MIN_PROFIT_USD} USDT\n"
        f"馃攧 丕賱丨丿 丕賱兀賯氐賶 賱廿毓丕丿丞 丕賱賲丨丕賵賱丞: {MAX_RETRIES}\n"
        f"馃洝 <b>賱丕 亘賷毓 亘禺爻丕乇丞 兀亘丿丕賸!</b>"
    )

    while time.time() < end_time:
        loop_start = time.time()

        try:
            history = load_history()
            current_price, price_1h_ago = get_prices()

            # 廿匕丕 賮卮賱 噩賱亘 丕賱兀爻毓丕乇 - 鬲禺胤賶 丕賱丿賵乇丞
            if current_price is None or price_1h_ago is None:
                print("鈴� 鬲禺胤賷 丕賱丿賵乇丞 丕賱丨丕賱賷丞 亘爻亘亘 賮卮賱 噩賱亘 丕賱兀爻毓丕乇...")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            # 1锔忊儯 賮丨氐 丕賱亘賷毓 兀賵賱丕賸
            sold, history = check_and_sell(history, current_price)
            if sold:
                save_history(history)
                git_commit_and_push()
                history = load_history()

            # 2锔忊儯 丕賱鬲丨賯賯 賲賳 丕賱丨丿 丕賱賷賵賲賷
            today = datetime.utcnow().date().isoformat()
            todays_buys = sum(1 for d in history.get('operations', {}).values() 
                            if d.get('date') == today and d.get('type') == 'buy')

            if todays_buys >= MAX_BUYS_PER_DAY:
                print(f"鈴� 丕賱丨丿 丕賱賷賵賲賷 ({MAX_BUYS_PER_DAY})")
                elapsed = time.time() - loop_start
                sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
                time.sleep(sleep_time)
                continue

            # 3锔忊儯 賮丨氐 丕賱卮乇丕亍
            diff = price_1h_ago - current_price
            print(f"馃搳 丕賱丨丕賱賷: {current_price:.2f} | 賯亘賱 爻丕毓丞: {price_1h_ago:.2f} | 丕賱賮丕乇賯: {diff:.2f}")

            if diff >= PRICE_DROP_THRESHOLD:
                print(f"馃幆 賴亘賵胤 {diff:.2f}$! 卮乇丕亍...")

                order, fee, qty, actual_price, total_cost = execute_buy()

                # 廿匕丕 賮卮賱 丕賱卮乇丕亍 - 鬲禺胤賶 賵丕爻鬲賲乇
                if order is None or qty <= 0:
                    print("鈴� 鬲禺胤賷 丕賱卮乇丕亍 亘爻亘亘 丕賱賮卮賱...")
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
                    f"鉁� <b>鬲賲 丕賱卮乇丕亍!</b>\n\n"
                    f"馃啍 <code>{op_id}</code>\n"
                    f"馃挵 爻毓乇: <code>{actual_price:.2f}</code>\n"
                    f"馃搳 賰賲賷丞: <code>{qty:.6f} BTC</code>\n"
                    f"馃捀 乇爻賵賲: <code>{fee:.4f}</code>\n"
                    f"馃挼 鬲賰賱賮丞: <code>{calc['total_cost']:.2f}</code>\n"
                    f"鈿栵笍 鬲毓丕丿賱: <code>{calc['break_even_price']:.2f}</code>\n"
                    f"馃幆 亘賷毓 毓賳丿: <code>{calc['min_sell_price']:.2f}</code>\n"
                    f"馃挌 乇亘丨 兀丿賳賶: <code>{MIN_PROFIT_USD} USDT</code>"
                )
                send_telegram_message(msg)

        except Exception as e:
            error = f"鈿狅笍 禺胤兀: {str(e)[:200]}"
            print(error)
            send_telegram_message(error)

            # 廿毓丕丿丞 鬲賴賷卅丞 丕賱丕鬲氐丕賱 廿匕丕 賰丕賳 禺胤兀 IP 兀賵 丕鬲氐丕賱
            if "IP" in str(e) or "banned" in str(e).lower() or "connection" in str(e).lower():
                print("馃攧 廿毓丕丿丞 鬲賴賷卅丞 丕賱丕鬲氐丕賱 賲毓 亘乇賵賰爻賷 噩丿賷丿...")
                time.sleep(5)
                init_client()  # 賷噩賱亘 亘乇賵賰爻賷 噩丿賷丿 賵賱丕 賷鬲賵賯賮

        # 囟亘胤 丕賱賳賵賲
        elapsed = time.time() - loop_start
        sleep_time = max(0, (SLEEP_INTERVAL_MINUTES * 60) - elapsed)
        time.sleep(sleep_time)

    send_telegram_message("馃洃 丕賳鬲賴鬲 丕賱賭 6 爻丕毓丕鬲.")

if __name__ == "__main__":
    main()
