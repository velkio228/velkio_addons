import base64
import hashlib
import hmac
import json
import logging

from odoo import SUPERUSER_ID, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WooWebhookController(http.Controller):

    @http.route(
        "/zenvio/woo/webhook/<int:instance_id>",
        type="http", auth="public", methods=["POST"], csrf=False, save_session=False,
    )
    def woo_webhook(self, instance_id, **kwargs):
        env = request.env(user=SUPERUSER_ID, su=True)
        instance = env["woo.instance"].browse(instance_id).exists()
        if not instance or not instance.active or not instance.webhook_secret:
            return request.make_response("Unknown webhook", status=404)

        body = request.httprequest.get_data()
        signature = request.httprequest.headers.get("X-WC-Webhook-Signature")
        if not signature:
            # WooCommerce sends an unsigned "webhook_id=N" ping when a webhook is
            # created; acknowledge it without processing anything.
            return request.make_response("ok")
        expected = base64.b64encode(hmac.new(instance.webhook_secret.encode(), body, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(expected, signature):
            _logger.warning("Rejected WooCommerce webhook with an invalid signature for instance %s", instance_id)
            return request.make_response("Invalid signature", status=401)

        try:
            payload = json.loads(body)
        except ValueError:
            return request.make_response("Invalid payload", status=400)
        if isinstance(payload, dict):
            topic = request.httprequest.headers.get("X-WC-Webhook-Topic")
            instance.with_company(instance.company_id)._process_webhook(topic, payload)
        return request.make_response("ok")
