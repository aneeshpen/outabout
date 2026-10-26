"""Parent notification hook.

The Express backend logged the dispatch instead of sending mail
(``sendParentNotification`` in ``routes/passes.js``).  The behaviour is kept
identical - and isolated here - so a real mail provider can be plugged in
without touching the pass workflow.
"""

import logging

logger = logging.getLogger("digipass.notifications")


def notify_parent(email: str | None, student_name: str, pass_type: str) -> None:
    if not email:
        return
    logger.info(
        "[EMAIL DISPATCH] Sent to %s: %s applied for a %s pass.",
        email,
        student_name,
        pass_type,
    )
