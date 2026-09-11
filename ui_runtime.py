"""Runtime UI layer for MailMarket.
Keeps application/business logic intact while upgrading the user/admin dashboards.
"""
import re
from decimal import Decimal

from flask import Response

import app as core

# Existing visual homepage redesign.
try:
    import visual_patch  # noqa: F401
except Exception:
    pass


def _dashboard_stats_html():
    u = core.current_user()
    if not u:
        return ""
    user_emails = core.EmailSubmission.query.join(core.Batch).filter(
        core.Batch.user_id == u.id
    )
    total_emails = user_emails.count()
    accepted = user_emails.filter(core.EmailSubmission.status == "accepted").count()
    rejected = user_emails.filter(core.EmailSubmission.status == "rejected").count()
    pending = user_emails.filter(core.EmailSubmission.status == "pending").count()
    paid = db_sum = core.db.session.query(
        core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout), 0)
    ).join(core.Batch).filter(
        core.Batch.user_id == u.id,
        core.EmailSubmission.status == "accepted",
    ).scalar() or 0
    return f'''<div class="mm-dashboard-stats">
      <div class="mm-dstat mm-dstat-users"><div class="mm-dicon">♙</div><div><span>Pengguna Aktif</span><strong>1</strong><small>Akun kamu</small></div></div>
      <div class="mm-dstat mm-dstat-email"><div class="mm-dicon">✉</div><div><span>Email Diterima</span><strong>{accepted:,}</strong><small>{total_emails:,} email diajukan</small></div></div>
      <div class="mm-dstat mm-dstat-security"><div class="mm-dicon">✓</div><div><span>Tingkat Keamanan</span><strong>{(accepted / total_emails * 100) if total_emails else 0:.0f}%</strong><small>Review manual</small></div></div>
      <div class="mm-dstat mm-dstat-money"><div class="mm-dicon">Rp</div><div><span>Dana Dibayarkan</span><strong>Rp {Decimal(paid):,.0f}</strong><small>{rejected:,} ditolak · {pending:,} pending</small></div></div>
    </div>'''


def _admin_stats_html():
    users = core.User.query.filter_by(is_banned=False).count()
    emails = core.EmailSubmission.query.count()
    accepted = core.EmailSubmission.query.filter_by(status="accepted").count()
    paid = core.db.session.query(
        core.db.func.coalesce(core.db.func.sum(core.EmailSubmission.payout), 0)
    ).filter(core.EmailSubmission.status == "accepted").scalar() or 0
    return f'''<div class="mm-dashboard-stats mm-admin-stats">
      <div class="mm-dstat mm-dstat-users"><div class="mm-dicon">♙</div><div><span>Pengguna Aktif</span><strong>{users:,}</strong><small>Pengguna tidak diblokir</small></div></div>
      <div class="mm-dstat mm-dstat-email"><div class="mm-dicon">✉</div><div><span>Email Diterima</span><strong>{accepted:,}</strong><small>Dari {emails:,} email diproses</small></div></div>
      <div class="mm-dstat mm-dstat-security"><div class="mm-dicon">✓</div><div><span>Tingkat Keamanan</span><strong>100%</strong><small>Review manual aktif</small></div></div>
      <div class="mm-dstat mm-dstat-money"><div class="mm-dicon">Rp</div><div><span>Dana Dibayarkan</span><strong>Rp {Decimal(paid):,.0f}</strong><small>Total payout diterima user</small></div></div>
    </div>'''


# Add richer dashboard styling to the existing template.
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
if '</style>' in core.BASE:
    core.BASE = core.BASE.replace('</style>', _extra_css + '</style>', 1)


_original_dashboard = core.app.view_functions.get("dashboard")
_original_admin = core.app.view_functions.get("admin_dashboard")


def _dashboard_visual(*args, **kwargs):
    response = _original_dashboard(*args, **kwargs)
    html = response.get_data(as_text=True) if hasattr(response, "get_data") else str(response)
    stats = _dashboard_stats_html()
    if stats:
        html = re.sub(r'<div class="grid">.*?</div>\s*<div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan',
                      stats + '<div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan',
                      html, count=1, flags=re.S)
    return Response(html, status=getattr(response, "status_code", 200), headers=dict(response.headers), content_type="text/html; charset=utf-8")


def _admin_visual(*args, **kwargs):
    response = _original_admin(*args, **kwargs)
    html = response.get_data(as_text=True) if hasattr(response, "get_data") else str(response)
    stats = _admin_stats_html()
    html = re.sub(r'<div class="grid">.*?</div>\s*<div class="card" style="margin-top:16px"><div class="top"><h3>Semua Pengajuan',
                  stats + '<div class="card" style="margin-top:16px"><div class="top"><h3>Semua Pengajuan',
                  html, count=1, flags=re.S)
    return Response(html, status=getattr(response, "status_code", 200), headers=dict(response.headers), content_type="text/html; charset=utf-8")


if _original_dashboard:
    core.app.view_functions["dashboard"] = _dashboard_visual
if _original_admin:
    core.app.view_functions["admin_dashboard"] = _admin_visual

# Export the same Flask app object for Gunicorn/Railway.
app = core.app
