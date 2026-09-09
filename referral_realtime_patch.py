from flask import request
from app import app
from models import Referral
from referral_patch import sync_referral_rewards

# Sync referral rewards AFTER the admin review route has committed the
# accepted/rejected status. The original before_request hook ran too early.
REVIEW_ENDPOINTS = {'accept', 'bulk_review', 'batch_bulk'}

@app.after_request
def realtime_referral_sync(response):
    if response.status_code < 200 or response.status_code >= 400:
        return response
    try:
        endpoint = request.endpoint or ''
        if endpoint in REVIEW_ENDPOINTS:
            for referral in Referral.query.all():
                try:
                    sync_referral_rewards(referral.referred_user_id)
                except Exception:
                    app.logger.exception('Referral reward sync failed for referral %s', referral.id)
    except Exception:
        app.logger.exception('Referral realtime sync failed')
    return response

# Also sync an inviter's rewards when they open the site, so the displayed
# balance is corrected even if an admin review happened in another session.
@app.before_request
def sync_inviter_rewards_on_activity():
    try:
        from app import current_user
        user = current_user()
        if not user or (request.endpoint or '') == 'static':
            return
        referrals = Referral.query.filter_by(inviter_id=user.id).all()
        for referral in referrals:
            try:
                sync_referral_rewards(referral.referred_user_id)
            except Exception:
                app.logger.exception('Inviter referral sync failed for referral %s', referral.id)
    except Exception:
        app.logger.exception('Inviter referral activity sync failed')
