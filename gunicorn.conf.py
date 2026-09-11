# Load the dashboard UI layer before Gunicorn resolves app:app.
# This avoids relying on Python's optional sitecustomize loading behavior.
try:
    import ui_runtime  # noqa: F401
except Exception as exc:
    print(f"[ui_runtime] disabled: {exc}")
