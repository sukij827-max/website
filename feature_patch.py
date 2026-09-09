from decimal import Decimal, InvalidOperation
from flask import request, redirect, url_for, flash
from app import app, db, User, Batch, EmailSubmission, Transaction, admin_required, login_required, current_user, page

class EmailCountAdjustment(db.Model):
    __tablename__ = 'email_count_adjustment'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship('User', backref='email_count_adjustments')

with app.app_context():
    db.create_all()

def accepted_count(user_id):
    actual = EmailSubmission.query.join(Batch).filter(
        Batch.user_id == user_id,
        EmailSubmission.status == 'accepted'
    ).count()
    adjustment = db.session.query(db.func.coalesce(db.func.sum(EmailCountAdjustment.amount), 0)).filter(
        EmailCountAdjustment.user_id == user_id
    ).scalar() or 0
    return actual, int(adjustment), max(0, actual + int(adjustment))

def remove_rule(rule_path, endpoint):
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == rule_path and rule.endpoint == endpoint:
            try: app.url_map._rules.remove(rule)
            except ValueError: pass
            try: app.url_map._rules_by_endpoint[endpoint].remove(rule)
            except (KeyError, ValueError): pass
    app.view_functions.pop(endpoint, None)

# Replace dashboard with a compact version that highlights accepted/sold email count
remove_rule('/dashboard', 'dashboard')
@app.route('/dashboard', endpoint='dashboard')
@login_required
def dashboard_feature():
    u = current_user()
    actual, adjustment, accepted_total = accepted_count(u.id)
    tx = Transaction.query.filter_by(user_id=u.id).order_by(Transaction.id.desc()).limit(10).all()
    batches = Batch.query.filter_by(user_id=u.id).order_by(Batch.id.desc()).limit(20).all()
    referrals = None
    try:
        from referral_patch import Referral
        referrals = Referral.query.filter_by(inviter_id=u.id).order_by(Referral.id.desc()).all()
        referral_total = sum((Decimal(r.total_reward) for r in referrals), Decimal('0'))
    except Exception:
        referrals = []
        referral_total = Decimal('0')
    rows = ''.join(
        f'<tr><td>#{b.id}</td><td>{b.created_at}</td><td>{len(b.emails)}</td>'
        f'<td>{sum(e.status=="accepted" for e in b.emails)}</td>'
        f'<td>{sum(e.status=="rejected" for e in b.emails)}</td>'
        f'<td>Rp {sum(Decimal(e.payout or 0) for e in b.emails):,.0f}</td></tr>'
        for b in batches
    )
    tx_rows = ''.join(
        f'<tr><td>{t.created_at}</td><td>{t.kind}</td><td>Rp {Decimal(t.amount):,.0f}</td><td>{t.note}</td></tr>'
        for t in tx
    )
    referral_text = (
        f'{len(referrals)} teman sudah terhubung · Bonus terkumpul Rp {referral_total:,.0f}'
        if referrals else 'Ajak teman dan dapatkan Rp 1.000 untuk setiap email teman yang diterima admin.'
    )
    body = f'''<div class="top"><div><div class="muted small">Halo, {u.username}</div><h1>Dashboard</h1></div><div class="actions"><a class="btn" href="/submit">+ Ajukan Email</a><a class="btn secondary" href="/withdraw">Withdraw</a></div></div>
    <div class="grid">
      <div class="card"><div class="muted">Saldo tersedia</div><div class="big">Rp {Decimal(u.balance):,.0f}</div></div>
      <div class="card"><div class="muted">Harga aktif / email</div><div class="big">Rp {price_value():,.0f}</div></div>
      <div class="card"><div class="muted">Email diterima admin</div><div class="big">{accepted_total}</div><p class="muted small" style="margin-bottom:0">Hanya email berstatus diterima yang dihitung sebagai email terjual.</p></div>
    </div>
    <div class="card" style="margin-top:16px;border:1px solid #dfe3ea"><div class="top"><div><div class="muted small">PROGRAM REFERRAL</div><h3 style="margin:4px 0">Undang Teman</h3><p class="muted" style="margin:0;line-height:1.6">{referral_text}</p><p class="muted small" style="margin:8px 0 0">Setiap 1 email teman yang <b>diterima admin</b> = Rp 1.000. Jadi 10 email = Rp 10.000. Bonus masuk ke saldo setelah email teman benar-benar diterima admin.</p></div><a class="btn" href="/referral">Undang Teman</a></div></div>
    <div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan</h3><table class="table"><tr><th>Batch</th><th>Tanggal</th><th>Email</th><th>Diterima</th><th>Ditolak</th><th>Payout</th></tr>{rows or '<tr><td colspan="6" class="muted">Belum ada pengajuan.</td></tr>'}</table></div>
    <div class="card" style="margin-top:16px"><div class="top"><h3>Transaksi Terbaru</h3><a class="btn secondary" href="/profile">Profil</a></div><table class="table"><tr><th>Tanggal</th><th>Jenis</th><th>Nominal</th><th>Catatan</th></tr>{tx_rows or '<tr><td colspan="4" class="muted">Belum ada transaksi.</td></tr>'}</table></div>'''
    return page(body, 'Dashboard')

