"""Runtime UI layer for MailMarket dashboards.
Loaded by gunicorn.conf.py before the app is served.
"""
from decimal import Decimal
from flask import Response
import app as core

try:
    import visual_patch  # noqa: F401
except Exception:
    pass


def _dashboard_stats_html():
    u = core.current_user()
    if not u:
        return ""
    q = core.EmailSubmission.query.join(core.Batch).filter(core.Batch.user_id == u.id)
    total = q.count()
    accepted = q.filter(core.EmailSubmission.status == "accepted").count()
    rejected = q.filter(core.EmailSubmission.status == "rejected").count()
    pending = q.filter(core.EmailSubmission.status == "pending").count()
    paid = core.db.session.query(
        core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout), 0)
    ).join(core.Batch).filter(
        core.Batch.user_id == u.id,
        core.EmailSubmission.status == "accepted",
    ).scalar() or 0
    rate = (accepted / total * 100) if total else 0
    return f'''<div class="mm-dashboard-stats">
      <div class="mm-dstat mm-dstat-users"><div class="mm-dicon">♙</div><div><span>Pengguna Aktif</span><strong>1</strong><small>Akun kamu</small></div></div>
      <div class="mm-dstat mm-dstat-email"><div class="mm-dicon">✉</div><div><span>Email Diterima</span><strong>{accepted:,}</strong><small>{total:,} email diajukan</small></div></div>
      <div class="mm-dstat mm-dstat-security"><div class="mm-dicon">✓</div><div><span>Tingkat Keamanan</span><strong>{rate:.0f}%</strong><small>Review manual</small></div></div>
      <div class="mm-dstat mm-dstat-money"><div class="mm-dicon">Rp</div><div><span>Dana Dibayarkan</span><strong>Rp {Decimal(paid):,.0f}</strong><small>{rejected:,} ditolak · {pending:,} pending</small></div></div>
    </div>'''


def _admin_stats_html():
    users = core.User.query.filter_by(is_banned=False).count()
    emails = core.EmailSubmission.query.count()
    accepted = core.EmailSubmission.query.filter_by(status="accepted").count()
    paid = core.db.session.query(
        core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout), 0)
    ).filter(core.EmailSubmission.status == "accepted").scalar() or 0
    security = 100 if emails else 0
    return f'''<div class="mm-dashboard-stats mm-admin-stats">
      <div class="mm-dstat mm-dstat-users"><div class="mm-dicon">♙</div><div><span>Pengguna Aktif</span><strong>{users:,}</strong><small>Pengguna tidak diblokir</small></div></div>
      <div class="mm-dstat mm-dstat-email"><div class="mm-dicon">✉</div><div><span>Email Diterima</span><strong>{accepted:,}</strong><small>Dari {emails:,} email diproses</small></div></div>
      <div class="mm-dstat mm-dstat-security"><div class="mm-dicon">✓</div><div><span>Tingkat Keamanan</span><strong>{security}%</strong><small>Review manual aktif</small></div></div>
      <div class="mm-dstat mm-dstat-money"><div class="mm-dicon">Rp</div><div><span>Dana Dibayarkan</span><strong>Rp {Decimal(paid):,.0f}</strong><small>Total payout diterima user</small></div></div>
    </div>'''


_extra_css = r'''
.mm-dashboard-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0 16px}
.mm-dstat{position:relative;overflow:hidden;min-height:126px;border:1px solid #e1e8f2;border-radius:18px;padding:18px;display:flex;align-items:center;gap:13px;background:linear-gradient(145deg,#fff,#f7faff);box-shadow:0 10px 30px #0b25500d}
.mm-dstat:after{content:"";position:absolute;width:100px;height:100px;border-radius:50%;right:-35px;top:-35px;background:#1677ff0d}
.mm-dicon{position:relative;z-index:1;width:47px;height:47px;min-width:47px;border-radius:15px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;background:#eaf3ff;color:#1677ff;box-shadow:inset 0 0 0 1px #1677ff12}
.mm-dstat span{display:block;font-size:12px;color:#6c7890;font-weight:700;margin-bottom:4px}.mm-dstat strong{display:block;font-size:23px;line-height:1.15;color:#0b1830;font-weight:900}.mm-dstat small{display:block;font-size:11px;color:#8a95a7;margin-top:5px}
.mm-dstat-email .mm-dicon{background:#e9f8f3;color:#14815e}.mm-dstat-security .mm-dicon{background:#fff5df;color:#aa7a13}.mm-dstat-money .mm-dicon{background:#f0eaff;color:#7650c8}
.admin .mm-dstat{background:linear-gradient(145deg,#0e1d33,#0a172a);border-color:#243752}.admin .mm-dstat strong{color:#eef5ff}.admin .mm-dstat span{color:#a8b7cb}.admin .mm-dstat small{color:#7f91aa}.admin .mm-dicon{background:#183252;color:#65aaff}.admin .mm-dstat-email .mm-dicon{background:#12382f;color:#58d6ac}.admin .mm-dstat-security .mm-dicon{background:#3b321d;color:#f0c96b}.admin .mm-dstat-money .mm-dicon{background:#2c2144;color:#b99aff}
@media(max-width:900px){.mm-dashboard-stats{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.mm-dashboard-stats{grid-template-columns:1fr}.mm-dstat{min-height:108px}}
'''

if '</style>' in core.BASE and 'mm-dashboard-stats' not in core.BASE:
    core.BASE = core.BASE.replace('</style>', _extra_css + '</style>', 1)

_original_dashboard = core.app.view_functions.get("dashboard")
_original_admin = core.app.view_functions.get("admin_dashboard")


def _wrap(original, stats_fn, marker):
    def wrapped(*args, **kwargs):
        response = original(*args, **kwargs)
        if not hasattr(response, "get_data"):
            return response
        html = response.get_data(as_text=True)
        stats = stats_fn()
        if stats and marker in html and 'mm-dashboard-stats' not in html:
            html = html.replace(marker, stats + marker, 1)
        return Response(
            html,
            status=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            content_type="text/html; charset=utf-8",
        )
    wrapped.__name__ = getattr(original, "__name__", "wrapped_dashboard")
    return wrapped


if _original_dashboard:
    core.app.view_functions["dashboard"] = _wrap(
        _original_dashboard,
        _dashboard_stats_html,
        '<div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan',
    )
if _original_admin:
    core.app.view_functions["admin_dashboard"] = _wrap(
        _original_admin,
        _admin_stats_html,
        '<div class="card" style="margin-top:16px"><div class="top"><h3>Semua Pengajuan',
    )

app = core.app
