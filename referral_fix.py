from flask import request, session
from sqlalchemy.exc import IntegrityError
from app import app, db, User, current_user
from referral_patch import Referral, sync_referral_rewards

# Attach the referral AFTER /register has created the user and session.
@app.after_request
def referral_attach_after_register(response):
    try:
        uid = session.get('user_id')
        refid = session.get('referrer_id')
        if uid and refid and uid != refid and request.endpoint == 'register':
            if not Referral.query.filter_by(referred_user_id=uid).first():
                inviter = db.session.get(User, refid)
                referred = db.session.get(User, uid)
                if inviter and referred:
                    db.session.add(Referral(inviter_id=inviter.id, referred_user_id=referred.id))
                    db.session.commit()
            session.pop('referrer_id', None)
    except IntegrityError:
        db.session.rollback()
        session.pop('referrer_id', None)
    except Exception:
        db.session.rollback()
    return response

# The old referral code synced BEFORE the admin review route ran.
# Sync again AFTER the review response, when accepted statuses are already committed.
@app.after_request
def referral_sync_after_admin_review(response):
    try:
        admin = current_user()
        if admin and request.endpoint in ('accept', 'reject', 'bulk_review', 'batch_bulk'):
            for ref in Referral.query.all():
                sync_referral_rewards(ref.referred_user_id)
    except Exception:
        db.session.rollback()
    return response
