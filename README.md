# 🔍 Insider Tracker Pro

تتبع صفقات المطلعين (CEOs, Directors) في الأسهم الأمريكية لحظة بلحظة.

## التشغيل المحلي
```bash
pip install -r requirements.txt
cp .env.example .env
# أضف FINNHUB_API_KEY في .env
python run.py
```

## النشر على Railway
```bash
git init
git add .
git commit -m "init: Insider Tracker Pro"
# أضف FINNHUB_API_KEY في Railway Variables
```

## الصفحات
- `/` — آخر صفقات المطلعين
- `/stock/NVDA` — تفاصيل سهم معين
- `/leaderboard` — أعلى الأسهم شراءً
- `/screener` — الفلتر الذكي
