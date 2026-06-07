from flask import Blueprint, render_template, request, redirect, url_for
from app.services.insider_service import insider_service

dashboard_bp = Blueprint("dashboard", __name__)

# قائمة أسهم افتراضية للمتابعة
DEFAULT_WATCHLIST = [
    "NVDA","AAPL","MSFT","META","GOOG","AMZN",
    "TSLA","PLTR","AMD","AVGO","ORCL","CRM"
]

@dashboard_bp.route("/")
def index():
    """الصفحة الرئيسية — آخر صفقات المطلعين"""
    trades = insider_service.get_latest_insider_activity(DEFAULT_WATCHLIST[:6], days=30)
    return render_template("pages/index.html", trades=trades, watchlist=DEFAULT_WATCHLIST)


@dashboard_bp.route("/stock/<symbol>")
def stock_view(symbol):
    """صفحة سهم واحد — كل المطلعين فيه"""
    summary = insider_service.get_stock_insider_summary(symbol.upper())
    return render_template("pages/stock.html", s=summary)


@dashboard_bp.route("/leaderboard")
def leaderboard():
    """أفضل المطلعين تاريخياً"""
    symbols = DEFAULT_WATCHLIST
    results = insider_service.screen_high_insider_buying(symbols)
    return render_template("pages/leaderboard.html", results=results)


@dashboard_bp.route("/screener")
def screener():
    """فلترة الأسهم بناءً على نشاط المطلعين"""
    results = insider_service.screen_high_insider_buying(DEFAULT_WATCHLIST)
    return render_template("pages/screener.html", results=results)
