from flask import Blueprint, jsonify, request
from app.services.insider_service import insider_service

api_bp = Blueprint("api", __name__)

@api_bp.route("/insider/<symbol>")
def insider_data(symbol):
    trades = insider_service.get_insider_transactions(symbol.upper())
    return jsonify({"symbol": symbol.upper(), "trades": trades})

@api_bp.route("/sentiment/<symbol>")
def sentiment(symbol):
    data = insider_service.get_insider_sentiment(symbol.upper())
    return jsonify(data)

@api_bp.route("/summary/<symbol>")
def summary(symbol):
    data = insider_service.get_stock_insider_summary(symbol.upper())
    return jsonify(data)

@api_bp.route("/screen")
def screen():
    symbols = request.args.get("symbols", "NVDA,AAPL,MSFT,META").split(",")
    results = insider_service.screen_high_insider_buying(symbols)
    return jsonify(results)
