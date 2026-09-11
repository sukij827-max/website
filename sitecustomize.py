# Load the visual runtime layer automatically for Gunicorn/Railway.
# Python's site module imports sitecustomize during normal startup.
try:
    import ui_runtime  # noqa: F401
except Exception:
    # Never prevent the main application from starting if the optional UI layer fails.
    pass
