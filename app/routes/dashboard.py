from flask import Blueprint, render_template
from app.models.models import Stock, Alert, SystemStats, WatchlistEntry
from app import db
from sqlalchemy import desc, and_
import os

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    from app.services.catalyst_radar import get_radar_stocks
    stats       = SystemStats.query.first()
    top_stocks  = Stock.query.filter(
        Stock.current_price.isnot(None),
        Stock.current_price > 0
    ).order_by(desc(Stock.catalyst_score)).limit(20).all()
    recent_alerts = Alert.query.filter_by(is_read=False).order_by(desc(Alert.created_at)).limit(10).all()
    all_stocks  = Stock.query.filter(Stock.catalyst_score >= 45).all()
    hot_radar   = get_radar_stocks(all_stocks, min_signals=2)[:3]
    return render_template('pages/dashboard.html', stats=stats, top_stocks=top_stocks,
                           recent_alerts=recent_alerts, hot_radar=hot_radar)


@dashboard_bp.route('/stock/<symbol>')
def stock_detail(symbol):
    stock     = Stock.query.filter_by(symbol=symbol.upper()).first_or_404()
    news      = stock.news.order_by(desc('published_at')).limit(10).all()
    catalysts = stock.catalysts.order_by('days_until').all()
    insiders  = stock.insider_transactions.order_by(desc('transaction_date')).limit(10).all()

    x10_data = None
    try:
        from app.services.growth_scorer import calculate_x10_potential
        x10_data = calculate_x10_potential(
            catalyst_score  = stock.catalyst_score or 50,
            future_leader   = stock.future_leader_probability or 50,
            growth_score    = stock.growth_score or 50,
            market_cap      = stock.market_cap,
            revenue_growth  = stock.revenue_growth,
            debt_to_equity  = stock.debt_to_equity,
            sector          = stock.sector,
            piotroski_score = stock.piotroski_score,
            symbol          = stock.symbol,
        )
        if x10_data:
            stock.x10_potential = x10_data['score']
            db.session.commit()
    except:
        pass

    try:
        from app.services.technical_scorer import calculate_technical_score
        tech = calculate_technical_score(stock.symbol)
        ma   = tech.get('ma_data', {})
        if ma and ma.get('ma20'):
            stock.ma_data         = ma
            stock.rs_rating       = tech.get('rs_rating') or stock.rs_rating
            stock.technical_score = tech.get('total_score') or stock.technical_score
            try:
                db.session.commit()
            except:
                pass
    except:
        pass

    try:
        if stock.current_price:
            from app.services.finnhub_service import finnhub_service
            from app.services.catalyst_engine import catalyst_engine
            metrics = finnhub_service.get_basic_financials(stock.symbol)
            profile = finnhub_service.get_company_profile(stock.symbol)
            pt = catalyst_engine.calculate_price_targets(
                stock.symbol, metrics, profile, stock.current_price
            )
            if pt:
                stock.price_targets = pt
                try:
                    db.session.commit()
                except:
                    pass
    except:
        pass

    health_data      = {'grade': 'N/A', 'score': 0, 'label': '...', 'grade_color': '#6B7280', 'details': {}, 'strengths': [], 'weaknesses': []}
    fair_value_data  = {'verdict_ar': 'N/A', 'verdict_icon': '⚪', 'verdict_color': '#6B7280', 'upside_pct': None, 'fair_value_composite': None, 'current_price': None, 'analyst_target': None, 'analyst_upside': None, 'methods_used': [], 'confidence': 0}
    next_rating_data = {'overall_score': 0, 'star_rating': '☆☆☆☆☆', 'recommendation_ar': 'N/A', 'rec_color': '#6B7280', 'rec_icon': '⚪', 'breakdown': {}, 'signals': [], 'health_grade': 'N/A', 'fair_value': 'N/A'}

    try:
        from app.services.catalyst_engine import catalyst_engine
        cs   = stock.catalyst_score    or 0
        rs   = stock.rs_rating         or 0
        ts   = stock.technical_score   or 0
        inst = stock.institutional_score or 5
        ratings = catalyst_engine.calculate_full_ratings(
            symbol=stock.symbol, catalyst_score=cs,
            rs_rating=rs, technical_score=ts, institutional_score=inst,
        )
        if ratings.get('success'):
            health_data      = ratings['health']
            fair_value_data  = ratings['fair_value']
            next_rating_data = ratings['next_rating']
    except:
        pass

    inst_flow_data = None
    try:
        from app.services.institutional_flow import institutional_flow_service
        inst_flow_data = institutional_flow_service.get_full_institutional_flow(stock.symbol)
    except:
        pass

    # 🚀 Pre-Breakout — اكتشاف السهم قبل انطلاقه (12 مؤشرًا فنيًا)
    prebreakout_data = None
    try:
        from app.services.prebreakout_data import get_prebreakout
        prebreakout_data = get_prebreakout(stock.symbol)
    except Exception:
        prebreakout_data = None

    return render_template(
        'pages/stock_detail.html',
        stock=stock, news=news, catalysts=catalysts, insiders=insiders,
        health=health_data, fv=fair_value_data, ncr=next_rating_data,
        inst_flow=inst_flow_data, x10_data=x10_data,
        prebreakout=prebreakout_data,
    )


