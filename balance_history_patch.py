from decimal import Decimal
from flask import Response
from app import app, db, User, Transaction, admin_required

BALANCE_KINDS = {
    'payout': ('Email diterima', 'plus'),
    'referral_bonus': ('Bonus referral', 'plus'),
    'withdrawal_pending': ('Withdraw', 'minus'),
    'withdrawal_refund': ('Refund withdraw', 'plus'),
    'manual_adjustment': ('Koreksi saldo admin', 'adjust'),
}


def balance_history_html(uid):
    u = db.session.get(User, uid)
    if not u:
        return '<div class="muted">User tidak ditemukan.</div>'
    tx = Transaction.query.filter(
        Transaction.user_id == uid,
        Transaction.kind.in_(list(BALANCE_KINDS.keys()))
    ).order_by(Transaction.id.desc()).limit(100).all()
    rows = []
    for t in tx:
        label, direction = BALANCE_KINDS.get(t.kind, (t.kind, 'adjust'))
        amount = Decimal(t.amount or 0)
        sign = '+' if amount > 0 else ''
        cls = 'accepted' if amount > 0 else ('rejected' if amount < 0 else 'pill')
        rows.append(
            f'<div class="balance-tx {direction}">'
            f'<div><b>{label}</b><div class="muted small">{t.created_at} · {t.note}</div></div>'
            f'<strong class="balance-amount">{sign}Rp {amount:,.0f}</strong>'
            f'</div>'
        )
    return (
        f'<div class="balance-live-head"><div><div class="muted small">SALDO SAAT INI</div>'
        f'<div class="big">Rp {Decimal(u.balance):,.0f}</div></div>'
        f'<span class="live-dot">● LIVE</span></div>'
        f'<div class="balance-history-list">'
        + ''.join(rows)
        + ('<div class="muted small">Belum ada perubahan saldo.</div>' if not rows else '')
        + '</div>'
    )


@app.route('/admin/user/<int:uid>/balance-history')
@admin_required
def admin_user_balance_history(uid):
    return Response(balance_history_html(uid), mimetype='text/html')


@app.after_request
def inject_balance_history(response):
    if response.content_type and 'text/html' in response.content_type and response.status_code == 200:
        path = __import__('re').match(r'^/admin/user/(\d+)$', __import__('flask').request.path)
        if path:
            uid = int(path.group(1))
            html = response.get_data(as_text=True)
            if 'id="realtime-balance-history"' not in html:
                initial = balance_history_html(uid)
                card = f'''<div class="card" style="margin-top:16px" id="realtime-balance-history-card">
                <div class="top"><div><h3 style="margin-bottom:4px">Riwayat Perubahan Saldo</h3><p class="muted small" style="margin:0">Khusus transaksi yang benar-benar mengubah saldo user. Diperbarui otomatis setiap 5 detik.</p></div></div>
                <div id="realtime-balance-history">{initial}</div>
                </div>
                <style>
                .balance-live-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid #293750;margin-bottom:8px}.live-dot{font-size:11px;font-weight:800;color:#6ee7a3}.balance-history-list{display:grid;gap:7px;max-height:520px;overflow:auto}.balance-tx{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px;border-radius:12px;background:#111a2a;border:1px solid #293750}.balance-tx.plus .balance-amount{color:#6ee7a3}.balance-tx.minus .balance-amount{color:#ff8585}.balance-tx.adjust .balance-amount{color:#ffd66e}.balance-amount{white-space:nowrap}.balance-tx .small{margin-top:3px;overflow-wrap:anywhere}@media(max-width:650px){.balance-tx{align-items:flex-start;flex-direction:column}.balance-amount{font-size:16px}}
                </style>
                <script>
                (function(){{
                  const box=document.getElementById('realtime-balance-history');
                  async function refreshBalanceHistory(){{
                    try{{
                      const r=await fetch('/admin/user/{uid}/balance-history?t='+Date.now(),{{cache:'no-store'}});
                      if(r.ok) box.innerHTML=await r.text();
                    }}catch(e){{}}
                  }}
                  setInterval(refreshBalanceHistory,5000);
                }})();
                </script>'''
                marker='</body>'
                html=html.replace(marker,card+marker,1)
                response.set_data(html)
    return response
