"""MailMarket production entrypoint.
Loads all UI/feature extensions before Gunicorn serves requests.
"""
import app as core

# Import order matters: the UI layer wraps the original dashboard first,
# then the Fresh/Bekas extension adds its own navigation and inventory layer.
import ui_runtime  # noqa: F401,E402
import used_email_feature  # noqa: F401,E402

app = core.app
