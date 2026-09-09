from decimal import Decimal
from flask import request, session, url_for, flash
from sqlalchemy.exc import IntegrityError
from app import app, db, User, EmailSubmission, Batch, Transaction, Withdrawal, admin_required, login_required, current_user, page

REFERRAL_REWARD = Decimal('1000')
MIN_WITHDRAW = Decimal('10500')

class Referral(db.Model):
    __tablename__ = 'referral'
    id = db.Column(db.Integer, primary_key=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    referred_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    rewarded_emails = db.Column(db.Integer, nullable=False, default=0)
    total_reward = db.Column(db.Numeric(14,2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    inviter = db.relationship('User', foreign_keys=[inviter_id], backref='referrals_sent')
    referred_user = db.relationship('User', foreign_keys=[referred_user_id], backref='referral_source', uselist=False)

with app.app_context():
    db.create_all()

@app.before_request
def capture_referral():
    ref = request.args.get('ref', '').strip()
    if ref and not current_user():
        try:
            uid = int(ref)
            if User.query.get(uid):
                session['referrer_id'] = uid
        except (ValueError, TypeError):
            pass

@app.before_request
def attach_referral_after_login():
    uid = session.get('user_id')
    refid = session.get('referrer_id')
    if not uid or not refid or uid == refid:
        return
    if Referral.query.filter_by(referred_user_id=uid).first():
        session.pop('referrer_id', None)
        return
    inviter = db.session.get(User, refid)
    referred = db.session.get(User, uid)
    if inviter and referred:
        try:
            db.session.add(Referral(inviter_id=inviter.id, referred_user_id=referred.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
        session.pop('referrer_id', None)

def sync_referral_rewards(user_id):
    referral = Referral.query.filter_by(referred_user_id=user_id).first()
    if not referral:
        return 0
    accepted_count = EmailSubmission.query.join(Batch).filter(
        Batch.user_id == user_id, EmailSubmission.status == 'accepted'
    ).count()
    if accepted_count <= referral.rewarded_emails:
        return 0
    delta = accepted_count - referral.rewarded_emails
    bonus = REFERRAL_REWARD * delta
    referral.rewarded_emails = accepted_count
    referral.total_reward = Decimal(referral.total_reward) + bonus
    referral.inviter.balance = Decimal(referral.inviter.balance) + bonus
    db.session.add(Transaction(
        user_id=referral.inviter.id,
        amount=bonus,
        kind='referral_bonus',
        note=f'Bonus referral {delta} email dari {referral.referred_user.username}'
    ))
    db.session.commit()
    return delta

@app.before_request
def auto_sync_referral():
    u = current_user()
    if u and request.endpoint != 'static':
        try:
            sync_referral_rewards(u.id)
        except Exception:
            db.session.rollback()

@app.before_request
def sync_after_admin_review():
    if current_user() and current_user().username == __import__('os').getenv('ADMIN_USERNAME', 'admin') and request.endpoint in ('accept', 'reject', 'bulk_review', 'batch_bulk'):
        try:
            for r in Referral.query.all():
                sync_referral_rewards(r.referred_user_id)
        except Exception:
            db.session.rollback()

@app.after_request
def add_referral_nav(response):
    if response.content_type and response.content_type.startswith('text/html'):
        body = response.get_data(as_text=True)
        if '/referral' not in body:
            body = body.replace('<a href="/withdraw">Withdraw</a>', '<a href="/withdraw">Withdraw</a><a href="/referral">Undang Teman</a>')
        if '/admin/referrals' not in body and 'Admin' in body:
            body = body.replace('<a href="/admin">Admin</a>', '<a href="/admin">Admin</a><a href="/admin/referrals">Referral</a>')
        response.set_data(body)
    return response

@app.route('/referral')
@login_required
def referral_page():
    u = current_user()
    link = request.url_root.rstrip('/') + f'/register?ref={u.id}'
    referrals = Referral.query.filter_by(inviter_id=u.id).order_by(Referral.id.desc()).all()
    total = sum((Decimal(r.total_reward) for r in referrals), Decimal('0'))
    rows = ''.join(
        f'<tr><td>{r.referred_user.username}</td><td>{r.referred_user.id}</td><td>{r.rewarded_emails}</td><td>Rp {Decimal(r.total_reward):,.0f}</td></tr>'
        for r in referrals
    )
    body = f'''<div class="top"><div><div class="muted">PROGRAM REFERRAL</div><h1>Undang Teman</h1><p class="muted">Setiap <b>1 email yang diterima</b> dari teman yang kamu undang memberikan <b>Rp 1.000</b>. Jadi 10 email = Rp 10.000.</p></div><a class="btn secondary" href="/dashboard">← Kembali</a></div><div class="card"><h3>Link Referral Kamu</h3><input class="input" value="{link}" readonly onclick="this.select()"><p class="muted small">Bagikan link ini. Teman harus mendaftar melalui link tersebut agar tercatat sebagai referral.</p></div><div class="grid"><div class="card"><div class="muted">Teman diundang</div><div class="big">{len(referrals)}</div></div><div class="card"><div class="muted">Total bonus referral</div><div class="big">Rp {total:,.0f}</div></div></div><div class="card" style="margin-top:16px"><h3>Riwayat Referral</h3><table class="table"><tr><th>Username</th><th>User ID</th><th>Email diterima</th><th>Bonus</th></tr>{rows or '<tr><td colspan="4" class="muted">Belum ada teman yang mendaftar.</td></tr>'}</table></div>'''
    return page(body, 'Referral')

def patched_withdraw():
    u = current_user()
    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount','0')).quantize(Decimal('0.01'))
        except Exception:
            amount = Decimal('0')
        destination = request.form.get('destination','').strip()[:255]
        note = request.form.get('note','').strip()[:500]
        if amount < MIN_WITHDRAW:
            flash('Minimal withdraw adalah Rp 10.500.')
        elif amount > Decimal(u.balance):
            flash('Saldo tidak mencukupi untuk withdraw tersebut.')
        elif not destination:
            flash('Masukkan tujuan withdraw.')
        else:
            u.balance = Decimal(u.balance) - amount
            w = Withdrawal(user_id=u.id, amount=amount, destination=destination, status='pending', note=note)
            db.session.add(w); db.session.flush()
            db.session.add(Transaction(user_id=u.id, amount=-amount, kind='withdrawal_pending', note=f'Withdraw #{w.id} diajukan'))
            db.session.commit()
            flash(f'Withdraw #{w.id} berhasil diajukan ke admin.')
            return redirect(url_for('withdraw'))
    items = Withdrawal.query.filter_by(user_id=u.id).order_by(Withdrawal.id.desc()).limit(50).all()
    rows = ''.join(f'<tr><td>#{w.id}</td><td>{w.created_at}</td><td>Rp {Decimal(w.amount):,.0f}</td><td>{w.destination}</td><td><span class="pill {w.status}">{w.status}</span></td><td>{w.admin_note or "-"}</td></tr>' for w in items)
    body = f'''<div class="top"><div><div class="muted">SALDO · WITHDRAW</div><h1>Ajukan Withdraw</h1><p class="muted">Saldo: <b>Rp {Decimal(u.balance):,.0f}</b> · Minimal withdraw <b>Rp 10.500</b>.</p></div><a class="btn secondary" href="/dashboard">← Kembali</a></div><div class="card"><form method="post"><label>Nominal Withdraw (Rp)</label><input class="input" name="amount" type="number" min="10500" step="1" max="{Decimal(u.balance):.0f}" required placeholder="10500"><label>Tujuan Withdraw</label><input class="input" name="destination" required placeholder="DANA / GoPay / rekening / tujuan pembayaran"><label>Catatan (opsional)</label><textarea class="input" name="note" placeholder="Contoh: DANA 08xxxxxxxxxx"></textarea><button class="btn">Ajukan ke Admin</button></form></div><div class="card" style="margin-top:16px"><h3>Riwayat Withdraw</h3><table class="table"><tr><th>ID</th><th>Tanggal</th><th>Nominal</th><th>Tujuan</th><th>Status</th><th>Catatan Admin</th></tr>{rows or '<tr><td colspan="6" class="muted">Belum ada pengajuan withdraw.</td></tr>'}</table></div>'''
    return page(body, 'Withdraw')

# Replace the original /withdraw rule from app.py so the minimum is enforced everywhere.
for rule in list(app.url_map.iter_rules()):
    if rule.rule == '/withdraw' and rule.endpoint == 'withdraw':
        app.url_map._rules.remove(rule)
        if 'withdraw' in app.url_map._rules_by_endpoint:
            app.url_map._rules_by_endpoint['withdraw'].remove(rule)
app.view_functions['withdraw'] = patched_withdraw
app.add_url_rule('/withdraw', endpoint='withdraw', view_func=patched_withdraw, methods=['GET','POST'])

@app.route('/admin/referrals')
@admin_required
def admin_referrals():
    refs = Referral.query.order_by(Referral.id.desc()).limit(500).all()
    rows = ''.join(f'<tr><td>{r.inviter.username}</td><td>{r.inviter.id}</td><td>{r.referred_user.username}</td><td>{r.referred_user.id}</td><td>{r.rewarded_emails}</td><td>Rp {Decimal(r.total_reward):,.0f}</td></tr>' for r in refs)
    body = f'''<div class="top"><div><div class="muted">ADMIN · REFERRAL</div><h1>Referral</h1></div><a class="btn secondary" href="/admin">← Kembali</a></div><div class="card"><table class="table"><tr><th>Pengundang</th><th>ID</th><th>Teman</th><th>ID</th><th>Email diterima</th><th>Bonus</th></tr>{rows or '<tr><td colspan="6" class="muted">Belum ada referral.</td></tr>'}</table></div>'''
    return page(body, 'Referral', True)
