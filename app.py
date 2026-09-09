import os, secrets
from decimal import Decimal
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
db_url = os.getenv('DATABASE_URL', 'sqlite:///marketplace.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif db_url.startswith('postgresql://'):
    db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    balance = db.Column(db.Numeric(14,2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    agreed_rules = db.Column(db.Boolean, default=False, nullable=False)
    price_snapshot = db.Column(db.Numeric(14,2), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship('User', backref='batches')

class EmailSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=False)
    email = db.Column(db.String(320), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    payout = db.Column(db.Numeric(14,2), default=0, nullable=False)
    rejection_reason = db.Column(db.String(500))
    reviewed_at = db.Column(db.DateTime)
    batch = db.relationship('Batch', backref='emails')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Numeric(14,2), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    note = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user = db.relationship('User', backref='transactions')

class Setting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

BASE='''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} · Email Marketplace</title><style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,sans-serif;background:#f5f7fb;color:#172033}a{text-decoration:none;color:inherit}.nav{height:64px;background:#fff;border-bottom:1px solid #e8ebf1;display:flex;align-items:center;justify-content:space-between;padding:0 6%;position:sticky;top:0;z-index:5}.brand{font-weight:800;letter-spacing:-.4px}.navlinks{display:flex;gap:18px;align-items:center;font-size:14px;color:#5c6678}.wrap{max-width:1120px;margin:32px auto;padding:0 20px}.hero{background:#fff;border:1px solid #e7eaf0;border-radius:22px;padding:30px;box-shadow:0 8px 30px #17203308}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.card{background:#fff;border:1px solid #e7eaf0;border-radius:18px;padding:20px;box-shadow:0 6px 24px #17203308}.muted{color:#697386}.big{font-size:30px;font-weight:800}.btn{border:0;border-radius:11px;padding:11px 16px;background:#172033;color:#fff;font-weight:700;cursor:pointer;display:inline-block}.btn.secondary{background:#eef1f6;color:#172033}.btn.danger{background:#a61b1b}.input,textarea{width:100%;padding:12px 13px;border:1px solid #dfe3ea;border-radius:11px;margin:7px 0 14px;background:#fff;font:inherit}textarea{min-height:130px;resize:vertical}.table{width:100%;border-collapse:collapse}.table th,.table td{padding:12px 8px;border-bottom:1px solid #edf0f4;text-align:left;font-size:14px}.pill{padding:5px 9px;border-radius:999px;font-size:12px;font-weight:700;background:#eef1f6}.pending{background:#fff3cd}.accepted{background:#dff6e8;color:#176b3a}.rejected{background:#fde3e3;color:#9a2020}.flash{padding:12px 14px;border-radius:12px;background:#fff3cd;margin-bottom:14px}.top{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}.actions{display:flex;gap:8px;flex-wrap:wrap}.auth{max-width:440px;margin:70px auto}.small{font-size:13px}.rule{white-space:pre-wrap;line-height:1.7}.email-list{min-height:180px}.admin{background:#101827;color:#fff}.admin .nav{background:#101827;color:#fff;border-color:#263247}.admin .navlinks{color:#c8d0dd}.admin .card,.admin .hero{background:#172236;border-color:#293750}.admin .muted{color:#aab5c7}.admin .input,.admin textarea{background:#111a2a;color:#fff;border-color:#34445f}
@media(max-width:650px){.nav{padding:0 18px}.navlinks{gap:9px}.wrap{margin:20px auto}.hero{padding:22px}.table{display:block;overflow:auto;white-space:nowrap}}
</style></head><body class="{{'admin' if admin else ''}}"><nav class="nav"><a class="brand" href="{{url_for('dashboard' if current_user else 'home')}}">EMAIL MARKET</a><div class="navlinks">{% if current_user %}<a href="{{url_for('dashboard')}}">Dashboard</a><a href="{{url_for('rules')}}">Aturan</a>{% if current_user.username==admin_user %}<a href="{{url_for('admin_dashboard')}}">Admin</a>{% endif %}<a href="{{url_for('logout')}}">Keluar</a>{% else %}<a href="{{url_for('login')}}">Masuk</a><a class="btn" href="{{url_for('register')}}">Daftar</a>{% endif %}</div></nav><main class="wrap">{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="flash">{{m}}</div>{% endfor %}{% endwith %}{{body|safe}}</main></body></html>'''

def page(body,title='Email Market',admin=False):
    u=current_user(); return render_template_string(BASE,body=body,title=title,current_user=u,admin=admin,admin_user=os.getenv('ADMIN_USERNAME','admin'))
def current_user():
    uid=session.get('user_id'); return db.session.get(User,uid) if uid else None
def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if not current_user(): return redirect(url_for('login'))
        return f(*a,**kw)
    return w
def admin_required(f):
    @wraps(f)
    def w(*a,**kw):
        u=current_user()
        if not u or u.username != os.getenv('ADMIN_USERNAME','admin'): abort(403)
        return f(*a,**kw)
    return w
def price():
    s=db.session.get(Setting,'email_price'); return Decimal(s.value) if s else Decimal('0')
def rules_text():
    r=Rule.query.first()
    return r.content if r else 'Hanya kirim alamat email yang memang kamu miliki dan berhak untuk diserahkan.\n\nDilarang mengirim password, OTP, recovery code, atau kredensial akun apa pun. Setiap pengajuan diperiksa admin dan dapat ditolak.'
def audit(action,detail): db.session.add(AdminLog(action=action,detail=detail))

@app.route('/')
def home():
    if current_user(): return redirect(url_for('dashboard'))
    body='''<section class="hero"><div style="max-width:700px"><div class="muted small">MARKETPLACE · REVIEW MANUAL</div><h1 style="font-size:44px;line-height:1.05;margin:10px 0">Ajukan email. Diperiksa. Dibayar.</h1><p class="muted" style="font-size:17px;line-height:1.6">Platform sederhana untuk mengajukan alamat email secara batch. Admin meninjau satu per satu dan saldo hanya bertambah untuk email yang diterima.</p><div class="actions"><a class="btn" href="/register">Mulai daftar</a><a class="btn secondary" href="/rules">Lihat aturan</a></div></div></section>'''
    return page(body,'Beranda')

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username=request.form.get('username','').strip(); pw=request.form.get('password','')
        if len(username)<3 or len(pw)<6: flash('Username minimal 3 karakter dan password minimal 6 karakter.')
        elif User.query.filter_by(username=username).first(): flash('Username sudah digunakan.')
        else:
            u=User(username=username,password_hash=generate_password_hash(pw)); db.session.add(u); db.session.commit(); session['user_id']=u.id; return redirect(url_for('dashboard'))
    body='''<div class="auth card"><h2>Buat akun</h2><p class="muted">Buat akun untuk mulai mengajukan email.</p><form method="post"><label>Username</label><input class="input" name="username" required><label>Password</label><input class="input" type="password" name="password" minlength="6" required><button class="btn">Daftar</button></form></div>'''; return page(body,'Daftar')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip()).first()
        if u and check_password_hash(u.password_hash,request.form.get('password','')): session['user_id']=u.id; return redirect(url_for('dashboard'))
        flash('Username atau password salah.')
    body='''<div class="auth card"><h2>Masuk</h2><form method="post"><label>Username</label><input class="input" name="username" required><label>Password</label><input class="input" type="password" name="password" required><button class="btn">Masuk</button></form></div>'''; return page(body,'Masuk')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/rules')
def rules():
    body=f'''<div class="hero"><div class="top"><div><h1>Aturan & Syarat Pengajuan</h1><p class="muted">Baca sebelum melakukan pengajuan.</p></div></div><div class="rule">{rules_text()}</div></div>'''; return page(body,'Aturan')

@app.route('/dashboard')
@login_required
def dashboard():
    u=current_user(); batches=Batch.query.filter_by(user_id=u.id).order_by(Batch.id.desc()).limit(20).all(); tx=Transaction.query.filter_by(user_id=u.id).order_by(Transaction.id.desc()).limit(10).all()
    rows=''.join(f'<tr><td>#{b.id}</td><td>{b.created_at}</td><td>{len(b.emails)}</td><td>{sum(e.status=="accepted" for e in b.emails)}</td><td>Rp {sum(Decimal(e.payout or 0) for e in b.emails):,.0f}</td></tr>' for b in batches)
    body=f'''<div class="top"><div><div class="muted small">Halo, {u.username}</div><h1>Dashboard</h1></div><a class="btn" href="/submit">+ Ajukan Email</a></div><div class="grid"><div class="card"><div class="muted">Saldo</div><div class="big">Rp {Decimal(u.balance):,.0f}</div></div><div class="card"><div class="muted">Harga aktif / email</div><div class="big">Rp {price():,.0f}</div></div><div class="card"><div class="muted">Total batch</div><div class="big">{len(u.batches)}</div></div></div><div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan</h3><table class="table"><tr><th>Batch</th><th>Tanggal</th><th>Email</th><th>Diterima</th><th>Payout</th></tr>{rows or '<tr><td colspan="5" class="muted">Belum ada pengajuan.</td></tr>'}</table></div><div class="card" style="margin-top:16px"><h3>Transaksi Terbaru</h3><table class="table"><tr><th>Tanggal</th><th>Jenis</th><th>Nominal</th><th>Catatan</th></tr>{''.join(f'<tr><td>{t.created_at}</td><td>{t.kind}</td><td>Rp {Decimal(t.amount):,.0f}</td><td>{t.note}</td></tr>' for t in tx) or '<tr><td colspan="4" class="muted">Belum ada transaksi.</td></tr>'}</table></div>'''; return page(body,'Dashboard')

@app.route('/submit',methods=['GET','POST'])
@login_required
def submit():
    if request.method=='POST':
        if request.form.get('agree')!='yes': flash('Kamu harus menyetujui aturan terlebih dahulu.'); return redirect(url_for('submit'))
        raw=request.form.get('emails',''); emails=[]
        for x in raw.replace(',','\n').splitlines():
            x=x.strip().lower()
            if x and x not in emails: emails.append(x)
        import re
        emails=[e for e in emails if re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',e)]
        if not emails: flash('Masukkan minimal satu alamat email yang valid.'); return redirect(url_for('submit'))
        b=Batch(user_id=current_user().id,agreed_rules=True,price_snapshot=price()); db.session.add(b); db.session.flush()
        for e in emails: db.session.add(EmailSubmission(batch_id=b.id,email=e))
        db.session.commit(); flash(f'Pengajuan #{b.id} berhasil dikirim.'); return redirect(url_for('dashboard'))
    body=f'''<div class="hero"><h1>Ajukan Email</h1><p class="muted">Masukkan satu atau banyak email. Pisahkan dengan baris baru atau koma.</p><form method="post"><textarea class="input email-list" name="emails" placeholder="email1@example.com\nemail2@example.com" required></textarea><label><input type="checkbox" name="agree" value="yes" required> Saya sudah membaca dan menyetujui <a href="/rules"><u>Aturan & Syarat Pengajuan</u></a>.</label><div style="margin-top:18px"><button class="btn">Kirim Pengajuan</button></div></form></div>'''; return page(body,'Ajukan Email')

@app.route('/admin')
@admin_required
def admin_dashboard():
    users=User.query.order_by(User.id.desc()).all(); batches=Batch.query.order_by(Batch.id.desc()).limit(30).all(); logs=AdminLog.query.order_by(AdminLog.id.desc()).limit(10).all()
    body=f'''<div class="top"><div><div class="muted">ADMIN PANEL</div><h1>Overview</h1></div><div class="actions"><a class="btn secondary" href="/admin/settings">Pengaturan</a><a class="btn secondary" href="/admin/logs">Log</a></div></div><div class="grid"><div class="card"><div class="muted">Pengguna</div><div class="big">{len(users)}</div></div><div class="card"><div class="muted">Batch</div><div class="big">{Batch.query.count()}</div></div><div class="card"><div class="muted">Harga aktif</div><div class="big">Rp {price():,.0f}</div></div></div><div class="card" style="margin-top:16px"><h3>Batch Terbaru</h3><table class="table"><tr><th>Batch</th><th>User</th><th>Email</th><th>Status</th><th></th></tr>{''.join(f'<tr><td>#{b.id}</td><td>{b.user.username}</td><td>{len(b.emails)}</td><td>{sum(e.status=="accepted" for e in b.emails)} diterima / {sum(e.status=="rejected" for e in b.emails)} ditolak</td><td><a class="btn secondary" href="/admin/batch/{b.id}">Review</a></td></tr>' for b in batches)}</table></div><div class="card" style="margin-top:16px"><h3>Pengguna</h3><table class="table"><tr><th>Username</th><th>ID</th><th>Saldo</th><th>Batch</th><th></th></tr>{''.join(f'<tr><td>{u.username}</td><td>{u.id}</td><td>Rp {Decimal(u.balance):,.0f}</td><td>{len(u.batches)}</td><td><a class="btn secondary" href="/admin/user/{u.id}">Kelola</a></td></tr>' for u in users)}</table></div>'''; return page(body,'Admin',True)

@app.route('/admin/batch/<int:bid>')
@admin_required
def admin_batch(bid):
    b=db.get_or_404(Batch,bid)
    rows=''.join(f'''<tr><td>{e.email}</td><td><span class="pill {e.status}">{e.status}</span></td><td>Rp {Decimal(e.payout):,.0f}</td><td>{e.rejection_reason or '-'}</td><td>{"<form method='post' action='/admin/email/%d/accept' style='display:inline'><button class='btn'>Terima</button></form> <form method='post' action='/admin/email/%d/reject' style='display:inline'><input class='input' style='width:170px;margin:0' name='reason' placeholder='Alasan'><button class='btn danger'>Tolak</button></form>"%(e.id,e.id) if e.status=='pending' else '-'}</td></tr>''' for e in b.emails)
    body=f'''<div class="top"><div><div class="muted">BATCH #{b.id} · {b.user.username}</div><h1>Review Pengajuan</h1></div><a class="btn secondary" href="/admin">Kembali</a></div><div class="card"><p class="muted">Harga saat submit: <b>Rp {Decimal(b.price_snapshot):,.0f}</b></p><table class="table"><tr><th>Email</th><th>Status</th><th>Payout</th><th>Alasan</th><th>Aksi</th></tr>{rows}</table></div>'''; return page(body,'Review Batch',True)

@app.post('/admin/email/<int:eid>/accept')
@admin_required
def accept(eid):
    e=db.get_or_404(EmailSubmission,eid)
    if e.status!='pending': flash('Item sudah direview.'); return redirect(url_for('admin_batch',bid=e.batch_id))
    e.status='accepted'; e.payout=e.batch.price_snapshot; e.reviewed_at=db.func.now(); u=e.batch.user; u.balance=Decimal(u.balance)+Decimal(e.payout); db.session.add(Transaction(user_id=u.id,amount=e.payout,kind='payout',note=f'Email diterima · Batch #{e.batch_id}')); audit('accept_email',f'Email #{e.id} batch #{e.batch_id} accepted'); db.session.commit(); flash('Email diterima dan saldo ditambahkan.'); return redirect(url_for('admin_batch',bid=e.batch_id))

@app.post('/admin/email/<int:eid>/reject')
@admin_required
def reject(eid):
    e=db.get_or_404(EmailSubmission,eid)
    if e.status!='pending': flash('Item sudah direview.'); return redirect(url_for('admin_batch',bid=e.batch_id))
    e.status='rejected'; e.rejection_reason=request.form.get('reason','Tidak memenuhi syarat.')[:500]; e.reviewed_at=db.func.now(); audit('reject_email',f'Email #{e.id} batch #{e.batch_id} rejected'); db.session.commit(); flash('Email ditolak.'); return redirect(url_for('admin_batch',bid=e.batch_id))

@app.route('/admin/user/<int:uid>',methods=['GET','POST'])
@admin_required
def admin_user(uid):
    u=db.get_or_404(User,uid)
    if request.method=='POST':
        try: amount=Decimal(request.form.get('amount','0'))
        except: amount=Decimal('0')
        note=request.form.get('note','Penyesuaian saldo manual').strip()[:500]
        if amount==0: flash('Nominal tidak boleh 0.')
        else:
            u.balance=Decimal(u.balance)+amount; db.session.add(Transaction(user_id=u.id,amount=amount,kind='manual_adjustment',note=note or 'Penyesuaian saldo manual')); audit('balance_adjustment',f'User {u.username} ({u.id}) amount {amount}'); db.session.commit(); flash('Saldo berhasil diperbarui.')
    tx=Transaction.query.filter_by(user_id=u.id).order_by(Transaction.id.desc()).limit(30).all()
    body=f'''<div class="top"><div><div class="muted">USER #{u.id}</div><h1>{u.username}</h1><p>Saldo: <b>Rp {Decimal(u.balance):,.0f}</b></p></div><a class="btn secondary" href="/admin">Kembali</a></div><div class="grid"><div class="card"><h3>Tambah / Kurangi Saldo</h3><form method="post"><label>Nominal (gunakan minus untuk mengurangi)</label><input class="input" name="amount" type="number" step="0.01" required placeholder="5000"><label>Alasan</label><input class="input" name="note" required placeholder="Koreksi data"><button class="btn">Simpan</button></form></div><div class="card"><h3>Riwayat Transaksi</h3><table class="table"><tr><th>Tanggal</th><th>Nominal</th><th>Jenis</th><th>Catatan</th></tr>{''.join(f'<tr><td>{t.created_at}</td><td>Rp {Decimal(t.amount):,.0f}</td><td>{t.kind}</td><td>{t.note}</td></tr>' for t in tx)}</table></div></div>'''; return page(body,'Kelola User',True)

@app.route('/admin/settings',methods=['GET','POST'])
@admin_required
def admin_settings():
    if request.method=='POST':
        try: p=Decimal(request.form.get('price','0'))
        except: p=Decimal('0')
        if p<0: flash('Harga tidak boleh negatif.')
        else:
            s=db.session.get(Setting,'email_price')
            if not s: s=Setting(key='email_price',value=str(p)); db.session.add(s)
            else: s.value=str(p)
            audit('price_update',f'Base email price changed to {p}'); db.session.commit(); flash('Harga aktif berhasil diperbarui.')
        r=Rule.query.first(); text=request.form.get('rules','').strip()
        if text:
            if not r: r=Rule(content=text); db.session.add(r)
            else: r.content=text
            db.session.commit(); flash('Aturan berhasil diperbarui.')
    body=f'''<div class="top"><div><div class="muted">ADMIN SETTINGS</div><h1>Pengaturan</h1></div><a class="btn secondary" href="/admin">Kembali</a></div><div class="grid"><div class="card"><h3>Pengaturan Harga per Email</h3><p class="muted">Harga ini hanya berlaku untuk pengajuan baru. Batch lama menyimpan harga saat submit.</p><form method="post"><label>Harga aktif (Rp)</label><input class="input" name="price" type="number" min="0" step="1" value="{price():.0f}" required><label>Aturan & Syarat Pengajuan</label><textarea name="rules" class="input">{rules_text()}</textarea><button class="btn">Simpan Pengaturan</button></form></div></div>'''; return page(body,'Pengaturan',True)

@app.route('/admin/logs')
@admin_required
def admin_logs():
    logs=AdminLog.query.order_by(AdminLog.id.desc()).limit(100).all(); body=f'''<div class="top"><h1>Audit Log</h1><a class="btn secondary" href="/admin">Kembali</a></div><div class="card"><table class="table"><tr><th>Waktu</th><th>Aksi</th><th>Detail</th></tr>{''.join(f'<tr><td>{l.created_at}</td><td>{l.action}</td><td>{l.detail}</td></tr>' for l in logs)}</table></div>'''; return page(body,'Log',True)

with app.app_context():
    db.create_all()
    if not db.session.get(Setting,'email_price'):
        db.session.add(Setting(key='email_price',value=os.getenv('DEFAULT_EMAIL_PRICE','500')))
    if not Rule.query.first(): db.session.add(Rule(content=rules_text()))
    if not User.query.filter_by(username=os.getenv('ADMIN_USERNAME','admin')).first():
        db.session.add(User(username=os.getenv('ADMIN_USERNAME','admin'),password_hash=generate_password_hash(os.getenv('ADMIN_PASSWORD','change-me-now'))))
    db.session.commit()

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