@dashboard_bp.route('/future-leaders')
def future_leaders():
    leaders = Stock.query.filter(
        and_(Stock.future_leader_probability >= 40, Stock.market_cap < 50000)
    ).order_by(desc(Stock.future_leader_probability)).limit(20).all()
    return render_template('pages/future_leaders.html', leaders=leaders)

@dashboard_bp.route('/hidden-gems')
def hidden_gems():
    gems = Stock.query.filter(
        and_(
            Stock.market_cap <= 20000, Stock.market_cap > 0,
            Stock.catalyst_score >= 60, Stock.revenue_growth >= 0.15,
            Stock.revenue_growth <= 4.0, Stock.revenue_growth != 2.0,
            Stock.current_price.isnot(None), Stock.current_price > 0,
        )
    ).order_by(desc(Stock.catalyst_score)).limit(20).all()
    gems = [s for s in gems if s.revenue_growth != 3.0]

    candidates = []
    if len(gems) < 5:
        all_stocks = Stock.query.filter(
            and_(Stock.market_cap > 0, Stock.market_cap <= 30000,
                 Stock.catalyst_score >= 45, Stock.current_price.isnot(None),
                 Stock.current_price > 0)
        ).order_by(desc(Stock.catalyst_score)).limit(20).all()
        for s in all_stocks:
            if s in gems: continue
            rg = s.revenue_growth or 0
            if rg in (3.0, 2.0) or rg > 4.0: rg = 0
            missing = []; match_score = 0
            if s.catalyst_score >= 60:   match_score += 30
            elif s.catalyst_score >= 50: match_score += 20; missing.append('Catalyst أقل من المطلوب')
            else:                        match_score += 10; missing.append('Catalyst منخفض')
            if rg >= 0.15:               match_score += 35
            elif rg >= 0.05:             match_score += 20; missing.append('نمو الإيرادات يحتاج تحسين')
            else:                        match_score += 5;  missing.append('نمو الإيرادات غير كافٍ')
            if s.market_cap and s.market_cap <= 20000:   match_score += 25
            elif s.market_cap and s.market_cap <= 30000: match_score += 15; missing.append('القيمة السوقية أعلى قليلاً')
            if s.debt_to_equity and s.debt_to_equity <= 0.5: match_score += 10
            elif not s.debt_to_equity: match_score += 5
            else: missing.append('الدين مرتفع نسبياً')
            if match_score >= 40:
                candidates.append({
                    'stock': s, 'match_score': min(99, match_score), 'missing': missing[:2],
                    'status': ('🟢 ينقصه شرط واحد' if len(missing) <= 1 else
                               '🟡 قريب جداً' if len(missing) == 2 else '🔴 يحتاج مزيداً من النمو'),
                })
        candidates.sort(key=lambda x: x['match_score'], reverse=True)
        candidates = candidates[:8]

    return render_template('pages/hidden_gems.html', gems=gems, candidates=candidates)

@dashboard_bp.route('/smart-flow')
def smart_flow():
    stocks = Stock.query.filter(Stock.catalyst_score >= 50).order_by(desc(Stock.catalyst_score)).limit(30).all()
    return render_template('pages/smart_flow.html', stocks=stocks)

@dashboard_bp.route('/portfolio-builder')
def portfolio_builder():
    stocks = Stock.query.filter(Stock.catalyst_score >= 55).order_by(Stock.catalyst_score.desc()).limit(30).all()
    return render_template('pages/portfolio_builder.html', stocks=stocks)

@dashboard_bp.route('/watchlist')
def watchlist():
    entries = WatchlistEntry.query.order_by(desc(WatchlistEntry.added_at)).all()
    return render_template('pages/watchlist.html', entries=entries)

@dashboard_bp.route('/catalyst-radar')
def catalyst_radar():
    from app.services.catalyst_radar import get_radar_stocks
    stocks       = Stock.query.filter(Stock.catalyst_score >= 45).all()
    radar_stocks = get_radar_stocks(stocks, min_signals=2)
    return render_template('pages/catalyst_radar.html', radar_stocks=radar_stocks)