def price_value():
    from app import price
    return price()

# Replace admin user detail with accepted count + manual correction control
remove_rule('/admin/user/<int:uid>', 'admin_user')
@app.route('/admin/user/<int:uid>', methods=['GET','POST'], endpoint='admin_user')
@admin_required
def admin_user_feature(uid):
    u = db.get_or_404(User, uid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'email_count_adjust':
            try:
                amount = int(request.form.get('amount', '0'))
            except (ValueError, TypeError):
                amount = 0
            note = request.form.get('note', '').strip()[:500]
            if amount == 0:
                flash('Jumlah koreksi tidak boleh 0.')
            elif not note:
                flash('Alasan koreksi wajib diisi.')
            else:
                actual, adjustment, total_before = accepted_count(u.id)
                if total_before + amount < 0:
                    flash('Koreksi tidak dapat membuat jumlah email diterima menjadi negatif.')
                else:
                    db.session.add(EmailCountAdjustment(user_id=u.id, amount=amount, note=note))
                    db.session.commit()
                    flash(f'Jumlah email diterima untuk {u.username} berhasil dikoreksi {amount:+d}.')
        elif action == 'balance':
            try: amount = Decimal(request.form.get('balance_amount','0'))
            except InvalidOperation: amount = Decimal('0')
            note = request.form.get('balance_note','Penyesuaian saldo manual').strip()[:500]
            if amount == 0: flash('Nominal saldo tidak boleh 0.')
            else:
                u.balance = Decimal(u.balance) + amount
                db.session.add(Transaction(user_id=u.id, amount=amount, kind='manual_adjustment', note=note or 'Penyesuaian saldo manual'))
                db.session.commit(); flash('Saldo berhasil diperbarui.')
        elif action == 'ban':
            if u.username == __import__('os').getenv('ADMIN_USERNAME','admin'): flash('Akun admin tidak dapat diblokir dari panel ini.')
            else: u.is_banned=True; db.session.commit(); flash(f'User {u.username} berhasil diblokir.')
        elif action == 'unban':
            u.is_banned=False; db.session.commit(); flash(f'User {u.username} berhasil dibuka blokirnya.')
    actual, adjustment, accepted_total = accepted_count(u.id)
    tx = Transaction.query.filter_by(user_id=u.id).order_by(Transaction.id.desc()).limit(50).all()
    batches = Batch.query.filter_by(user_id=u.id).order_by(Batch.id.desc()).limit(50).all()
    emails = EmailSubmission.query.join(Batch).filter(Batch.user_id==u.id).order_by(EmailSubmission.id.desc()).limit(100).all()
    adjustments = EmailCountAdjustment.query.filter_by(user_id=u.id).order_by(EmailCountAdjustment.id.desc()).limit(30).all()
    body = f'''<div class="top"><div><div class="muted">USER #{u.id}</div><h1>{u.username}</h1><p>Status: <span class="pill {"banned" if u.is_banned else "accepted"}">{"BANNED" if u.is_banned else "AKTIF"}</span> · Saldo: <b>Rp {Decimal(u.balance):,.0f}</b></p></div><a class="btn secondary" href="/admin/users">← Kembali</a></div>
    <div class="grid">
      <div class="card"><div class="muted">Email diterima admin</div><div class="big">{accepted_total}</div><p class="muted small">Aktual dari sistem: {actual} · Koreksi admin: {adjustment:+d}</p></div>
      <div class="card"><div class="muted">Total email diajukan</div><div class="big">{len(emails)}</div><p class="muted small">Email pending/ditolak tidak masuk hitungan terjual.</p></div>
      <div class="card"><div class="muted">Saldo</div><div class="big">Rp {Decimal(u.balance):,.0f}</div></div>
    </div>
    <div class="grid" style="margin-top:16px">
      <div class="card"><h3>Koreksi Jumlah Email Diterima</h3><p class="muted small">Gunakan jika ada kesalahan data. Positif untuk menambah, negatif untuk mengurangi. Koreksi ini hanya memperbaiki angka statistik dan tidak membuat payout/referral bonus baru.</p><form method="post"><input type="hidden" name="action" value="email_count_adjust"><label>Jumlah koreksi</label><input class="input" name="amount" type="number" step="1" required placeholder="Contoh: 5 atau -1"><label>Alasan</label><input class="input" name="note" required placeholder="Koreksi data email diterima"><button class="btn">Simpan Koreksi</button></form></div>
      <div class="card"><h3>Tambah / Kurangi Saldo</h3><form method="post"><input type="hidden" name="action" value="balance"><label>Nominal</label><input class="input" name="balance_amount" type="number" step="0.01" required placeholder="5000"><label>Alasan</label><input class="input" name="balance_note" required placeholder="Koreksi saldo"><button class="btn">Simpan Saldo</button></form></div>
    </div>
    <div class="card" style="margin-top:16px"><h3>Riwayat Koreksi Jumlah Email</h3><table class="table"><tr><th>Tanggal</th><th>Koreksi</th><th>Alasan</th></tr>{''.join(f'<tr><td>{a.created_at}</td><td>{a.amount:+d}</td><td>{a.note}</td></tr>' for a in adjustments) or '<tr><td colspan="3" class="muted">Belum ada koreksi.</td></tr>'}</table></div>
    <div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan</h3><table class="table"><tr><th>Batch</th><th>Tanggal</th><th>Email</th><th>Diterima</th><th>Ditolak</th><th>Pending</th><th>Aksi</th></tr>{''.join(f'<tr><td>#{b.id}</td><td>{b.created_at}</td><td>{len(b.emails)}</td><td>{sum(e.status=="accepted" for e in b.emails)}</td><td>{sum(e.status=="rejected" for e in b.emails)}</td><td>{sum(e.status=="pending" for e in b.emails)}</td><td><a class="btn secondary" href="/admin/batch/{b.id}">Lihat</a></td></tr>' for b in batches) or '<tr><td colspan="7" class="muted">Belum ada pengajuan.</td></tr>'}</table></div>
    <div class="card" style="margin-top:16px"><h3>Detail Email</h3><table class="table"><tr><th>Email</th><th>Batch</th><th>Status</th><th>Payout</th><th>Alasan</th><th>Review</th></tr>{''.join(f'<tr><td>{e.email}</td><td>#{e.batch_id}</td><td><span class="pill {e.status}">{e.status}</span></td><td>Rp {Decimal(e.payout or 0):,.0f}</td><td>{e.rejection_reason or "-"}</td><td>{e.reviewed_at or "-"}</td></tr>' for e in emails) or '<tr><td colspan="6" class="muted">Belum ada email.</td></tr>'}</table></div>
    <div class="card" style="margin-top:16px"><h3>Riwayat Transaksi</h3><table class="table"><tr><th>Tanggal</th><th>Nominal</th><th>Jenis</th><th>Catatan</th></tr>{''.join(f'<tr><td>{t.created_at}</td><td>Rp {Decimal(t.amount):,.0f}</td><td>{t.kind}</td><td>{t.note}</td></tr>' for t in tx) or '<tr><td colspan="4" class="muted">Belum ada transaksi.</td></tr>'}</table></div>'''
    return page(body, 'Kelola User', True)
