# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 Next Catalyst AI Pro — Pre-Breakout Engine
 محرك اكتشاف الأسهم قبل انطلاقها (12 مؤشرًا + درجة مدمجة)
───────────────────────────────────────────────────────────────────────────────
 • Pure Python — بدون مكتبات خارجية (يعمل في أي بيئة Railway)
 • مستقل عن المصدر — يستقبل شموع OHLCV من FMP أو Finnhub
 • الاستخدام:
       from pre_breakout import pre_breakout_score
       result = pre_breakout_score(ohlcv, benchmark_closes=spy_closes)
   حيث ohlcv = [{"open":..,"high":..,"low":..,"close":..,"volume":..}, ...]
   مرتّبة من الأقدم إلى الأحدث.
═══════════════════════════════════════════════════════════════════════════════
"""

from math import sqrt


# ───────────────────────────── أدوات أساسية ─────────────────────────────
def _ema_series(values, period):
    """سلسلة EMA كاملة."""
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]          # بذرة = SMA
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _ema(values, period):
    s = _ema_series(values, period)
    return s[-1] if s else None


def _sma(values, period):
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _std(values, period):
    if len(values) < period:
        return None
    seg = values[-period:]
    m = sum(seg) / period
    return sqrt(sum((x - m) ** 2 for x in seg) / period)


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ───────────────────────────── المؤشرات الـ12 ─────────────────────────────
def ema_trend(closes):
    """1) EMA21 + EMA50 — بداية الاتجاه."""
    e21, e50 = _ema(closes, 21), _ema(closes, 50)
    price = closes[-1]
    if not e21 or not e50:
        return {"score": 0.5, "e21": e21, "e50": e50, "bull": False}
    if price > e21 > e50:
        sc, bull = 1.0, True
    elif price > e21:
        sc, bull = 0.6, True
    elif price > e50:
        sc, bull = 0.3, False
    else:
        sc, bull = 0.0, False
    return {"score": sc, "e21": round(e21, 2), "e50": round(e50, 2), "bull": bull}


def macd(closes):
    """2) MACD — تقاطع + تحسّن الهيستوجرام."""
    m_line = _ema_series(closes, 12)
    m_slow = _ema_series(closes, 26)
    if not m_line or not m_slow:
        return {"score": 0.5}
    n = min(len(m_line), len(m_slow))
    macd_line = [m_line[-n + i] - m_slow[-n + i] for i in range(n)]
    sig = _ema_series(macd_line, 9)
    if not sig:
        return {"score": 0.5}
    line, signal = macd_line[-1], sig[-1]
    hist = line - signal
    hist_prev = macd_line[-2] - sig[-2] if len(sig) >= 2 else hist
    rising = hist > hist_prev
    if line > signal and rising and line > 0:
        sc = 1.0
    elif line > signal and rising:
        sc = 0.8
    elif line > signal:
        sc = 0.6
    elif rising:
        sc = 0.35
    else:
        sc = 0.1
    return {"score": sc, "line": round(line, 4), "signal": round(signal, 4),
            "hist": round(hist, 4), "rising": rising}


def relative_strength(closes, benchmark_closes=None):
    """3) RS مقابل السوق — التفوّق على المؤشر (3 و6 أشهر)."""
    def ret(series, days):
        if len(series) <= days or series[-days - 1] == 0:
            return None
        return (series[-1] / series[-days - 1] - 1) * 100

    if not benchmark_closes:
        return {"score": 0.5, "note": "لا يوجد مؤشر مرجعي", "out_3m": None}
    out3 = None
    s3, b3 = ret(closes, 63), ret(benchmark_closes, 63)
    s6, b6 = ret(closes, 126), ret(benchmark_closes, 126)
    if s3 is not None and b3 is not None:
        out3 = s3 - b3
    out6 = (s6 - b6) if (s6 is not None and b6 is not None) else None
    base = out3 if out3 is not None else (out6 or 0)
    if base > 15:
        sc = 1.0
    elif base > 5:
        sc = 0.8
    elif base > 0:
        sc = 0.6
    elif base > -10:
        sc = 0.3
    else:
        sc = 0.1
    return {"score": sc, "out_3m": round(out3, 1) if out3 is not None else None,
            "out_6m": round(out6, 1) if out6 is not None else None}


def volume_surge(ohlcv):
    """4) RVOL — حجم اليوم مقابل متوسط 20 يوم."""
    vols = [c["volume"] for c in ohlcv]
    if len(vols) < 21:
        return {"score": 0.5, "rvol": None}
    avg = sum(vols[-21:-1]) / 20
    rvol = (vols[-1] / avg) if avg else 1
    if rvol >= 3:
        sc = 1.0
    elif rvol >= 2:
        sc = 0.85
    elif rvol >= 1.5:
        sc = 0.55
    elif rvol >= 1:
        sc = 0.3
    else:
        sc = 0.15
    return {"score": sc, "rvol": round(rvol, 2)}


def _atr_series(ohlcv, period=14):
    if len(ohlcv) < period + 1:
        return []
    trs = []
    for i in range(1, len(ohlcv)):
        h, l, pc = ohlcv[i]["high"], ohlcv[i]["low"], ohlcv[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    # SMA بسيط للـ TR
    out = []
    for i in range(period, len(trs) + 1):
        out.append(sum(trs[i - period:i]) / period)
    return out


def atr_expansion(ohlcv, period=14):
    """5) ATR — توسّع التذبذب (بداية حركة) + قيمة لوقف الخسارة."""
    a = _atr_series(ohlcv, period)
    if len(a) < 11:
        return {"score": 0.5, "atr": (a[-1] if a else None)}
    cur, prev = a[-1], a[-11]              # ATR الآن مقابل قبل 10 جلسات
    ratio = (cur / prev) if prev else 1
    price = ohlcv[-1]["close"]
    atr_pct = (cur / price * 100) if price else 0
    if ratio >= 1.3:
        sc = 1.0
    elif ratio >= 1.1:
        sc = 0.75
    elif ratio >= 0.95:
        sc = 0.5
    else:
        sc = 0.3
    return {"score": sc, "atr": round(cur, 2), "atr_pct": round(atr_pct, 2),
            "expansion": round(ratio, 2)}


def adx(ohlcv, period=14):
    """6) ADX + DI — قوة واتجاه الترند (Wilder)."""
    if len(ohlcv) < period * 2 + 1:
        return {"score": 0.5, "adx": None}
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(ohlcv)):
        up = ohlcv[i]["high"] - ohlcv[i - 1]["high"]
        dn = ohlcv[i - 1]["low"] - ohlcv[i]["low"]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        h, l, pc = ohlcv[i]["high"], ohlcv[i]["low"], ohlcv[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    def wilder(seq):
        sm = sum(seq[:period])
        out = [sm]
        for v in seq[period:]:
            sm = sm - (sm / period) + v
            out.append(sm)
        return out

    tr_s = wilder(trs)
    pdm_s = wilder(plus_dm)
    mdm_s = wilder(minus_dm)
    n = min(len(tr_s), len(pdm_s), len(mdm_s))
    dxs = []
    pdi = mdi = 0
    for i in range(n):
        tr = tr_s[i] or 1e-9
        pdi = 100 * pdm_s[i] / tr
        mdi = 100 * mdm_s[i] / tr
        s = (pdi + mdi) or 1e-9
        dxs.append(100 * abs(pdi - mdi) / s)
    if len(dxs) < period:
        return {"score": 0.5, "adx": None}
    adx_val = sum(dxs[-period:]) / period
    bull = pdi > mdi
    if adx_val >= 25 and bull:
        sc = 1.0
    elif adx_val >= 25:
        sc = 0.4
    elif adx_val >= 20 and bull:
        sc = 0.6
    else:
        sc = 0.25
    return {"score": sc, "adx": round(adx_val, 1),
            "plus_di": round(pdi, 1), "minus_di": round(mdi, 1), "bull": bull}


def bollinger_squeeze(closes, period=20, lookback=50):
    """7) Bollinger Squeeze — ضيق الباندات (تجمّع قبل الانفجار)."""
    if len(closes) < period + lookback:
        return {"score": 0.5, "squeeze": False}
    widths = []
    for i in range(period, len(closes) + 1):
        seg = closes[i - period:i]
        m = sum(seg) / period
        sd = sqrt(sum((x - m) ** 2 for x in seg) / period)
        widths.append((4 * sd) / m if m else 0)        # عرض الباند النسبي
    cur = widths[-1]
    recent = widths[-lookback:]
    lo = min(recent)
    in_squeeze = cur <= lo * 1.15                       # قرب أضيق نطاق
    if in_squeeze:
        sc = 1.0
    elif cur <= lo * 1.4:
        sc = 0.6
    else:
        sc = 0.3
    return {"score": sc, "squeeze": in_squeeze, "width": round(cur * 100, 2)}


def vwap_position(ohlcv, period=20):
    """8) VWAP (تقريب يومي) — السعر فوق متوسط السعر المرجح بالحجم."""
    seg = ohlcv[-period:]
    num = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in seg)
    den = sum(c["volume"] for c in seg)
    if not den:
        return {"score": 0.5, "vwap": None}
    vwap = num / den
    price = ohlcv[-1]["close"]
    sc = 0.9 if price > vwap else 0.3
    return {"score": sc, "vwap": round(vwap, 2), "above": price > vwap}


def donchian_breakout(ohlcv, period=20):
    """9) Donchian — اختراق أعلى 20 يومًا."""
    if len(ohlcv) < period + 1:
        return {"score": 0.5}
    prior_high = max(c["high"] for c in ohlcv[-period - 1:-1])
    prior_low = min(c["low"] for c in ohlcv[-period - 1:-1])
    price = ohlcv[-1]["close"]
    rng = (prior_high - prior_low) or 1e-9
    pos = (price - prior_low) / rng
    if price >= prior_high:
        sc = 1.0
    elif pos >= 0.9:
        sc = 0.7
    elif pos >= 0.7:
        sc = 0.5
    else:
        sc = 0.25
    return {"score": sc, "breakout": price >= prior_high,
            "high20": round(prior_high, 2)}


def ichimoku(ohlcv):
    """10) Ichimoku — السعر فوق السحابة + Tenkan>Kijun."""
    if len(ohlcv) < 52:
        return {"score": 0.5}
    highs = [c["high"] for c in ohlcv]
    lows = [c["low"] for c in ohlcv]

    def mid(n):
        return (max(highs[-n:]) + min(lows[-n:])) / 2
    tenkan, kijun = mid(9), mid(26)
    span_a = (tenkan + kijun) / 2
    span_b = (max(highs[-52:]) + min(lows[-52:])) / 2
    price = ohlcv[-1]["close"]
    cloud_top = max(span_a, span_b)
    above = price > cloud_top
    if above and tenkan > kijun:
        sc = 1.0
    elif above:
        sc = 0.7
    elif price > min(span_a, span_b):
        sc = 0.45
    else:
        sc = 0.2
    return {"score": sc, "above_cloud": above, "tenkan_gt_kijun": tenkan > kijun}


def obv_trend(ohlcv, lookback=20):
    """11) OBV — تجميع ذكي (OBV صاعد)."""
    obv = [0]
    for i in range(1, len(ohlcv)):
        if ohlcv[i]["close"] > ohlcv[i - 1]["close"]:
            obv.append(obv[-1] + ohlcv[i]["volume"])
        elif ohlcv[i]["close"] < ohlcv[i - 1]["close"]:
            obv.append(obv[-1] - ohlcv[i]["volume"])
        else:
            obv.append(obv[-1])
    if len(obv) < lookback + 1:
        return {"score": 0.5}
    slope = obv[-1] - obv[-lookback - 1]
    rng = max(abs(x) for x in obv[-lookback - 1:]) or 1
    norm = slope / rng
    if norm > 0.3:
        sc = 1.0
    elif norm > 0:
        sc = 0.65
    elif norm > -0.3:
        sc = 0.35
    else:
        sc = 0.15
    return {"score": sc, "rising": slope > 0}


def chaikin_money_flow(ohlcv, period=20):
    """12) CMF — تدفق السيولة إلى السهم."""
    seg = ohlcv[-period:]
    mfv = 0.0
    vol = 0.0
    for c in seg:
        hl = (c["high"] - c["low"]) or 1e-9
        mult = ((c["close"] - c["low"]) - (c["high"] - c["close"])) / hl
        mfv += mult * c["volume"]
        vol += c["volume"]
    cmf = (mfv / vol) if vol else 0
    if cmf > 0.1:
        sc = 1.0
    elif cmf > 0.05:
        sc = 0.75
    elif cmf > 0:
        sc = 0.55
    elif cmf > -0.1:
        sc = 0.3
    else:
        sc = 0.1
    return {"score": sc, "cmf": round(cmf, 3)}


# ───────────────────────────── الدرجة المدمجة ─────────────────────────────
# الأوزان حسب وصفتك (المجموع = 100)
WEIGHTS = {
    "ema": 15, "macd": 15, "rs": 15, "rvol": 15,
    "atr": 8, "adx": 8, "bollinger": 8, "obv": 8,
    "cmf": 4, "donchian": 4,
}


def pre_breakout_score(ohlcv, benchmark_closes=None):
    """
    يحسب درجة Pre-Breakout (0–100) من 12 مؤشرًا + يُرجع التفاصيل والأسباب.
    """
    if not ohlcv or len(ohlcv) < 60:
        return {"error": "بيانات غير كافية (نحتاج 60 جلسة على الأقل)", "score": 0}
    closes = [c["close"] for c in ohlcv]

    comp = {
        "ema": ema_trend(closes),
        "macd": macd(closes),
        "rs": relative_strength(closes, benchmark_closes),
        "rvol": volume_surge(ohlcv),
        "atr": atr_expansion(ohlcv),
        "adx": adx(ohlcv),
        "bollinger": bollinger_squeeze(closes),
        "obv": obv_trend(ohlcv),
        "cmf": chaikin_money_flow(ohlcv),
        "donchian": donchian_breakout(ohlcv),
    }
    # مؤشرات إضافية للعرض (لا تدخل الوزن لتفادي الازدواج)
    extra = {"vwap": vwap_position(ohlcv), "ichimoku": ichimoku(ohlcv)}

    total = 0.0
    for key, w in WEIGHTS.items():
        total += _clamp(comp[key]["score"]) * w
    score = round(total)

    if score >= 75:
        verdict, emoji = "انفجار قوي — جاهز للانطلاق", "🚀🚀"
    elif score >= 60:
        verdict, emoji = "بداية الانفجار", "🚀"
    elif score >= 45:
        verdict, emoji = "قبل الانفجار — يتجمّع", "🔭"
    else:
        verdict, emoji = "لا إشارة قوية", "⚠️"

    return {
        "score": score, "verdict": verdict, "emoji": emoji,
        "components": comp, "extra": extra,
        "reasons": _reasons(comp, extra),
    }


def _reasons(comp, extra):
    """أسباب نصية مبنية على المؤشرات."""
    out = []
    e = comp["ema"]
    if e.get("bull") and e["score"] >= 1.0:
        out.append(("✅", "السعر فوق EMA21 وEMA21 فوق EMA50 — اتجاه صاعد مبكر"))
    elif e.get("bull"):
        out.append(("✅", "السعر فوق EMA21"))
    else:
        out.append(("⚠️", "السعر تحت المتوسطات الأسية"))

    m = comp["macd"]
    if m["score"] >= 0.8:
        out.append(("✅", "MACD إيجابي مع تحسّن الهيستوجرام — زخم مبكر"))
    elif m["score"] >= 0.6:
        out.append(("✅", "تقاطع MACD إيجابي"))
    else:
        out.append(("⚠️", "MACD ضعيف"))

    r = comp["rs"]
    if r.get("out_3m") is not None:
        if r["score"] >= 0.6:
            out.append(("✅", f"يتفوّق على السوق (+{r['out_3m']}% خلال 3 أشهر)"))
        else:
            out.append(("⚠️", f"أداء أضعف من السوق ({r['out_3m']}% خلال 3 أشهر)"))

    rv = comp["rvol"]
    if rv.get("rvol") and rv["rvol"] >= 2:
        out.append(("✅", f"قفزة حجم قوية ({rv['rvol']}x المتوسط)"))
    elif rv.get("rvol") and rv["rvol"] >= 1.5:
        out.append(("✅", f"حجم أعلى من المتوسط ({rv['rvol']}x)"))

    if comp["adx"].get("adx") and comp["adx"]["score"] >= 0.6:
        out.append(("✅", f"اتجاه قوي (ADX {comp['adx']['adx']})"))
    if comp["bollinger"].get("squeeze"):
        out.append(("🎯", "ضغط بولينجر — تجمّع قبل حركة كبيرة محتملة"))
    if comp["donchian"].get("breakout"):
        out.append(("🚀", f"اختراق أعلى 20 يومًا ({comp['donchian']['high20']})"))
    if comp["obv"].get("rising"):
        out.append(("✅", "OBV صاعد — تجميع ذكي"))
    if comp["cmf"].get("cmf", 0) > 0.05:
        out.append(("✅", f"تدفق سيولة إيجابي (CMF {comp['cmf']['cmf']})"))
    if extra["ichimoku"].get("above_cloud"):
        out.append(("✅", "السعر فوق سحابة Ichimoku"))
    return out
