import logging
import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.ctx import CTX_USER_ID
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.company import Bill, Company
from app.models.customer_center import CrmCustomer, CrmSigningEntity
from app.models.idc import CustomerService, IdcBillAllocation, IdcQuote, ServiceVersion
from app.services.idc_catalog import CATALOG, validate_parameters
from app.services.idc_workflow import catalog_products


class IdcWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        logging.getLogger("asyncio").setLevel(logging.ERROR)
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        await catalog_products()
        self.user = await User.create(username="idc-admin", email="idc@example.test", is_superuser=True)
        entity = await CrmSigningEntity.create(name="Catixs", code="CATIXS")
        customer = await CrmCustomer.create(name="Customer", signing_entity=entity)
        company = await Company.create(name="Bill Customer", role=1)
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            CTX_USER_ID.set(self.user.id)
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/idc")
        response = await self.client.post(
            "accounts", json={"customer_id": customer.id, "signing_entity_id": entity.id, "company_id": company.id}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.account_id = response.json()["data"]["id"]
        self.counter = 0

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    def parameters(self, code="NET.DIA.DC"):
        result = {}
        for item in CATALOG[code]["fields"]:
            if item.get("when"):
                continue
            result[item["key"]] = (
                "100"
                if item["type"] == "number"
                else item["options"][0]["value"] if item["type"] == "select" else "Test"
            )
        if code.startswith("IP.V"):
            result["prefix"] = "/24" if code.endswith("4") else "/48"
        return result

    async def post(self, path, data):
        response = await self.client.post(path, json=data)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def order(self, action="new", source=None, code="NET.DIA.DC", parameters=None):
        self.counter += 1
        return await self.post(
            "orders",
            {
                "request_key": f"test-order-key-{self.counter:08d}",
                "account_id": self.account_id,
                "title": "IDC Order",
                "contact": "Customer contact",
                "action": action,
                "lines": [
                    {
                        "product_code": code,
                        "parameters": parameters or self.parameters(code),
                        "source_service_id": source,
                    }
                ],
            },
        )

    async def quote(self, order, charges=None, procurement=""):
        line = order["lines"][0]
        charges = charges or [
            {"code": "monthly", "name": "DIA", "kind": "recurring", "amount": "300"},
            {"code": "setup", "name": "Installation", "kind": "nrc", "amount": "100"},
        ]
        result = await self.post(
            f"lines/{line['id']}/quotes",
            {
                "revision": line["revision"],
                "currency": "USD",
                "valid_until": "2099-12-31",
                "terms": "Customer agreed actual calendar day proration",
                "charges": charges,
                "procurement_reference": procurement,
            },
        )
        for action in ["approve", "confirm"]:
            result = await self.post(
                f"lines/{line['id']}/decision",
                {
                    "version": result["lines"][0]["quote_version"],
                    "action": action,
                    "evidence": "Confirmed in signed order",
                },
            )
        return result

    async def deliver(self, order, resources=None):
        line = order["lines"][0]
        for task in line["tasks"]:
            await self.post(f"tasks/{task['id']}", {"status": "done", "evidence": "Tested"})
        return await self.post(
            f"lines/{line['id']}/delivery",
            {
                "revision": line["revision"],
                "actual_parameters": line["parameters"],
                "values": {name: "Delivered and tested" for name in line["schema_snapshot"]["delivery_fields"]},
                "evidence": "Acceptance report",
                "resources": resources or [],
            },
        )

    async def accept(self, order, start="2026-09-10"):
        line = order["lines"][0]
        return await self.post(
            f"lines/{line['id']}/accept",
            {
                "revision": line["revision"],
                "quote_version": line["quote_version"],
                "starts_on": start,
                "evidence": "Customer acceptance",
            },
        )

    async def activate(self, start="2026-09-10", action="new", source=None, charges=None):
        return await self.accept(await self.deliver(await self.quote(await self.order(action, source), charges)), start)

    async def generate(self, month="2026-09-01", dry_run=False):
        return await self.post("billing/generate", {"account_id": self.account_id, "month": month, "dry_run": dry_run})

    async def test_end_to_end_proration_nrc_repeat_accept_and_billing(self):
        order = await self.activate()
        await self.accept(order)
        self.assertEqual(await CustomerService.all().count(), 1)
        self.assertEqual(await ServiceVersion.all().count(), 1)
        preview = await self.generate(dry_run=True)
        self.assertEqual(preview["previews"][0]["total_amount"], "310.00")
        self.assertEqual(await Bill.all().count(), 0)
        first = await self.generate()
        second = await self.generate()
        self.assertEqual(first["created"][0]["bill_id"], second["created"][0]["bill_id"])
        self.assertEqual(await Bill.all().count(), 1)
        self.assertEqual(await IdcBillAllocation.all().count(), 2)
        await self.post(
            f"billing/{first['created'][0]['bill_id']}/decision", {"action": "approve", "comment": "Checked"}
        )
        repeated = await self.generate()
        self.assertFalse(repeated["created"])
        october = await self.generate("2026-10-01")
        self.assertEqual(october["previews"][0]["total_amount"], "300.00")

    async def test_retail_requires_procurement_reference(self):
        order = await self.order(code="NET.DIA.RETAIL")
        line = order["lines"][0]
        response = await self.client.post(
            f"lines/{line['id']}/quotes",
            json={
                "revision": 1,
                "valid_until": "2099-01-01",
                "terms": "terms",
                "charges": [{"code": "mrc", "name": "DIA", "kind": "recurring", "amount": "300"}],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(await IdcQuote.all().count(), 0)

    async def test_quote_only_does_not_activate(self):
        order = await self.quote(await self.order(action="quote"))
        self.assertEqual(order["lines"][0]["stage"], "quote_done")
        self.assertEqual(await CustomerService.all().count(), 0)
        response = await self.client.post(
            f"lines/{order['lines'][0]['id']}/accept",
            json={"revision": 1, "quote_version": 1, "starts_on": "2026-09-10", "evidence": "Test"},
        )
        self.assertEqual(response.status_code, 409)

    async def test_support_completion_never_creates_charges(self):
        source = (await self.activate())["lines"][0]["service_id"]
        order = await self.order(action="incident", source=source)
        await self.post(f"lines/{order['lines'][0]['id']}/support-complete", {"status": "done", "evidence": "Resolved"})
        self.assertEqual(await ServiceVersion.all().count(), 1)

    async def test_monthly_change_splits_period_and_keeps_service_id(self):
        source = (await self.activate(start="2026-09-01"))["lines"][0]["service_id"]
        changed = await self.activate(
            start="2026-09-16",
            action="change",
            source=source,
            charges=[{"code": "monthly", "name": "DIA upgraded", "kind": "recurring", "amount": "600"}],
        )
        self.assertEqual(changed["lines"][0]["service_id"], source)
        self.assertEqual((await self.generate())["previews"][0]["total_amount"], "550.00")

    async def test_terminated_service_still_gets_final_bill(self):
        source = (await self.activate(start="2026-09-01"))["lines"][0]["service_id"]
        await self.activate(
            start="2026-09-16",
            action="terminate",
            source=source,
            charges=[{"code": "close", "name": "Closure", "kind": "nrc", "amount": "0", "treatment": "free"}],
        )
        result = await self.generate()
        self.assertEqual(result["previews"][0]["total_amount"], "250.00")
        self.assertFalse((await self.generate("2026-10-01"))["created"])

    async def test_missing_usage_blocks_billing(self):
        await self.activate(
            charges=[
                {
                    "code": "usage",
                    "name": "Usage",
                    "kind": "usage",
                    "amount": "2",
                    "meter_rule": "Verified meter, complete monthly window",
                }
            ]
        )
        result = await self.generate()
        self.assertTrue(result["blocked"])
        self.assertEqual(await Bill.all().count(), 0)
        service = (await self.client.get("services")).json()["data"]["items"][0]
        charge = service["versions"][0]["charges"][0]
        await self.post(
            "usage",
            {
                "charge_id": charge["id"],
                "starts_on": "2026-09-10",
                "ends_before": "2026-10-01",
                "quantity": "12",
                "evidence": "Meter report",
            },
        )
        self.assertEqual((await self.generate())["previews"][0]["total_amount"], "24.00")

    async def test_legacy_bill_mutation_is_blocked(self):
        await self.activate()
        bill = (await self.generate())["created"][0]["bill_id"]
        response = await self.client.delete(f"http://test/api/v1/bill/delete?bill_id={bill}")
        self.assertEqual(response.status_code, 409)

    async def test_invalid_account_mapping_and_customer_permissions(self):
        self.user = await User.create(username="customer", email="customer@example.test")
        response = await self.client.get("orders")
        self.assertEqual(response.status_code, 403)
        self.app.dependency_overrides.clear()
        response = await self.client.get("orders")
        self.assertEqual(response.status_code, 422)

    async def test_all_templates_and_burst_limits(self):
        for code in CATALOG:
            values = self.parameters(code)
            validate_parameters(code, values)
        values = self.parameters("NET.IEPL")
        values.update({"burst": "yes", "burst_limit": "200", "burst_rule": "meter"})
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            validate_parameters("NET.IEPL", values)

    async def test_void_regeneration_preserves_original_allocations(self):
        await self.activate()
        original = (await self.generate())["created"][0]["bill_id"]
        await self.post(f"billing/{original}/decision", {"action": "void", "comment": "Correct draft"})
        replacement = (await self.generate())["created"][0]["bill_id"]
        self.assertNotEqual(original, replacement)
        await self.generate()
        self.assertEqual(await IdcBillAllocation.filter(item__bill_id=original).count(), 2)
        self.assertEqual(await IdcBillAllocation.filter(item__bill_id=replacement).count(), 2)
        self.assertEqual((await Bill.get(id=original)).status, "void")

    async def test_revise_requires_new_quote_and_confirmation(self):
        order = await self.deliver(await self.quote(await self.order()))
        line = order["lines"][0]
        revised = await self.post(
            f"lines/{line['id']}/decision",
            {"version": 1, "action": "revise", "evidence": "Customer changed specification"},
        )
        self.assertEqual(revised["lines"][0]["revision"], 2)
        self.assertEqual(revised["lines"][0]["stage"], "draft")
        response = await self.client.post(
            f"lines/{line['id']}/accept",
            json={"revision": 1, "quote_version": 1, "starts_on": "2026-09-10", "evidence": "Outdated"},
        )
        self.assertEqual(response.status_code, 409)
        accepted = await self.accept(await self.deliver(await self.quote(revised)))
        self.assertEqual(accepted["lines"][0]["quote_version"], 2)

    async def test_draft_cancel_and_legacy_ticket_delete_guard(self):
        order = await self.order()
        response = await self.client.delete(f"http://test/api/v1/ticket/delete?ticket_id={order['ticket_id']}")
        self.assertEqual(response.status_code, 409)
        cancelled = await self.post(
            f"lines/{order['lines'][0]['id']}/decision",
            {"version": 0, "action": "cancel", "evidence": "No longer required"},
        )
        self.assertEqual(cancelled["lines"][0]["stage"], "cancelled")

    async def test_resource_overlap_rollback(self):
        from app.models.idc import ServiceResourceBinding

        first = await self.quote(await self.order())
        second = await self.quote(await self.order())
        for order, prefix, expected in [(first, "192.0.2.0/24", 200), (second, "192.0.2.0/25", 409)]:
            line = order["lines"][0]
            response = await self.client.post(
                f"lines/{line['id']}/delivery",
                json={
                    "revision": 1,
                    "actual_parameters": line["parameters"],
                    "values": {name: "Test" for name in line["schema_snapshot"]["delivery_fields"]},
                    "evidence": "Reserved",
                    "resources": [{"kind": "ip", "key": prefix}],
                },
            )
            self.assertEqual(response.status_code, expected, response.text)
        self.assertEqual(await ServiceResourceBinding.exclude(state="released").count(), 1)

    async def test_quarterly_advance_and_unapproved_payment_guard(self):
        await self.activate(
            start="2026-09-01",
            charges=[
                {
                    "code": "quarter",
                    "name": "Quarterly",
                    "kind": "recurring",
                    "amount": "900",
                    "interval": 3,
                    "timing": "advance",
                }
            ],
        )
        result = await self.generate()
        self.assertEqual(result["previews"][0]["total_amount"], "900.00")
        self.assertFalse((await self.generate("2026-10-01"))["created"])
        self.assertEqual((await self.generate("2026-12-01"))["previews"][0]["total_amount"], "900.00")
        bill = result["created"][0]["bill_id"]
        response = await self.client.post(f"http://test/api/v1/bill/{bill}/status", json={"action": "mark_paid"})
        self.assertEqual(response.status_code, 409)

    async def test_authorized_customer_cannot_see_other_account_or_approve(self):
        from app.models.admin import Api, Role
        from app.models.idc import IdcAccount

        order = await self.quote(await self.order())
        customer = await User.create(username="allowed-customer", email="allowed@example.test")
        role = await Role.create(name="IDC Customer")
        for method, path in [("GET", "/orders"), ("GET", "/orders/{order_id}"), ("POST", "/lines/{line_id}/decision")]:
            api = await Api.create(method=method, path="/api/v1/idc" + path, summary="Test", tags="IDC")
            await role.apis.add(api)
        await customer.roles.add(role)
        self.user = customer
        forbidden = await self.client.get(f"orders/{order['id']}")
        self.assertEqual(forbidden.status_code, 403)

        self.assertEqual((await self.client.get("orders")).json()["data"]["total"], 0)
        await IdcAccount.filter(id=self.account_id).update(user_ids=[customer.id])
        self.assertEqual((await self.client.get("orders")).json()["data"]["total"], 1)
        forbidden = await self.client.post(
            f"lines/{order['lines'][0]['id']}/decision", json={"version": 1, "action": "approve", "evidence": "Attempt"}
        )
        self.assertEqual(forbidden.status_code, 403)

    async def test_catalog_menu_setup_is_repeatable(self):
        from app.models.admin import Menu, Role
        from app.services.idc_setup import setup_idc

        role = await Role.create(name="sales")
        await setup_idc()
        await setup_idc()
        self.assertEqual(await Menu.filter(path__startswith="/idc").count(), 4)
        self.assertEqual(await role.menus.all().count(), 3)

    async def test_resource_replacement_and_renewal_preserve_correct_locks(self):
        from app.models.idc import ServiceResourceBinding

        original = await self.accept(
            await self.deliver(await self.quote(await self.order()), [{"kind": "circuit", "key": "circuit-A"}]),
            "2026-09-01",
        )
        service_id = original["lines"][0]["service_id"]
        changed = await self.quote(await self.order("change", service_id))
        await self.accept(await self.deliver(changed, [{"kind": "circuit", "key": "circuit-B"}]), "2026-09-16")
        self.assertEqual((await ServiceResourceBinding.get(resource_key="circuit-A")).state, "released")
        self.assertEqual((await ServiceResourceBinding.get(resource_key="circuit-B")).state, "active")
        renewed = await self.quote(await self.order("renew", service_id))
        await self.accept(await self.deliver(renewed), "2026-09-20")
        self.assertEqual((await ServiceResourceBinding.get(resource_key="circuit-B")).state, "active")

    async def test_credit_is_idempotent_and_cannot_exceed_original_bill(self):
        await self.activate()
        bill_id = (await self.generate())["created"][0]["bill_id"]
        await self.post(f"billing/{bill_id}/decision", {"action": "approve", "comment": "Checked"})
        payload = {
            "request_key": "credit-test-00000001",
            "account_id": self.account_id,
            "source_bill_id": bill_id,
            "currency": "USD",
            "kind": "credit",
            "amount": "-200",
            "due_on": "2026-10-01",
            "description": "Credit agreed",
        }
        first = await self.post("billing/events", payload)
        self.assertEqual((await self.post("billing/events", payload))["id"], first["id"])
        payload["request_key"] = "credit-test-00000002"
        response = await self.client.post("billing/events", json=payload)
        self.assertEqual(response.status_code, 409)
