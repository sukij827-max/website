# Load optional UI and fresh/used email extensions automatically for Gunicorn/Railway.
try:
    import ui_runtime  # noqa: F401
except Exception:
    pass

try:
    import used_email_feature  # noqa: F401
except Exception:
    pass
