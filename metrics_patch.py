from decimal import Decimal, InvalidOperation
from flask import request, redirect, url_for, flash
from app import app, db, User, EmailSubmission, AdminLog, Setting, admin_required

# Homepage statistics can be corrected by the owner without changing real
# marketplace data. Corrections are stored as adjustments and are never used
# for user balances, email payouts, or referral rewards.
DEFAULTS = {
    'homepage_users_adjustment': '0',
    'homepage_emails_adjustment': '0',
    'homepage_security_rate': '98.4',
    'homepage_paid_adjustment': '0',
}

with app.app_context():
    db.create_all()
    changed = False
    for key, value in DEFAULTS.items():
        if not db.session.get(Setting, key):
            db.session.add(Setting(key=key, value=value))
            changed = True
    if changed:
        db.session.commit()

def _num(key, default='0'):
    s = db.session.get(Setting, key)
    try:
        return Decimal(s.value) if s else Decimal(default)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)

def homepage_stats():
    real_users = User.query.filter_by(is_banned=False).count()
    real_accepted = EmailSubmission.query.filter_by(status='accepted').count()
    real_paid = db.session.query(
        db.func.coalesce(db.func.sum(EmailSubmission.payout), 0)
    ).filter(EmailSubmission.status == 'accepted').scalar() or 0

    users = max(0, real_users + int(_num('homepage_users_adjustment')))
    emails = max(0, real_accepted + int(_num('homepage_emails_adjustment')))
    security = max(0, min(100, _num('homepage_security_rate')))
    paid = max(Decimal('0'), Decimal(real_paid) + _num('homepage_paid_adjustment'))
    return users, emails, security, paid

# visual_patch calls its module-level _stats() at request time. Replace only
# that statistics provider; all existing marketplace routes remain unchanged.
try:
    import visual_patch
    def _visual_stats():
        users, emails, security, paid = homepage_stats()
        return users, emails, security, paid
    visual_patch._stats = _visual_stats
except Exception:
    pass

