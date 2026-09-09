from decimal import Decimal
from flask import request, url_for, session
from app import app, db, Withdrawal, admin_required, current_user, page

def _remove_rule(rule_path, endpoint):
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == rule_path and rule.endpoint == endpoint:
            try: app.url_map._rules.remove(rule)
            except ValueError: pass
            try: app.url_map._rules_by_endpoint[endpoint].remove(rule)
            except (KeyError, ValueError): pass
    app.view_functions.pop(endpoint, None)

_remove_rule('/admin/withdrawals', 'admin_withdrawals')

@app.route('/admin/withdrawals', endpoint='admin_withdrawals')
@admin_required
def compact_admin_withdrawals():
    items = Withdrawal.query.order_by(Withdrawal.id.desc()).limit(100).all()
    cards=[]
    for w in items:
        if w.status == 'pending':
            actions = f'''<div class="actions compact-actions">
                <form method="post" action="/admin/withdrawal/{w.id}/approve"><button class="btn success">✓ Terima</button></form>
                <form method="post" action="/admin/withdrawal/{w.id}/reject" class="reject-form"><input class="input reason" name="reason" placeholder="Alasan penolakan"><button class="btn danger">✕ Tolak</button></form>
            </div>'''
        else:
            actions = f'<div class="status-line">Sudah diproses · <span class="pill {w.status}">{w.status}</span></div>'
        cards.append(f'''<article class="review-card">
            <div class="review-head"><div><strong>Withdraw #{w.id}</strong><div class="muted small">{w.created_at}</div></div><span class="pill {w.status}">{w.status}</span></div>
            <div class="review-grid">
              <div><span class="label">User</span><a class="user-chip" href="/admin/user/{w.user.id}">@{w.user.username}</a><span class="muted small">ID {w.user.id}</span></div>
              <div><span class="label">Nominal</span><strong class="amount">Rp {Decimal(w.amount):,.0f}</strong></div>
              <div><span class="label">Tujuan</span><span class="value">{w.destination}</span></div>
              <div><span class="label">Catatan</span><span class="value">{w.note or '-'}</span></div>
            </div>{actions}
        </article>''')
    body=f'''<div class="top"><div><div class="muted">ADMIN · WITHDRAW</div><h1>Withdraw</h1><p class="muted">Review cepat tanpa tabel lebar.</p></div><a class="btn secondary" href="/admin">← Admin</a></div>
    <div class="review-list">{''.join(cards) or '<div class="card muted">Belum ada pengajuan withdraw.</div>'}</div>'''
    return page(body,'Withdraw',True)

@app.route('/profile')
def profile():
    u=current_user()
    if not u:
        from flask import redirect
        return redirect(url_for('login'))
    tx = sorted(u.transactions, key=lambda x: x.id, reverse=True)[:20]
    body=f'''<div class="top"><div><div class="muted">USER</div><h1>Profil Saya</h1></div><a class="btn secondary" href="/dashboard">← Dashboard</a></div>
    <div class="grid"><div class="card"><div class="muted small">USERNAME</div><h2>@{u.username}</h2><div class="muted">User ID: <b>{u.id}</b></div></div><div class="card"><div class="muted small">SALDO</div><div class="big">Rp {Decimal(u.balance):,.0f}</div><a class="btn" href="/withdraw" style="margin-top:12px">Withdraw</a></div></div>
    <div class="card" style="margin-top:16px"><h3>Riwayat Transaksi</h3><div style="display:grid;gap:8px">{''.join(f'<div class="status-box"><b>Rp {Decimal(t.amount):,.0f}</b> · {t.kind}<div class="muted small">{t.created_at}</div><div class="small">{t.note}</div></div>' for t in tx) or '<div class="muted">Belum ada transaksi.</div>'}</div></div>'''
    return page(body,'Profil Saya')

@app.route('/logout', endpoint='logout')
def logout():
    session.clear()
    return __import__('flask').redirect(url_for('login'))

@app.after_request
def add_ui_navigation(response):
    if response.content_type and 'text/html' in response.content_type and response.status_code == 200:
        html = response.get_data(as_text=True)
        u = current_user()
        if u and 'ui-bottom-nav' not in html:
            if u.username == __import__('os').getenv('ADMIN_USERNAME','admin'):
                links = [('/dashboard','⌂','Dashboard'),('/submit','＋','Ajukan'),('/admin/withdrawals','↳','Withdraw'),('/admin/users','♙','User'),('/admin','▦','Admin'),('/logout','↪','Keluar')]
            else:
                links = [('/dashboard','⌂','Dashboard'),('/submit','＋','Ajukan'),('/withdraw','↳','Withdraw'),('/profile','♙','User'),('/rules','☰','Aturan'),('/logout','↪','Keluar')]
            nav=''.join(f'<a class="bottom-item {"active" if request.path==p else ""}" href="{p}"><span class="bottom-icon">{ic}</span><span>{label}</span></a>' for p,ic,label in links)
            extra='''<style>
            body{padding-bottom:82px}.navlinks{display:none!important}
            .ui-bottom-nav{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:100;width:min(680px,calc(100% - 24px));background:rgba(17,26,42,.96);backdrop-filter:blur(14px);border:1px solid #34445f;border-radius:20px;padding:8px;display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:4px;box-shadow:0 12px 35px #0003}
            .bottom-item{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:52px;border-radius:14px;color:#aab5c7;font-size:11px;font-weight:700;transition:.15s}.bottom-item:hover,.bottom-item.active{background:#26344b;color:#fff}.bottom-icon{font-size:20px;line-height:20px}
            .review-list{display:grid;gap:12px}.review-card{background:#172236;border:1px solid #293750;border-radius:18px;padding:16px}.review-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px}.review-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.review-grid>div{background:#111a2a;border-radius:12px;padding:11px;min-width:0}.label{display:block;color:#8f9bb0;font-size:11px;text-transform:uppercase;margin-bottom:4px}.value{display:block;overflow-wrap:anywhere}.amount{font-size:18px}.user-chip{display:inline-block;margin-right:7px;color:#fff;font-weight:800}.compact-actions{margin-top:14px;align-items:stretch}.compact-actions form{margin:0}.compact-actions .btn{height:44px}.reject-form{display:flex;gap:7px;flex:1;min-width:220px}.reject-form .reason{margin:0;flex:1;min-width:0}.status-line{margin-top:12px;color:#aab5c7}
            @media(max-width:650px){.review-grid{grid-template-columns:1fr}.reject-form{min-width:100%}.compact-actions{display:grid}.compact-actions>form:first-child{width:100%}.compact-actions>form:first-child .btn{width:100%}.reject-form .btn{white-space:nowrap}.ui-bottom-nav{bottom:8px;border-radius:18px}.bottom-item{min-height:50px;font-size:10px}.bottom-icon{font-size:18px}}
            </style><nav id="ui-bottom-nav" class="ui-bottom-nav">'''+nav+'''</nav>'''
            html = html.replace('</body>', extra+'</body>')
            response.set_data(html)
    return response