@dashboard_bp.route('/signals')
def trade_signals():
    from app.services.signal_engine import get_all_signals
    stocks = Stock.query.filter(
        Stock.current_price.isnot(None), Stock.current_price > 0,
        Stock.catalyst_score >= 45
    ).all()
    signals = get_all_signals(stocks, min_strength=40)
    return render_template('pages/trade_signals.html', signals=signals)

@dashboard_bp.route('/report/<symbol>')
def full_report(symbol):
    from app.services.fmp_service import fmp_service
    symbol = symbol.upper()
    stock  = Stock.query.filter_by(symbol=symbol).first()
    r = fmp_service.get_comprehensive_report(symbol, stock_db=stock)
    return render_template('pages/full_report.html', r=r)

@dashboard_bp.route('/backtest')
def backtest():
    """
    صفحة التتبع الأمامي (Forward Testing).
    تعرض نتائج حقيقية من الإشارات المُتتبَّعة — لا أرقام وهمية.
    تتعامل مع حالة 'لا نتائج بعد' بأمان.
    """
    try:
        from app.services.signal_tracker import get_tracker_stats
        stats = get_tracker_stats()
    except Exception as e:
        stats = {
            'available': False,
            'reason': f'النظام قيد التهيئة: {str(e)[:120]}',
            'open_count': 0,
            'closed_count': 0,
        }

    # ضمان وجود كل المفاتيح التي قد يحتاجها القالب (تجنّب أخطاء None)
    safe = {
        'available':     stats.get('available', False),
        'reason':        stats.get('reason', ''),
        'open_count':    stats.get('open_count', 0) or 0,
        'closed_count':  stats.get('closed_count', 0) or 0,
        'win_count':     stats.get('win_count', 0) or 0,
        'loss_count':    stats.get('loss_count', 0) or 0,
        'win_rate':      stats.get('win_rate') if stats.get('win_rate') is not None else 0,
        'avg_return':    stats.get('avg_return') if stats.get('avg_return') is not None else 0,
        'avg_win':       stats.get('avg_win') if stats.get('avg_win') is not None else 0,
        'avg_loss':      stats.get('avg_loss') if stats.get('avg_loss') is not None else 0,
        'total_return':  stats.get('total_return') if stats.get('total_return') is not None else 0,
        'profit_factor': stats.get('profit_factor') if stats.get('profit_factor') is not None else 0,
        'best_trade':    stats.get('best_trade'),
        'worst_trade':   stats.get('worst_trade'),
        'note':          stats.get('note', ''),
        'generated_at':  stats.get('generated_at', ''),
        # توافق مع القالب القديم
        'total_signals': stats.get('closed_count', 0) or 0,
        'is_demo':       False,
        'is_estimated':  False,
    }

    # جلب قائمة الإشارات لعرضها في الصفحة
    open_signals = []
    closed_signals = []
    try:
        from app.models.models import SignalSnapshot
        open_signals = SignalSnapshot.query.filter_by(status='open').order_by(
            desc(SignalSnapshot.created_at)).limit(50).all()
        closed_signals = SignalSnapshot.query.filter(
            SignalSnapshot.status != 'open').order_by(
            desc(SignalSnapshot.created_at)).limit(50).all()
    except Exception:
        pass

    return render_template('pages/backtesting.html', stats=safe,
                           open_signals=open_signals,
                           closed_signals=closed_signals)

@dashboard_bp.route('/daily-report')
def daily_report():
    from app.services.finviz_scanner import get_finviz_top10_report
    try:
        report = get_finviz_top10_report()
    except Exception as e:
        report = {'top10': [], 'total_scanned': 0, 'generated_at': '', 'date': '', 'error': str(e)}
    return render_template('pages/daily_report.html', report=report)

@dashboard_bp.route('/news')
def news():
    finnhub_key = os.environ.get('FINNHUB_API_KEY', '')
    return render_template('pages/news.html', finnhub_key=finnhub_key)

@dashboard_bp.route('/compare')
def compare():
    return render_template('pages/compare.html')

@dashboard_bp.route('/technical-alerts')
def technical_alerts():
    return render_template('pages/technical_alerts.html')

@dashboard_bp.route('/markets')
def markets():
    import os
    finnhub_key = os.environ.get('FINNHUB_API_KEY', '')
    return render_template('pages/markets.html', finnhub_key=finnhub_key)

@dashboard_bp.route('/screener')
def screener():
    return render_template('pages/screener.html')
