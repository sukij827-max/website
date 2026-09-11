"""Final dashboard UI layer: guaranteed inline cards and Fresh/Bekas action cards."""
from decimal import Decimal
from flask import Response
import app as core

CSS = r'''
.mm-inline-wrap{margin:0 0 18px}
.mm-inline-head{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.mm-inline-head h2{margin:0;font-size:20px;letter-spacing:-.3px}.mm-inline-head p{margin:4px 0 0;color:#728097;font-size:12px}
.mm-inline-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.mm-inline-card{position:relative;overflow:hidden;border:1px solid #e1e8f2;border-radius:17px;padding:16px;background:linear-gradient(145deg,#fff,#f7faff);box-shadow:0 8px 25px #102d5a0a;display:flex;align-items:center;gap:12px;min-height:104px}
.mm-inline-card:after{content:'';position:absolute;right:-30px;top:-30px;width:82px;height:82px;border-radius:50%;background:#1677ff0d}
.mm-inline-icon{position:relative;z-index:1;width:42px;height:42px;min-width:42px;border-radius:13px;display:grid;place-items:center;font-weight:900;background:#eaf3ff;color:#1677ff}
.mm-inline-card:nth-child(2) .mm-inline-icon{background:#e8f8f2;color:#13835e}.mm-inline-card:nth-child(3) .mm-inline-icon{background:#fff4dc;color:#a87610}.mm-inline-card:nth-child(4) .mm-inline-icon{background:#eee8ff;color:#7351c4}
.mm-inline-label{display:block;color:#718096;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.35px}.mm-inline-value{display:block;color:#0b1830;font-size:21px;font-weight:950;margin-top:3px}.mm-inline-note{display:block;color:#8995a7;font-size:10px;margin-top:3px}
.mm-inline-actions{display:grid;grid-template-columns:1.2fr 1fr;gap:12px;margin-top:12px}.mm-inline-action{border-radius:16px;padding:16px 18px;border:1px solid #dfe7f2;background:#fff;display:flex;align-items:center;justify-content:space-between;gap:14px}.mm-inline-action.primary{background:linear-gradient(135deg,#09295c,#1265c5);border:0;color:#fff}.mm-inline-action h3{margin:0 0 4px;font-size:14px}.mm-inline-action p{margin:0;font-size:11px;color:#738198}.mm-inline-action.primary p{color:#c9dcf4}.mm-inline-action .btn{white-space:nowrap}
.admin .mm-inline-card{background:linear-gradient(145deg,#0e1d33,#0a172a);border-color:#263956}.admin .mm-inline-label{color:#9fb0c7}.admin .mm-inline-value{color:#eef5ff}.admin .mm-inline-note{color:#7f91aa}.admin .mm-inline-action{background:#0d1b31;border-color:#263956}.admin .mm-inline-action p{color:#8fa2bb}
@media(max-width:900px){.mm-inline-grid{grid-template-columns:1fr 1fr}.mm-inline-actions{grid-template-columns:1fr}}
@media(max-width:560px){.mm-inline-grid{grid-template-columns:1fr}.mm-inline-card{min-height:94px}}
'''

if '</style>' in core.BASE and 'mm-inline-wrap' not in core.BASE:
    core.BASE = core.BASE.replace('</style>', CSS + '</style>', 1)


