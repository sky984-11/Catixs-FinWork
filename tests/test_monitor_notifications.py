import asyncio
import copy
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient, Response
from tortoise import Tortoise

from app.api.v1.monitor_events import router
from app.core.dependency import AuthControl, DependPermission
from app.models import MonitorEventConfig, MonitorNotificationConfig, MonitorNotificationDelivery, User
from app.services import monitor_notifications as service

SCOPE = {
    "revision": 1,
    "categories": [{"key": "network", "label": "Network"}],
    "hosts": [{"hostid": "1", "name": "test", "category": "network", "itemids": None}],
}
EVENT = {
    "id": "10",
    "name": "Ping loss <at id=all>",
    "severity": 4,
    "clock": 200,
    "recovered": False,
    "suppressed": False,
    "acknowledged": False,
    "recovery_clock": 0,
    "duration_seconds": 90,
    "categories": ["network"],
    "hosts": [{"name": "test", "addresses": ["192.0.2.1"]}],
    "items": [],
    "advice": {"steps": ["Check connectivity"]},
    "url": "https://example.invalid/event",
}


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="notify-test", email="test@example.invalid", is_superuser=True)
        await MonitorEventConfig.create(id=1, updated_by_id=self.user.id, **SCOPE)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/monitor-events", dependencies=[DependPermission])

        async def auth():
            if not self.user.is_active:
                raise HTTPException(401)
            return self.user

        app.dependency_overrides[AuthControl.is_authed] = auth
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api/v1/monitor-events")

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def config(self, **kwargs):
        return await MonitorNotificationConfig.create(
            id=1, enabled=True, recipient_ids=[self.user.id], enabled_since=100, **kwargs
        )

    async def test_disabled_default_has_no_upstream_activity(self):
        with patch.object(service, "ZabbixClient") as upstream:
            await service.run_notifications()
            upstream.assert_not_called()
        data = (await self.client.get("/notifications")).json()["data"]
        self.assertFalse(data["enabled"])
        self.assertEqual(data["users"][0]["name"], self.user.username)
        self.assertNotIn("email", data["users"][0])
        self.assertEqual(await MonitorNotificationConfig.all().count(), 0)

    async def test_save_validation_and_revision(self):
        payload = {"revision": 0, "enabled": True, "recipient_ids": [self.user.id]}
        with (
            patch.object(service, "feishu_app_enabled", return_value=True),
            patch.object(service.time, "time", return_value=1000),
        ):
            response = await self.client.put("/notifications", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["enabled_since"], 1000)
        with patch.object(service, "feishu_app_enabled", return_value=True):
            self.assertEqual((await self.client.put("/notifications", json=payload)).status_code, 409)
        payload.update(revision=1, category_keys=["unknown"])
        self.assertEqual((await self.client.put("/notifications", json=payload)).status_code, 422)
        payload.update(category_keys=[], recipient_ids=[])
        self.assertEqual((await self.client.put("/notifications", json=payload)).status_code, 422)
        self.assertEqual(await MonitorNotificationDelivery.all().count(), 0)

    async def test_permissions_and_request_validation(self):
        self.user.is_superuser = False
        self.assertEqual((await self.client.get("/notifications")).status_code, 403)
        self.assertEqual((await self.client.post("/notifications/preview", json={})).status_code, 403)
        self.user.is_superuser = True
        self.assertEqual((await self.client.post("/notifications/preview", json={"event_id": "x"})).status_code, 422)
        self.assertEqual((await self.client.get("/notifications/deliveries?page_size=101")).status_code, 422)
        self.user.is_active = False
        self.assertEqual((await self.client.get("/notifications")).status_code, 401)

    async def test_discovery_deduplicates_and_records_recovery(self):
        config = await self.config()
        event = copy.deepcopy(EVENT)
        snapshot = {"rows": [event], "truncated": False}
        with patch.object(service, "dashboard", AsyncMock(return_value=snapshot)):
            await service.discover(None, config, SCOPE)
            await service.discover(None, config, SCOPE)
            self.assertEqual(await MonitorNotificationDelivery.all().count(), 1)
            await MonitorNotificationDelivery.all().update(status="sent")
            event.update(recovered=True, recovery_clock=290)
            await service.discover(None, config, SCOPE)
        self.assertEqual(await MonitorNotificationDelivery.all().count(), 2)
        self.assertTrue((await MonitorNotificationDelivery.get(phase="problem")).recovery_done)

    async def test_delivery_failures_are_not_automatically_retried(self):
        config = await self.config(ai_enabled=False)
        entry = await MonitorNotificationDelivery.create(event_id="10", phase="problem", user_id=self.user.id)
        with (
            patch.object(service, "detail", AsyncMock(return_value=EVENT)),
            patch.object(service, "send_to_user", AsyncMock(return_value=False)) as send,
        ):
            await service.deliver_pending(None, config, SCOPE)
            await service.deliver_pending(None, config, SCOPE)
        self.assertEqual(send.await_count, 1)
        await entry.refresh_from_db()
        self.assertEqual((entry.status, entry.attempts), ("failed", 1))

    async def test_revoked_recipient_and_out_of_scope_events_not_sent(self):
        config = await self.config(ai_enabled=False)
        entry = await MonitorNotificationDelivery.create(event_id="10", phase="problem", user_id=self.user.id)
        with (
            patch.object(service, "detail", AsyncMock(side_effect=HTTPException(404))),
            patch.object(service, "send_to_user", AsyncMock()) as send,
        ):
            await service.deliver_pending(None, config, SCOPE)
        send.assert_not_awaited()
        await entry.refresh_from_db()
        self.assertEqual(entry.status, "skipped")
        entry.status = "pending"
        await entry.save()
        await User.filter(id=self.user.id).update(is_active=False)
        with patch.object(service, "send_to_user", AsyncMock()) as send:
            await service.deliver_pending(None, config, SCOPE)
        send.assert_not_awaited()

    async def test_disabling_while_ai_is_running_stops_send(self):
        config = await self.config()
        await MonitorNotificationDelivery.create(event_id="10", phase="problem", user_id=self.user.id)

        async def disable(*args):
            await MonitorNotificationConfig.filter(id=1).update(enabled=False, revision=1)
            return "advice", "ai"

        with (
            patch.object(service, "detail", AsyncMock(return_value=EVENT)),
            patch.object(service, "generate_advice", side_effect=disable),
            patch.object(service, "send_to_user", AsyncMock()) as send,
        ):
            await service.deliver_pending(None, config, SCOPE)
        send.assert_not_awaited()

    async def test_filters_and_pre_enable_events_are_excluded(self):
        config = await self.config(category_keys=["network"])
        self.assertTrue(service.matches(EVENT, config))
        self.assertFalse(service.matches({**EVENT, "suppressed": True}, config))
        self.assertFalse(service.matches({**EVENT, "categories": ["other"]}, config))
        self.assertFalse(service.matches({**EVENT, "severity": 1}, config))
        with patch.object(
            service, "dashboard", AsyncMock(return_value={"rows": [{**EVENT, "clock": 50}], "truncated": False})
        ):
            await service.discover(None, config, SCOPE)
        self.assertEqual(await MonitorNotificationDelivery.all().count(), 0)

    async def test_card_and_ai_fallback(self):
        with patch.object(service.httpx, "AsyncClient") as upstream:
            self.assertEqual(await service.generate_advice({**EVENT, "recovered": True}, True), ("", "none"))
            upstream.assert_not_called()
        text, source = await service.generate_advice(EVENT, False)
        self.assertEqual((text, source), ("Check connectivity", "rule"))
        card = service.build_card(EVENT, "problem", text, source, SCOPE["categories"])
        self.assertEqual(card["header"]["template"], "red")
        self.assertNotIn("持续时间\n", str(card).replace("\\n", "\n"))
        self.assertEqual(card["header"]["title"]["tag"], "plain_text")
        enriched = copy.deepcopy(EVENT)
        enriched["hosts"][0]["attributes"] = [{"key": "provider", "label": "Provider", "value": "ExampleCarrier"}]
        enriched_card = service.build_card(enriched, "problem", text, source, SCOPE["categories"])
        self.assertIn("ExampleCarrier", str(enriched_card))
        self.assertEqual(enriched_card["elements"][1]["text"]["tag"], "plain_text")
        recovery = service.build_card({**EVENT, "recovery_clock": 290}, "recovery", text, source, SCOPE["categories"])
        self.assertIn(
            "持续时间\n1 分 30 秒", [f["text"]["content"] for e in recovery["elements"] for f in e.get("fields", [])]
        )
        self.assertEqual(recovery["header"]["template"], "green")
        self.assertNotIn(text, str(recovery))
        self.assertNotIn("排查建议", str(recovery))
        enriched["hosts"][0]["name"] = "A -- Carrier -- B PATH - device1 - device2"
        layout = service.build_card(enriched, "problem", "**Check**\n# Steps\n`ping`", "ai", SCOPE["categories"])
        self.assertIn("线路 / 主机\nA -- Carrier -- B", [e.get("text", {}).get("content") for e in layout["elements"]])
        self.assertNotIn("**Check**", str(layout))
        self.assertIn("device1 - device2", str(layout))
        with (
            patch.object(service.settings, "FW_ASSISTANT_API_KEY", "test-key"),
            patch.object(service.httpx, "AsyncClient", side_effect=RuntimeError("offline")),
        ):
            self.assertEqual(await service.generate_advice(EVENT, True), (text, "rule"))

    async def test_ai_request_is_bounded_and_has_no_tools_or_recipient(self):
        response = Response(200, json={"choices": [{"message": {"content": "Suggested checks"}}]})
        response.raise_for_status = lambda: None
        client = AsyncMock()
        client.post.return_value = response
        with (
            patch.object(service.settings, "FW_ASSISTANT_API_KEY", "test-key"),
            patch.object(service.httpx, "AsyncClient") as factory,
        ):
            factory.return_value.__aenter__.return_value = client
            result = await service.generate_advice(EVENT, True)
        self.assertEqual(result, ("Suggested checks", "ai"))
        payload = client.post.call_args.kwargs["json"]
        self.assertNotIn("tools", payload)
        self.assertNotIn(self.user.email, str(payload))
        self.assertLessEqual(len(payload["messages"][1]["content"]), 9000)

    async def test_concurrent_workers_share_database_lease(self):
        await self.config(ai_enabled=False)
        entered, release = asyncio.Event(), asyncio.Event()

        async def discover(*args):
            entered.set()
            await release.wait()
            return ""

        with (
            patch.object(service, "feishu_app_enabled", return_value=True),
            patch.object(service, "ZabbixClient") as upstream,
            patch.object(service, "discover", side_effect=discover) as discovery,
            patch.object(service, "deliver_pending", AsyncMock()),
        ):
            upstream.return_value.__aenter__ = AsyncMock()
            upstream.return_value.__aexit__ = AsyncMock()
            task = asyncio.create_task(service.run_notifications())
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                await service.run_notifications()
                self.assertEqual(discovery.await_count, 1)
            finally:
                release.set()
                await task
        self.assertEqual((await MonitorNotificationConfig.get(id=1)).lease_until, 0)

    async def test_feishu_identity_priority_and_stable_idempotency_key(self):
        self.user.feishu_open_id = "openid"
        self.user.feishu_user_id = "userid"
        with patch.object(service, "send_feishu_app_card", AsyncMock(return_value=True)) as send:
            await service.send_to_user(self.user, {}, 1)
            first = send.call_args.kwargs
            await service.send_to_user(self.user, {}, 1)
            self.assertEqual(first, send.call_args.kwargs)
            self.assertEqual(first["receive_id_type"], "open_id")
            self.user.feishu_open_id = ""
            await service.send_to_user(self.user, {}, 2)
            self.assertEqual(send.call_args.kwargs["receive_id_type"], "user_id")

    async def test_preview_never_sends_and_retry_requires_failed_record(self):
        with (
            patch("app.api.v1.monitor_notifications.generate_advice", AsyncMock(return_value=("preview", "rule"))),
            patch.object(service, "send_to_user", AsyncMock()) as send,
        ):
            response = await self.client.post("/notifications/preview", json={})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["sample"])
        send.assert_not_awaited()
        await self.config()
        entry = await MonitorNotificationDelivery.create(event_id="10", phase="problem", user_id=self.user.id)
        self.assertEqual((await self.client.post(f"/notifications/deliveries/{entry.id}/retry")).status_code, 409)
        entry.status = "failed"
        await entry.save()
        with (
            patch("app.api.v1.monitor_notifications.ZabbixClient") as client,
            patch("app.api.v1.monitor_notifications.detail", AsyncMock(return_value=EVENT)),
        ):
            client.return_value.__aenter__ = AsyncMock()
            client.return_value.__aexit__ = AsyncMock()
            self.assertEqual((await self.client.post(f"/notifications/deliveries/{entry.id}/retry")).status_code, 200)
        await entry.refresh_from_db()
        self.assertEqual(entry.status, "pending")


if __name__ == "__main__":
    unittest.main()
