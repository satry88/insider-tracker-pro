# -*- coding: utf-8 -*-
"""
prebreakout_data.py — Next Catalyst AI Pro
==========================================
يربط محرك Pre-Breakout ببيانات البوت الحالية.
يعيد استخدام fmp_service (FMP + Finnhub، نفس المفاتيح) لجلب شموع OHLCV،
ثم يستدعي pre_breakout_score. لا يعدّل fmp_service إطلاقًا.
"""

import time
import logging

from app.services.fmp_service import fmp_service
from app.services.pre_breakout import pre_breakout_score

logger = logging.getLogger(__name__)

# كاش بسيط لتقليل الطلبات (المؤشر المرجعي SPY يُجلب مرة)
_cache = {}
_CACHE_TTL = 1800   # 30 دقيقة


def _cached(key):
    item = _cache.get(key)
    if item and (time.time() - item[1]) < _CACHE_TTL:
        return item[0]
    return None


def _store(key, val):
    _cache[key] = (val, time.time())


def _ohlcv(symbol, days=220):
    """
    يجلب شموع يومية OHLCV (الأقدم → الأحدث).
    1) FMP: historical-price-full  2) Finnhub: stock/candle (احتياطي)
    """
    cached = _cached(f"ohlcv:{symbol}")
    if cached is not None:
        return cached

    rows = []
    # ── المصدر 1: FMP ──
    try:
        data = fmp_service._fmp(f"historical-price-full/{symbol}", {"timeseries": days})
        hist = data.get("historical") if isinstance(data, dict) else None
        if hist:
            for h in reversed(hist):                       # الأقدم أولًا
                if h.get("close") is not None:
                    rows.append({
                        "open":   h.get("open"),
                        "high":   h.get("high"),
                        "low":    h.get("low"),
                        "close":  h.get("close"),
                        "volume": h.get("volume") or 0,
                    })
    except Exception as e:
        logger.warning("FMP history '%s': %s", symbol, e)

    # ── المصدر 2: Finnhub candle (احتياطي) ──
    if len(rows) < 60:
        try:
            to = int(time.time())
            frm = to - days * 86400 * 2
            d = fmp_service._fh("stock/candle", {
                "symbol": symbol, "resolution": "D", "from": frm, "to": to})
            if isinstance(d, dict) and d.get("s") == "ok" and d.get("c"):
                rows = [{
                    "open":   d["o"][i], "high": d["h"][i], "low": d["l"][i],
                    "close":  d["c"][i], "volume": d["v"][i],
                } for i in range(len(d["c"]))]
        except Exception as e:
            logger.warning("Finnhub candle '%s': %s", symbol, e)

    _store(f"ohlcv:{symbol}", rows)
    return rows


def get_prebreakout(symbol, benchmark="SPY"):
    """
    يحسب درجة Pre-Breakout للسهم مقابل المؤشر المرجعي (SPY افتراضيًا).
    يُرجع dict النتيجة أو None إن لم تتوفر بيانات كافية.
    """
    ohlcv = _ohlcv(symbol)
    if not ohlcv or len(ohlcv) < 60:
        return None
    bench = _ohlcv(benchmark)
    bench_closes = [c["close"] for c in bench] if bench and len(bench) >= 60 else None
    try:
        return pre_breakout_score(ohlcv, benchmark_closes=bench_closes)
    except Exception as e:
        logger.warning("pre_breakout '%s': %s", symbol, e)
        return None
