import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import streamlit as st

# Oliver Signals — educational market dashboard.
# This app displays market indicators for learning/paper tracking only.
# It does not place trades or provide financial advice.

PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"]
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_PRICE = "https://api.binance.com/api/v3/ticker/price"
HEADERS = {"User-Agent": "OliverSignals/1.0"}


def fetch_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def get_market_data(symbol):
    params = urllib.parse.urlencode(
        {"symbol": symbol, "interval": "1m", "limit": 60}
    )
    candles = fetch_json(f"{BINANCE_KLINES}?{params}")
    # Exclude the currently-forming candle.
    closes = [float(candle[4]) for candle in candles[:-1]]
    price_params = urllib.parse.urlencode({"symbol": symbol})
    current_price = float(
        fetch_json(f"{BINANCE_PRICE}?{price_params}")["price"]
    )
    return closes, current_price


def ema(values, period):
    multiplier = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = value * multiplier + result * (1 - multiplier)
    return result


def rsi(values, period=14):
    recent = values[-(period + 1):]
    gains = 0.0
    losses = 0.0
    for index in range(1, len(recent)):
        change = recent[index] - recent[index - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    if losses == 0:
        return 100.0
    relative_strength = (gains / period) / (losses / period)
    return 100 - (100 / (1 + relative_strength))


def analyze(symbol):
    closes, current_price = get_market_data(symbol)
    fast_ema = ema(closes, 9)
    slow_ema = ema(closes, 21)
    current_rsi = rsi(closes)

    if fast_ema > slow_ema and 50 < current_rsi < 70:
        observation = "اتجاه صاعد"
        reason = "EMA 9 أعلى من EMA 21 و RSI بين 50 و70"
    elif fast_ema < slow_ema and 30 < current_rsi < 50:
        observation = "اتجاه هابط"
        reason = "EMA 9 أقل من EMA 21 و RSI بين 30 و50"
    else:
        observation = "لا توجد إشارة واضحة"
        reason = "المؤشرات لا تحقق شروط الاتجاه المحددة"

    return {
        "العملة": symbol,
        "السعر الحالي": current_price,
        "EMA 9": fast_ema,
        "EMA 21": slow_ema,
        "RSI 14": current_rsi,
        "قراءة المؤشرات": observation,
        "السبب": reason,
    }


def send_telegram(message, token, chat_id):
    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": message}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


st.set_page_config(
    page_title="Oliver Signals",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {background: #0b1220; color: #f4f7fb;}
    [data-testid="stMetric"] {
        background: #141f32;
        border: 1px solid #263650;
        padding: 14px;
        border-radius: 12px;
    }
    div.stButton > button {
        background: #2563eb;
        color: white;
        border: 0;
        border-radius: 9px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 Oliver Signals")
st.caption("لوحة متابعة تعليمية للسوق — بيانات مباشرة من Binance")

st.warning(
    "للتعلّم والتجربة الورقية فقط. قراءات المؤشرات ليست توصية شراء أو بيع، "
    "ولا تضمن أي نتيجة. التطبيق لا ينفّذ صفقات ولا يتصل بمحفظة."
)

left, right = st.columns([3, 1])
with left:
    st.subheader("مراقبة العملات")
    st.write("اضغط على زر الفحص لجلب أحدث بيانات السوق وحساب المؤشرات.")
with right:
    scan_clicked = st.button("🔄 فحص السوق", use_container_width=True)

if "market_results" not in st.session_state:
    st.session_state.market_results = []
if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if scan_clicked:
    results = []
    progress = st.progress(0)
    status = st.empty()
    for index, symbol in enumerate(PAIRS):
        status.write(f"جارٍ فحص {symbol}...")
        try:
            results.append(analyze(symbol))
        except Exception as error:
            results.append(
                {
                    "العملة": symbol,
                    "خطأ": str(error),
                    "قراءة المؤشرات": "تعذّر جلب البيانات",
                }
            )
        progress.progress((index + 1) / len(PAIRS))
    st.session_state.market_results = results
    st.session_state.last_scan = datetime.now(timezone.utc)
    status.empty()
    progress.empty()

if st.session_state.last_scan:
    st.caption(
        "آخر فحص: "
        + st.session_state.last_scan.strftime("%Y-%m-%d %H:%M:%S UTC")
    )

results = st.session_state.market_results
if results:
    good_results = [item for item in results if "خطأ" not in item]
    if good_results:
        st.subheader("ملخص السوق")
        metric_columns = st.columns(len(good_results))
        for column, item in zip(metric_columns, good_results):
            with column:
                st.metric(
                    item["العملة"],
                    f'{item["السعر الحالي"]:,.4f} USDT',
                    item["قراءة المؤشرات"],
                )

        st.subheader("تفاصيل المؤشرات")
        st.dataframe(good_results, use_container_width=True, hide_index=True)

    errors = [item for item in results if "خطأ" in item]
    if errors:
        with st.expander("الأزواج التي تعذّر فحصها"):
            for item in errors:
                st.write(f'{item["العملة"]}: {item["خطأ"]}')
else:
    st.info("لم يتم إجراء فحص بعد. اضغط «فحص السوق» لعرض المؤشرات.")

st.divider()
st.subheader("إشعارات Telegram (اختياري)")
st.write(
    "يمكنك تفعيل إرسال ملخص الفحص إلى تيليغرام بعد إضافة بيانات البوت "
    "بشكل آمن في Streamlit Secrets."
)

with st.expander("إعدادات Telegram"):
    st.code(
        '[telegram]\n'
        'bot_token = "ضع_التوكن_الجديد_هنا"\n'
        'chat_id = "ضع_chat_id_هنا"',
        language="toml",
    )
    telegram_enabled = st.checkbox("تفعيل إرسال الملخص")
    if st.button("إرسال ملخص آخر فحص إلى Telegram"):
        if not telegram_enabled:
            st.error("فعّل خيار إرسال الملخص أولاً.")
        elif not results:
            st.error("افحص السوق أولاً.")
        else:
            try:
                token = st.secrets["telegram"]["bot_token"]
                chat_id = st.secrets["telegram"]["chat_id"]
                lines = ["Oliver Signals — ملخص تعليمي"]
                for item in results:
                    lines.append(
                        f'{item["العملة"]}: {item["قراءة المؤشرات"]}'
                    )
                    if "السعر الحالي" in item:
                        lines.append(
                            f'السعر: {item["السعر الحالي"]:,.4f} USDT'
                        )
                send_telegram("\n".join(lines), token, chat_id)
                st.success("تم إرسال الملخص إلى Telegram.")
            except Exception:
                st.error(
                    "تعذّر الإرسال. تأكد من إعداد bot_token و chat_id "
                    "داخل Streamlit Secrets."
                )

st.caption(
    "المصدر: واجهة بيانات Binance العامة. قد تتأخر البيانات أو تنقطع؛ "
    "لا تعتمد على هذه اللوحة لاتخاذ قرارات مالية."
)
