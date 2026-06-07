from datetime import datetime
from app import db

class InsiderTrade(db.Model):
    """كل صفقة مطلع من Finnhub"""
    __tablename__ = "insider_trades"

    id            = db.Column(db.Integer, primary_key=True)
    symbol        = db.Column(db.String(20), nullable=False, index=True)
    company_name  = db.Column(db.String(200))
    name          = db.Column(db.String(200))   # اسم المطلع
    title         = db.Column(db.String(200))   # منصبه
    trade_type    = db.Column(db.String(10))    # buy / sell
    shares        = db.Column(db.BigInteger)
    price         = db.Column(db.Float)
    value         = db.Column(db.Float)         # shares * price
    trade_date    = db.Column(db.Date)
    filing_date   = db.Column(db.Date)
    signal_score  = db.Column(db.Integer, default=0)  # 0-100
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":           self.id,
            "symbol":       self.symbol,
            "company":      self.company_name,
            "name":         self.name,
            "title":        self.title,
            "type":         self.trade_type,
            "shares":       self.shares,
            "price":        self.price,
            "value":        self.value,
            "trade_date":   str(self.trade_date) if self.trade_date else None,
            "signal_score": self.signal_score,
        }


class WatchedStock(db.Model):
    """الأسهم التي يتابعها المستخدم"""
    __tablename__ = "watched_stocks"

    id         = db.Column(db.Integer, primary_key=True)
    symbol     = db.Column(db.String(20), unique=True, nullable=False)
    added_at   = db.Column(db.DateTime, default=datetime.utcnow)


class InsiderScore(db.Model):
    """سجل أداء كل مطلع تاريخياً"""
    __tablename__ = "insider_scores"

    id           = db.Column(db.Integer, primary_key=True)
    insider_name = db.Column(db.String(200), unique=True, nullable=False)
    symbol       = db.Column(db.String(20))
    total_trades = db.Column(db.Integer, default=0)
    buy_count    = db.Column(db.Integer, default=0)
    sell_count   = db.Column(db.Integer, default=0)
    accuracy_pct = db.Column(db.Float, default=0)   # % صفقات رابحة
    total_value  = db.Column(db.Float, default=0)
    score        = db.Column(db.Integer, default=0)  # 0-100
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow)
