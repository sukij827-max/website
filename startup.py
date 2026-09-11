"""MailMarket production entrypoint.
Loads all UI/feature extensions before Gunicorn serves requests.
"""
import app as core

# Load in order: base visual layer -> Fresh/Bekas feature -> final dashboard UI.
import ui_runtime  # noqa: F401,E402
import used_email_feature  # noqa: F401,E402
import dashboard_ui  # noqa: F401,E402

app = core.app