@app.route('/admin/homepage-stats', methods=['GET', 'POST'])
@admin_required
def admin_homepage_stats():
    if request.method == 'POST':
        fields = {
            'homepage_users_adjustment': ('Pengguna Aktif', 'int'),
            'homepage_emails_adjustment': ('Email Diterima', 'int'),
            'homepage_security_rate': ('Tingkat Keamanan', 'decimal'),
            'homepage_paid_adjustment': ('Dana Dibayarkan', 'decimal'),
        }
        errors = []
        values = {}
        for key, (label, kind) in fields.items():
            raw = request.form.get(key, '').strip()
            try:
                value = Decimal(raw)
                if kind == 'int' and value != value.to_integral_value():
                    raise ValueError
                if key == 'homepage_security_rate' and not (Decimal('0') <= value <= Decimal('100')):
                    raise ValueError
                values[key] = str(int(value)) if kind == 'int' else format(value, 'f')
            except (InvalidOperation, ValueError, TypeError):
                errors.append(label)

        if errors:
            flash('Nilai tidak valid: ' + ', '.join(errors) + '.')
        else:
            for key, value in values.items():
                s = db.session.get(Setting, key)
                s.value = value
            db.session.add(AdminLog(
                action='homepage_stats_update',
                detail='Memperbarui koreksi statistik homepage: ' + ', '.join(f'{k}={v}' for k, v in values.items())
            ))
            db.session.commit()
            flash('Statistik homepage berhasil diperbarui.')
        return redirect(url_for('admin_homepage_stats'))

    real_users = User.query.filter_by(is_banned=False).count()
    real_accepted = EmailSubmission.query.filter_by(status='accepted').count()
    real_paid = db.session.query(db.func.coalesce(db.func.sum(EmailSubmission.payout), 0)).filter(
        EmailSubmission.status == 'accepted'
    ).scalar() or 0
    users, emails, security, paid = homepage_stats()

    body = f'''<div class="top"><div><div class="muted">ADMIN · HOMEPAGE</div><h1>Statistik Homepage</h1><p class="muted">Koreksi angka yang tampil di halaman depan jika ada kesalahan data. Koreksi tidak mengubah saldo, payout, atau data transaksi pengguna.</p></div><a class="btn secondary" href="/admin">← Admin</a></div>
    <div class="grid">
      <div class="card"><div class="muted">Pengguna Aktif</div><div class="big">{users:,}</div><p class="muted small">Data asli: {real_users:,} · Koreksi: {int(_num('homepage_users_adjustment')):+d}</p></div>
      <div class="card"><div class="muted">Email Diterima</div><div class="big">{emails:,}</div><p class="muted small">Data asli: {real_accepted:,} · Koreksi: {int(_num('homepage_emails_adjustment')):+d}</p></div>
      <div class="card"><div class="muted">Tingkat Keamanan</div><div class="big">{security:.1f}%</div><p class="muted small">Nilai yang dikontrol admin.</p></div>
      <div class="card"><div class="muted">Dana Dibayarkan</div><div class="big">Rp {paid:,.0f}</div><p class="muted small">Data asli: Rp {Decimal(real_paid):,.0f} · Koreksi: Rp {_num('homepage_paid_adjustment'):,.0f}</p></div>
    </div>
    <div class="card" style="margin-top:16px"><h3>Koreksi Statistik</h3><p class="muted small">Masukkan <b>angka akhir</b>, bukan +/-. Contoh: jika Pengguna Aktif saat ini 120 dan ingin diralat menjadi 125, isi 125. Untuk mengurangi, isi angka yang lebih kecil.</p>
    <form method="post"><div class="grid">
      <div><label>Pengguna Aktif (koreksi)</label><input class="input" name="homepage_users_adjustment" type="number" step="1" value="{int(_num('homepage_users_adjustment'))}" required><div class="muted small">Angka koreksi relatif terhadap data asli.</div></div>
      <div><label>Email Diterima (koreksi)</label><input class="input" name="homepage_emails_adjustment" type="number" step="1" value="{int(_num('homepage_emails_adjustment'))}" required><div class="muted small">Angka koreksi relatif terhadap data asli.</div></div>
      <div><label>Tingkat Keamanan</label><input class="input" name="homepage_security_rate" type="number" step="0.1" min="0" max="100" value="{security:.1f}" required><div class="muted small">0 sampai 100%.</div></div>
      <div><label>Dana Dibayarkan (koreksi)</label><input class="input" name="homepage_paid_adjustment" type="number" step="1" value="{_num('homepage_paid_adjustment')}" required><div class="muted small">Koreksi nominal dari total pembayaran asli.</div></div>
    </div><button class="btn" style="margin-top:16px">Simpan Perubahan</button></form></div>
    <div class="card" style="margin-top:16px"><h3>Cara Kerja Koreksi</h3><ul class="muted"><li>Pengguna Aktif = jumlah user aktif asli + koreksi.</li><li>Email Diterima = jumlah email accepted asli + koreksi.</li><li>Tingkat Keamanan = angka yang kamu tetapkan.</li><li>Dana Dibayarkan = total payout asli + koreksi.</li><li>Koreksi statistik <b>tidak</b> menambah saldo pengguna dan tidak memicu referral bonus.</li></ul></div>'''
    return __import__('app').page(body, 'Statistik Homepage', True)

@app.after_request
def homepage_stat_labels(response):
    if response.content_type and 'text/html' in response.content_type and response.status_code == 200:
        html = response.get_data(as_text=True)
        html = html.replace('Email Diproses', 'Email Diterima')
        html = html.replace('Tingkat Disetujui', 'Tingkat Keamanan')
        html = html.replace('Total Dibayarkan', 'Dana Dibayarkan')
        # Make the admin shortcut visible without creating another menu item.
        if '/admin/homepage-stats' not in html and '/admin' in html:
            marker = '<a class="btn secondary" href="/admin/settings">'
            pos = html.find(marker)
            if pos != -1:
                end = html.find('</a>', pos)
                if end != -1:
                    end += 4
                    html = html[:end] + ' <a class="btn secondary" href="/admin/homepage-stats">▦ Statistik Homepage</a>' + html[end:]
        response.set_data(html)
    return response
