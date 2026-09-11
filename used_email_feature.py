"""Fresh/used email submission extension.
Adds a separate used-email intake while keeping the existing review/payout flow.
"""
from flask import request, redirect, url_for
from sqlalchemy import text
from decimal import Decimal
import html
import app as core

# Store the category separately so this extension does not alter existing data columns.
def ensure_category_table():
    with core.app.app_context():
        core.db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS email_submission_category (
                submission_id INTEGER PRIMARY KEY,
                category VARCHAR(10) NOT NULL DEFAULT 'fresh'
            )
        '''))
        core.db.session.execute(text("UPDATE email_submission_category SET category='fresh' WHERE category IS NULL OR category NOT IN ('fresh','used')"))
        core.db.session.commit()

ensure_category_table()


def category_for(submission_id):
    row = core.db.session.execute(
        text("SELECT category FROM email_submission_category WHERE submission_id=:id"),
        {"id": submission_id},
    ).first()
    return row[0] if row else "fresh"


def set_category(submission_ids, category):
    for sid in submission_ids:
        core.db.session.execute(
            text("INSERT INTO email_submission_category(submission_id,category) VALUES (:id,:cat) ON CONFLICT(submission_id) DO UPDATE SET category=:cat"),
            {"id": sid, "cat": category},
        )


def submit_used():
    if request.method == 'POST':
        if request.form.get('agree') != 'yes':
            core.flash('Kamu harus menyetujui aturan terlebih dahulu.')
            return redirect(url_for('submit_used'))
        emails = core.normalize_emails(request.form.get('emails',''))
        if not emails:
            core.flash('Masukkan minimal satu alamat email yang valid.')
            return redirect(url_for('submit_used'))
        existing = set(x[0] for x in core.db.session.query(core.EmailSubmission.email).filter(core.EmailSubmission.email.in_(emails)).all())
        if existing:
            sample = ', '.join(sorted(existing)[:5])
            more = ' dan lainnya' if len(existing) > 5 else ''
            core.flash(f'Pengajuan ditolak: email sudah pernah masuk ke marketplace: {sample}{more}.')
            return redirect(url_for('submit_used'))
        b = core.Batch(user_id=core.current_user().id, agreed_rules=True, price_snapshot=core.price())
        core.db.session.add(b)
        core.db.session.flush()
        created = []
        for e in emails:
            item = core.EmailSubmission(batch_id=b.id, email=e)
            core.db.session.add(item)
            core.db.session.flush()
            created.append(item.id)
        set_category(created, 'used')
        try:
            core.db.session.commit()
        except Exception:
            core.db.session.rollback()
            core.flash('Pengajuan gagal disimpan. Silakan cek kembali daftar email.')
            return redirect(url_for('submit_used'))
        core.flash(f'Pengajuan email bekas #{b.id} berhasil dikirim dan menunggu review admin.')
        return redirect(url_for('dashboard'))

    body = '''<div class="hero">
      <div class="muted small">EMAIL BEKAS · REVIEW MANUAL</div>
      <h1>Ajukan Email Bekas</h1>
      <p class="muted">Sistemnya sama seperti pengajuan biasa, tetapi pengajuan ini ditandai khusus sebagai <b>Email Bekas</b> agar admin dapat membedakannya saat review.</p>
      <div class="status-box"><b>Catatan penting</b><br><span class="muted">Masukkan hanya alamat email yang memang kamu miliki dan berhak untuk diserahkan. Jangan masukkan password, OTP, recovery code, atau kredensial lainnya.</span></div>
      <form method="post" style="margin-top:18px"><label>Alamat Email Bekas</label><textarea class="input email-list" name="emails" placeholder="emaillama@example.com\nemailbekas@example.com" required></textarea>
      <label><input type="checkbox" name="agree" value="yes" required> Saya sudah membaca dan menyetujui <a href="/rules"><u>Aturan & Syarat Pengajuan</u></a>.</label>
      <div style="margin-top:18px"><button class="btn">Kirim Email Bekas</button> <a class="btn secondary" href="/dashboard">Kembali</a></div></form></div>'''
    return core.page(body, 'Ajukan Email Bekas')


core.app.add_url_rule('/submit-used', 'submit_used', core.login_required(submit_used), methods=['GET','POST'])


def admin_inventory():
    items = core.EmailSubmission.query.join(core.Batch).order_by(core.EmailSubmission.id.desc()).limit(500).all()
    fresh = sum(category_for(x.id) == 'fresh' for x in items)
    used = sum(category_for(x.id) == 'used' for x in items)
    rows = ''.join(
        f'<tr><td>#{e.id}</td><td>{html.escape(e.email)}</td><td><span class="pill {"approved" if category_for(e.id)=="fresh" else "pending"}">{"FRESH" if category_for(e.id)=="fresh" else "BEKAS"}</span></td><td>{html.escape(e.batch.user.username)}</td><td>{e.batch.user.id}</td><td>#{e.batch_id}</td><td><span class="pill {e.status}">{e.status}</span></td><td>Rp {Decimal(e.payout or 0):,.0f}</td><td><a class="btn secondary" href="/admin/batch/{e.batch_id}">Review</a></td></tr>'
        for e in items
    )
    body = f'''<div class="top"><div><div class="muted">ADMIN · EMAIL INVENTORY</div><h1>Semua Email</h1><p class="muted">Setiap data jelas ditandai sebagai Fresh atau Bekas.</p></div><a class="btn secondary" href="/admin">← Kembali</a></div>
    <div class="mm-dashboard-stats mm-admin-stats"><div class="mm-dstat"><div class="mm-dicon">✉</div><div><span>Total Email</span><strong>{len(items):,}</strong><small>Semua pengajuan</small></div></div><div class="mm-dstat"><div class="mm-dicon">F</div><div><span>Email Fresh</span><strong>{fresh:,}</strong><small>Kategori fresh</small></div></div><div class="mm-dstat"><div class="mm-dicon">B</div><div><span>Email Bekas</span><strong>{used:,}</strong><small>Kategori bekas</small></div></div></div>
    <div class="card" style="margin-top:16px"><table class="table"><tr><th>ID</th><th>Email</th><th>Jenis</th><th>User</th><th>ID User</th><th>Batch</th><th>Status</th><th>Payout</th><th>Aksi</th></tr>{rows or '<tr><td colspan="9" class="muted">Belum ada email.</td></tr>'}</table></div>'''
    return core.page(body, 'Inventory Email', True)

core.app.add_url_rule('/admin/email-inventory', 'admin_email_inventory', core.admin_required(admin_inventory))


# Add navigation links to the existing rendered pages.
_original_dashboard = core.app.view_functions.get('dashboard')
_original_admin = core.app.view_functions.get('admin_dashboard')
_original_pending = core.app.view_functions.get('admin_pending')
_original_batch = core.app.view_functions.get('admin_batch')


def wrap_response(fn, transform):
    def wrapped(*args, **kwargs):
        response = fn(*args, **kwargs)
        if not hasattr(response, 'get_data'):
            return response
        response.set_data(transform(response.get_data(as_text=True)))
        return response
    wrapped.__name__ = getattr(fn, '__name__', 'wrapped')
    return wrapped


def add_user_nav(body):
    link = '<a class="btn secondary" href="/submit-used">Ajukan Email Bekas</a>'
    if '/submit-used' not in body:
        body = body.replace('<a class="btn" href="/submit">+ Ajukan Email</a>', '<a class="btn" href="/submit">+ Email Fresh</a>' + link)
    return body


def add_admin_nav(body):
    link = '<a class="btn secondary" href="/admin/email-inventory">Semua Email · Fresh/Bekas</a>'
    if '/admin/email-inventory' not in body:
        body = body.replace('<a class="btn secondary" href="/admin/pending">Review Email</a>', '<a class="btn secondary" href="/admin/pending">Review Email</a>' + link)
    return body

if _original_dashboard:
    core.app.view_functions['dashboard'] = wrap_response(_original_dashboard, add_user_nav)
if _original_admin:
    core.app.view_functions['admin_dashboard'] = wrap_response(_original_admin, add_admin_nav)


def mark_admin_rows(body):
    # Make the type visible in the pending review table as a badge beside each email.
    for e in core.EmailSubmission.query.filter_by(status='pending').all():
        marker = html.escape(e.email)
        badge = 'FRESH' if category_for(e.id) == 'fresh' else 'BEKAS'
        body = body.replace(f'<td>{marker}</td>', f'<td>{marker}<br><span class="pill {"approved" if badge=="FRESH" else "pending"}">{badge}</span></td>')
    return body

if _original_pending:
    core.app.view_functions['admin_pending'] = wrap_response(_original_pending, mark_admin_rows)


def mark_batch(body):
    # The batch page shows the same Fresh/Bekas badge next to every email.
    bmatch = __import__('re').search(r'/admin/batch/(\d+)', body)
    if not bmatch:
        return body
    bid = int(bmatch.group(1))
    b = core.db.session.get(core.Batch, bid)
    if not b:
        return body
    for e in b.emails:
        marker = html.escape(e.email)
        badge = 'FRESH' if category_for(e.id) == 'fresh' else 'BEKAS'
        body = body.replace(f'<td>{marker}</td>', f'<td>{marker}<br><span class="pill {"approved" if badge=="FRESH" else "pending"}">{badge}</span></td>')
    return body

if _original_batch:
    core.app.view_functions['admin_batch'] = wrap_response(_original_batch, mark_batch)
