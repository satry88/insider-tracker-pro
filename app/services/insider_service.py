"""
insider_service.py — Insider Tracker Pro
=========================================
جميع بيانات المطلعين من Finnhub API (مجاني 100%)
"""

import os
import math
import logging
import requests
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

FH_KEY  = os.getenv("FINNHUB_API_KEY", "")
FH_BASE = "https://finnhub.io/api/v1"


def _safe_float(val, default=None):
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


class InsiderService:

    def _fh(self, endpoint, params=None):
        if not FH_KEY:
            return None
        try:
            r = requests.get(
                f"{FH_BASE}/{endpoint}",
                params={"token": FH_KEY, **(params or {})},
                timeout=8
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.warning("Finnhub '%s': %s", endpoint, exc)
            return None

    # ── Stock Profile ─────────────────────────────────────────────────────────

    def get_profile(self, symbol):
        data = self._fh("stock/profile2", {"symbol": symbol.upper()}) or {}
        return {
            "symbol":   symbol.upper(),
            "name":     data.get("name", symbol),
            "sector":   data.get("finnhubIndustry", ""),
            "logo":     data.get("logo", ""),
            "country":  data.get("country", ""),
            "exchange": data.get("exchange", ""),
        }

    def get_quote(self, symbol):
        data = self._fh("quote", {"symbol": symbol.upper()}) or {}
        return {
            "price":      _safe_float(data.get("c")),
            "change":     _safe_float(data.get("d")),
            "change_pct": _safe_float(data.get("dp")),
            "high":       _safe_float(data.get("h")),
            "low":        _safe_float(data.get("l")),
        }

    # ── Insider Transactions ──────────────────────────────────────────────────

    def get_insider_transactions(self, symbol, from_date=None, to_date=None):
        """
        إرجاع قائمة صفقات المطلعين لسهم معين.
        from_date / to_date: YYYY-MM-DD strings
        """
        if not from_date:
            from_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = date.today().strftime("%Y-%m-%d")

        data = self._fh("stock/insider-transactions", {
            "symbol": symbol.upper(),
            "from":   from_date,
            "to":     to_date,
        }) or {}

        trades = []
        for t in data.get("data", []):
            shares = _safe_float(t.get("share", 0), 0)
            price  = _safe_float(t.get("transactionPrice", 0), 0)
            ttype  = t.get("transactionCode", "").upper()

            # P = Purchase (شراء), S = Sale (بيع)
            if ttype == "P":
                trade_type = "buy"
            elif ttype in ("S", "S-"):
                trade_type = "sell"
            else:
                continue   # نتجاهل الخيارات والمنح

            value = abs(shares * price) if price else 0
            signal = self._calc_signal_score(trade_type, value, t.get("name", ""))

            trades.append({
                "symbol":      symbol.upper(),
                "name":        t.get("name", "Unknown"),
                "title":       "",   # Finnhub لا يُرجع المنصب في هذا endpoint
                "type":        trade_type,
                "shares":      int(abs(shares)),
                "price":       price,
                "value":       value,
                "trade_date":  t.get("transactionDate", ""),
                "filing_date": t.get("filingDate", ""),
                "signal_score": signal,
            })

        # ترتيب: الأحدث أولاً
        trades.sort(key=lambda x: x["trade_date"], reverse=True)
        return trades

    # ── Latest Insider Activity (all stocks) ──────────────────────────────────

    def get_latest_insider_activity(self, symbols: list, days=30):
        """
        آخر نشاط المطلعين لقائمة أسهم.
        يُرجع قائمة موحدة مرتبة بالتاريخ.
        """
        all_trades = []
        from_date  = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        to_date    = date.today().strftime("%Y-%m-%d")

        for symbol in symbols:
            trades = self.get_insider_transactions(symbol, from_date, to_date)
            all_trades.extend(trades)

        all_trades.sort(key=lambda x: x["trade_date"], reverse=True)
        return all_trades

    # ── Signal Score ──────────────────────────────────────────────────────────

    def _calc_signal_score(self, trade_type, value, insider_name):
        """
        نقاط الإشارة 0-100:
        - الشراء أقوى من البيع
        - القيمة الأعلى = إشارة أقوى
        - المنصب الرفيع = إشارة أقوى
        """
        score = 0

        # نوع الصفقة
        if trade_type == "buy":
            score += 40
        else:
            score += 10   # البيع أقل أهمية (قد يكون لأسباب شخصية)

        # قيمة الصفقة
        if value >= 1_000_000:
            score += 40
        elif value >= 500_000:
            score += 30
        elif value >= 100_000:
            score += 20
        elif value >= 50_000:
            score += 10

        # المنصب (نستخدم الاسم كـ proxy بسيط)
        name_lower = insider_name.lower()
        if any(k in name_lower for k in ["ceo", "chief exec", "president"]):
            score += 20
        elif any(k in name_lower for k in ["cfo", "coo", "director", "chairman"]):
            score += 15
        elif any(k in name_lower for k in ["vp", "vice"]):
            score += 10

        return min(score, 100)

    # ── Insider Sentiment ─────────────────────────────────────────────────────

    def get_insider_sentiment(self, symbol, from_date=None, to_date=None):
        """
        Finnhub Insider Sentiment — MSPR score
        양수 = صعودي، سالب = هبوطي
        """
        if not from_date:
            from_date = (date.today() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = date.today().strftime("%Y-%m-%d")

        data = self._fh("stock/insider-sentiment", {
            "symbol": symbol.upper(),
            "from":   from_date,
            "to":     to_date,
        }) or {}

        sentiment_data = data.get("data", [])
        if not sentiment_data:
            return {"mspr": 0, "change": 0, "label": "محايد", "color": "#facc15"}

        latest = sentiment_data[-1]
        mspr   = _safe_float(latest.get("mspr"), 0)
        change = _safe_float(latest.get("change"), 0)

        if mspr > 0.1:
            label = "صعودي 🟢"; color = "#22c55e"
        elif mspr < -0.1:
            label = "هبوطي 🔴"; color = "#ef4444"
        else:
            label = "محايد ⚪"; color = "#facc15"

        return {"mspr": round(mspr, 3), "change": change, "label": label, "color": color}

    # ── Stock Screener: High Insider Buying ───────────────────────────────────

    def screen_high_insider_buying(self, watchlist: list):
        """
        من قائمة الأسهم، أرجع الأسهم التي فيها شراء مطلعين مرتفع مؤخراً.
        """
        results = []
        from_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")

        for symbol in watchlist:
            trades = self.get_insider_transactions(symbol, from_date=from_date)
            buys   = [t for t in trades if t["type"] == "buy"]
            sells  = [t for t in trades if t["type"] == "sell"]

            if not buys:
                continue

            total_buy_value  = sum(t["value"] for t in buys)
            total_sell_value = sum(t["value"] for t in sells)
            buy_ratio = total_buy_value / (total_buy_value + total_sell_value + 1) * 100

            # أعلى إشارة شراء
            top_signal = max(t["signal_score"] for t in buys)

            results.append({
                "symbol":           symbol,
                "buy_count":        len(buys),
                "sell_count":       len(sells),
                "total_buy_value":  total_buy_value,
                "buy_ratio":        round(buy_ratio, 1),
                "top_signal":       top_signal,
                "latest_trade":     buys[0] if buys else None,
            })

        results.sort(key=lambda x: x["top_signal"], reverse=True)
        return results

    # ── Summary for Dashboard ─────────────────────────────────────────────────

    def get_stock_insider_summary(self, symbol):
        """ملخص كامل لصفحة السهم."""
        profile    = self.get_profile(symbol)
        quote      = self.get_quote(symbol)
        trades     = self.get_insider_transactions(symbol)
        sentiment  = self.get_insider_sentiment(symbol)

        buys  = [t for t in trades if t["type"] == "buy"]
        sells = [t for t in trades if t["type"] == "sell"]

        total_buy_val  = sum(t["value"] for t in buys)
        total_sell_val = sum(t["value"] for t in sells)

        # نقاط الثقة الكلية (0-100)
        if buys:
            avg_signal = sum(t["signal_score"] for t in buys) / len(buys)
        else:
            avg_signal = 0

        if total_buy_val > total_sell_val * 1.5:
            overall = "شراء قوي 🔥"; overall_color = "#22c55e"
        elif total_buy_val > total_sell_val:
            overall = "شراء معتدل ✅"; overall_color = "#86efac"
        elif total_sell_val > total_buy_val * 1.5:
            overall = "بيع مرتفع ⚠️"; overall_color = "#ef4444"
        else:
            overall = "محايد ⚪"; overall_color = "#facc15"

        return {
            "symbol":         symbol.upper(),
            "profile":        profile,
            "quote":          quote,
            "trades":         trades[:20],
            "sentiment":      sentiment,
            "buy_count":      len(buys),
            "sell_count":     len(sells),
            "total_buy_val":  total_buy_val,
            "total_sell_val": total_sell_val,
            "avg_signal":     round(avg_signal),
            "overall":        overall,
            "overall_color":  overall_color,
        }


insider_service = InsiderService()