def user_panel():
    u=core.current_user()
    if not u: return ''
    q=core.EmailSubmission.query.join(core.Batch).filter(core.Batch.user_id==u.id)
    total=q.count(); accepted=q.filter(core.EmailSubmission.status=='accepted').count()
    pending=q.filter(core.EmailSubmission.status=='pending').count(); rejected=q.filter(core.EmailSubmission.status=='rejected').count()
    paid=core.db.session.query(core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout),0)).join(core.Batch).filter(core.Batch.user_id==u.id,core.EmailSubmission.status=='accepted').scalar() or 0
    rate=(accepted/total*100) if total else 0
    return f'''<section class="mm-inline-wrap"><div class="mm-inline-head"><div><h2>Ringkasan Akun</h2><p>Semua informasi utama akun kamu terlihat langsung dalam satu panel.</p></div><span class="pill accepted">● Akun Aktif</span></div><div class="mm-inline-grid"><div class="mm-inline-card"><div class="mm-inline-icon">♙</div><div><span class="mm-inline-label">Pengguna Aktif</span><strong class="mm-inline-value">1</strong><small class="mm-inline-note">Akun kamu</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">✉</div><div><span class="mm-inline-label">Email Diterima</span><strong class="mm-inline-value">{accepted:,}</strong><small class="mm-inline-note">{total:,} total diajukan</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">✓</div><div><span class="mm-inline-label">Tingkat Keamanan</span><strong class="mm-inline-value">{rate:.0f}%</strong><small class="mm-inline-note">Review manual</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">Rp</div><div><span class="mm-inline-label">Dana Dibayarkan</span><strong class="mm-inline-value">Rp {Decimal(paid):,.0f}</strong><small class="mm-inline-note">{pending} pending · {rejected} ditolak</small></div></div></div><div class="mm-inline-actions"><div class="mm-inline-action primary"><div><h3>✉ Email Bekas</h3><p>Ajukan email bekas secara terpisah agar admin langsung mengetahui jenis pengajuannya.</p></div><a class="btn secondary" href="/submit-used">Ajukan Email Bekas →</a></div><div class="mm-inline-action"><div><h3>▣ Email Fresh</h3><p>Gunakan alur pengajuan biasa untuk email fresh.</p></div><a class="btn" href="/submit">Ajukan Fresh →</a></div></div></section>'''


def admin_panel():
    users=core.User.query.filter_by(is_banned=False).count(); emails=core.EmailSubmission.query.count(); accepted=core.EmailSubmission.query.filter_by(status='accepted').count()
    paid=core.db.session.query(core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout),0)).filter(core.EmailSubmission.status=='accepted').scalar() or 0
    return f'''<section class="mm-inline-wrap"><div class="mm-inline-head"><div><h2>Control Center</h2><p>Statistik utama dan pengelolaan data ditampilkan sebagai komponen dashboard.</p></div><span class="pill accepted">● Admin aktif</span></div><div class="mm-inline-grid"><div class="mm-inline-card"><div class="mm-inline-icon">♙</div><div><span class="mm-inline-label">Pengguna Aktif</span><strong class="mm-inline-value">{users:,}</strong><small class="mm-inline-note">Tidak diblokir</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">✉</div><div><span class="mm-inline-label">Email Diterima</span><strong class="mm-inline-value">{accepted:,}</strong><small class="mm-inline-note">Dari {emails:,} email</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">✓</div><div><span class="mm-inline-label">Tingkat Keamanan</span><strong class="mm-inline-value">100%</strong><small class="mm-inline-note">Review manual</small></div></div><div class="mm-inline-card"><div class="mm-inline-icon">Rp</div><div><span class="mm-inline-label">Dana Dibayarkan</span><strong class="mm-inline-value">Rp {Decimal(paid):,.0f}</strong><small class="mm-inline-note">Total payout</small></div></div></div><div class="mm-inline-actions"><div class="mm-inline-action primary"><div><h3>✉ Inventory Fresh / Bekas</h3><p>Lihat setiap email beserta jenis, user, ID user, status dan payout.</p></div><a class="btn secondary" href="/admin/email-inventory">Buka Inventory →</a></div><div class="mm-inline-action"><div><h3>◉ Review Manual</h3><p>Periksa pengajuan yang masih menunggu.</p></div><a class="btn" href="/admin/pending">Review →</a></div></div></section>'''


def wrap(name, panel):
    original=core.app.view_functions.get(name)
    if not original: return
    def wrapped(*args,**kwargs):
        response=original(*args,**kwargs)
        if not hasattr(response,'get_data'): return response
        html=response.get_data(as_text=True)
        if 'mm-inline-wrap' not in html:
            marker="</main>"
            html=html.replace(marker,panel()+marker,1)
        return Response(html,status=response.status_code,headers={k:v for k,v in response.headers.items() if k.lower()!='content-length'},content_type='text/html; charset=utf-8')
    wrapped.__name__=getattr(original,'__name__','wrapped')
    core.app.view_functions[name]=wrapped

wrap('dashboard',user_panel)
wrap('admin_dashboard',admin_panel)
