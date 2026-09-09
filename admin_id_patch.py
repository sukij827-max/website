import os
from flask import session
from app import app, db, User

# Authorize the admin by immutable database User.id instead of username.
# ADMIN_ID must be set in Railway Variables to the admin user's numeric User ID.
_original_admin_username = os.getenv('ADMIN_USERNAME', 'admin')

@app.before_request
def authorize_admin_by_id():
    path = request_path = getattr(__import__('flask').request, 'path', '')
    if not path.startswith('/admin'):
        return None

    raw_id = os.getenv('ADMIN_ID', '').strip()
    if not raw_id.isdigit():
        return None

    uid = session.get('user_id')
    if uid is None or int(uid) != int(raw_id):
        return None

    # Existing admin_required() checks ADMIN_USERNAME. For the configured
    # ADMIN_ID, synchronize that legacy check to the actual admin username.
    u = db.session.get(User, int(raw_id))
    if u:
        os.environ['ADMIN_USERNAME'] = u.username
    return None
