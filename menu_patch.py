from app import app, db, Setting, admin_required, current_user, page
from flask import request, redirect, url_for, flash

MENU_DEFAULTS = {
    'menu_dashboard': 'Dashboard',
    'menu_submit': 'Ajukan',
    'menu_withdraw': 'Withdraw',
    'menu_user': 'User',
    'menu_rules': 'Aturan',
    'menu_referral': 'Undang Teman',
    'menu_admin': 'Admin',
    'menu_logout': 'Keluar',
    'menu_review': 'Review Email',
    'menu_settings': 'Pengaturan',
    'menu_logs': 'Log',
}

def menu_text(key):
    s = db.session.get(Setting, key)
    return (s.value.strip() if s and s.value.strip() else MENU_DEFAULTS[key])

with app.app_context():
    db.create_all()
    for k, v in MENU_DEFAULTS.items():
        if not db.session.get(Setting, k):
            db.session.add(Setting(key=k, value=v))
    db.session.commit()

@app.route('/admin/menu-settings', methods=['GET', 'POST'])
@admin_required
def admin_menu_settings():
    if request.method == 'POST':
        for key, default in MENU_DEFAULTS.items():
            value = request.form.get(key, default).strip()[:80]
            if not value:
                value = default
            s = db.session.get(Setting, key)
            if not s:
                s = Setting(key=key, value=value)
                db.session.add(s)
            else:
                s.value = value
        db.session.commit()
        flash('Nama menu berhasil diperbarui.')
        return redirect(url_for('admin_menu_settings'))

    fields = ''.join(
        f'<div class="card" style="padding:14px"><label>{default}</label>'
        f'<input class="input" name="{key}" value="{menu_text(key)}" maxlength="80" required></div>'
        for key, default in MENU_DEFAULTS.items()
    )
    body = f'''<div class="top"><div><div class="muted">ADMIN · UI</div><h1>Nama Menu</h1><p class="muted">Admin dapat mengganti teks/nama menu tanpa mengubah kode.</p></div><a class="btn secondary" href="/admin">← Kembali</a></div>
    <form method="post"><div class="grid">{fields}</div><button class="btn" style="margin-top:16px">Simpan Nama Menu</button></form>'''
    return page(body, 'Nama Menu', True)

@app.after_request
def apply_menu_settings(response):
    if response.content_type and 'text/html' in response.content_type and response.status_code == 200:
        html = response.get_data(as_text=True)
        replacements = {
            '>Dashboard<': f'>{menu_text("menu_dashboard")}<',
            '>Ajukan<': f'>{menu_text("menu_submit")}<',
            '>Withdraw<': f'>{menu_text("menu_withdraw")}<',
            '>User<': f'>{menu_text("menu_user")}<',
            '>Aturan<': f'>{menu_text("menu_rules")}<',
            '>Undang Teman<': f'>{menu_text("menu_referral")}<',
            '>Admin<': f'>{menu_text("menu_admin")}<',
            '>Keluar<': f'>{menu_text("menu_logout")}<',
            '>Review Email<': f'>{menu_text("menu_review")}<',
            '>Pengaturan<': f'>{menu_text("menu_settings")}<',
            '>Log<': f'>{menu_text("menu_logs")}<',
        }
        for old, new in replacements.items():
            html = html.replace(old, new)

        if current_user() and current_user().username == __import__('os').getenv('ADMIN_USERNAME', 'admin') and '/admin/menu-settings' not in html:
            marker = '<a class="btn secondary" href="/admin/settings">'
            html = html.replace(marker, marker + f'<a class="btn secondary" href="/admin/menu-settings">⚙ {menu_text("menu_admin")}</a>')

        if current_user() and '/dashboard' in html and 'dashboard-referral-card' not in html and 'Dashboard' in html:
            card = f'''<div id="dashboard-referral-card" class="card" style="margin-top:16px"><div class="top"><div><div class="muted">PROGRAM REFERRAL</div><h3>{menu_text('menu_referral')}</h3><p class="muted">Undang teman melalui link referral kamu. Setiap <b>1 email teman yang diterima admin</b> = <b>Rp 1.000</b>. Jadi 10 email diterima = <b>Rp 10.000</b>.</p></div><a class="btn" href="/referral">{menu_text('menu_referral')}</a></div></div>'''
            html = html.replace('<div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan</h3>', card + '<div class="card" style="margin-top:16px"><h3>Riwayat Pengajuan</h3>')
        response.set_data(html)
    return response
