# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Bring the on-screen stack down to a single card.

    The default used to be four. The default design is a large card, so four of
    them are taller than the screen: a burst of notices ran off the bottom
    instead of queueing behind the "more waiting" chip.

    Only styles still holding the old default are touched. Anyone who picked a
    number deliberately keeps it.
    """
    cr.execute("""
        UPDATE velkio_popup_style
           SET stack_limit = 1
         WHERE stack_limit = 4
    """)
    if cr.rowcount:
        _logger.info(
            'Velkio: %s popup style(s) moved from four cards on screen to one.',
            cr.rowcount,
        )
