import asyncio
import importlib
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.api.v1 import v1_router
from app.core.dependency import AuthControl
from app.models.admin import Api, Menu, Role, User
from app.models.crm_billing import CrmBillingAudit, CrmBillingDocument, CrmBillingPayment, CrmBillingPlan
from app.models.customer_center import CrmCustomer, CrmCustomerBill, CrmSigningEntity
from app.models.product_center import ProductItem
from app.models.product_order import ProductOrder, ProductOrderItem
from app.services.crm_billing import add_months, month_factor, run_due_plans, run_plan


class BillingMathTests(unittest.TestCase):
    def test_calendar_leap_and_anniversary(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(month_factor(date(2024, 2, 1), date(2024, 2, 29), "calendar", date(2024, 2, 1)), 1)
        self.assertEqual(
            month_factor(date(2024, 2, 15), date(2024, 2, 29), "calendar", date(2024, 2, 15)), Decimal(15) / 29
        )
        self.assertEqual(month_factor(date(2024, 1, 31), date(2024, 4, 29), "anniversary", date(2024, 1, 31)), 3)


class CrmBillingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        self.user = await User.create(username="billing-admin", email="billing@test.invalid", is_superuser=True)
        self.customer = await CrmCustomer.create(name="Short", legal_name="Formal Customer", sales_owner="sales")
        self.order = await ProductOrder.create(order_no="ORDER-1", name="Rack", customer=self.customer)
        self.product = await ProductItem.create(name="Rack", code="RACK")
        await ProductOrderItem.create(
            order=self.order, product=self.product, quantity=3, currency="USD", mrc="1350", nrc="100", period_months=1
        )
        self.app = FastAPI()
        self.app.include_router(v1_router, prefix="/api/v1")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test/api/v1/")
        self.payload = {
            "title": "November billing",
            "customer_id": self.customer.id,
            "order_ids": [self.order.id],
            "currency": "USD",
            "local_currency": "USD",
            "fx_rate": "1",
            "fx_source": "Same currency",
            "fx_date": "2026-11-01",
            "period_start": "2026-11-01",
            "months": 1,
            "calendar_mode": "calendar",
            "service_start": "2026-11-01",
            "include_nrc": True,
            "payment_timing": "prepaid",
            "bill_date": "2026-11-01",
            "due_date": "2026-11-03",
            "request_key": "TEST-NOV-001",
        }

    async def asyncTearDown(self):
        await self.client.aclose()
        await Tortoise.close_connections()

    async def post(self, path, data, status=200):
        response = await self.client.post(f"crm-billing/{path}", json=data)
        self.assertEqual(response.status_code, status, response.text)
        return response.json().get("data")

    async def create(self, **changes):
        return await self.post("generate", {**self.payload, **changes})

    async def action(self, doc, action, status=200):
        return await self.post(f"bills/{doc['id']}/actions", {"action": action, "comment": "Reviewed"}, status)

    async def test_preview_generate_idempotency_and_snapshot(self):
        entity = await CrmSigningEntity.create(name="Invoice issuer", address="Test address", logo_url="/logos/test.png")
        self.customer.signing_entity = entity
        await self.customer.save()
        preview = await self.post("preview", self.payload)
        self.assertEqual(preview["customer"]["signing_entity_address"], "Test address")
        self.assertEqual(preview["customer"]["signing_entity_logo_url"], "/logos/test.png")
        self.assertEqual(preview["amount"], "4350.00")
        self.assertEqual(preview["lines"][0]["mrc_amount"], "4050.00")
        self.assertEqual(await CrmCustomerBill.all().count(), 0)
        bill = await self.create()
        repeated = await self.create()
        self.assertEqual(bill["id"], repeated["id"])
        self.assertEqual(bill["customer_name"], "Formal Customer")
        await ProductOrderItem.filter(order=self.order).update(mrc=1)
        await CrmCustomer.filter(id=self.customer.id).update(legal_name="Changed")
        await CrmSigningEntity.filter(id=entity.id).update(address="Changed address", logo_url="/logos/changed.png")
        detail = (await self.client.get(f"crm-billing/bills/{bill['id']}")).json()["data"]
        self.assertEqual(detail["customer_snapshot"]["signing_entity_address"], "Test address")
        self.assertEqual(detail["customer_snapshot"]["signing_entity_logo_url"], "/logos/test.png")
        self.assertEqual(detail["signing_entity_logo_url"], "/logos/changed.png")
        self.assertEqual(Decimal(detail["lines"][0]["mrc"]), Decimal("1350"))
        self.assertEqual(detail["customer_name"], "Formal Customer")
        await self.post("generate", {**self.payload, "request_key": "TEST-DUP-002"}, 409)
        await self.post("generate", {**self.payload, "title": "Changed"}, 409)
        self.assertEqual(await CrmBillingDocument.all().count(), 1)

    async def test_prorating_discount_tax_fx_and_nrc_once(self):
        first = await self.create(
            service_start="2026-11-16",
            discount="25",
            adjustment="10",
            adjustment_reason="Discount",
            tax_rate="10",
            local_currency="CNY",
            fx_rate="7",
            fx_source="Contract",
        )
        self.assertEqual(first["lines"][0]["mrc_amount"], "2025.00")
        self.assertEqual(first["amount"], "2541.00")
        self.assertEqual(first["local_amount"], "17787.00")
        second = await self.create(period_start="2026-12-01", request_key="TEST-DEC-001")
        self.assertEqual(second["lines"][0]["nrc_amount"], "0.00")
        self.assertEqual(second["amount"], "4050.00")

    async def test_lock_partial_payment_reversal_and_overdue(self):
        bill = await self.create()
        payment = {
            "reference": "BANK-1",
            "payment_date": "2026-11-02",
            "amount": "1000",
            "currency": "USD",
            "method": "Bank",
            "remark": "",
        }
        path = f"bills/{bill['id']}/payments"
        await self.post(path, payment, 409)
        await self.action(bill, "issue")
        paid = await self.post(path, payment)
        self.assertEqual(paid["status"], "partial")
        self.assertEqual(paid["outstanding"], "3350.00")
        await self.post(path, payment)
        self.assertEqual(await CrmBillingPayment.all().count(), 1)
        await self.post(path, {**payment, "reference": "BANK-2", "amount": "3350.01"}, 422)
        await self.post(path, {**payment, "reference": "BANK-2", "currency": "CNY"}, 422)
        await self.action(bill, "void", 422)
        completed = await self.post(path, {**payment, "reference": "BANK-2", "amount": "3350"})
        self.assertEqual(completed["status"], "paid")
        self.assertTrue(completed["is_settled"])
        undone = await self.post(f"{path}/{paid['payments'][0]['id']}/reverse", {"reason": "Correction"})
        self.assertEqual(undone["status"], "partial")
        self.assertEqual(undone["outstanding"], "1000.00")
        with (
            patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)),
            patch("app.api.v1.crm_billing.today", return_value=date(2026, 11, 6)),
        ):
            reminder = await self.action(bill, "remind")
            self.assertEqual(reminder["reminder_level"], 1)
            self.assertEqual(reminder["overdue_days"], 3)
            response = await self.client.get("crm-billing/bills", params={"overdue": "true"})
            self.assertEqual(response.json()["total"], 1)
            self.assertEqual(response.json()["summary"][0]["overdue"], "1000.00")

    async def test_draft_edit_and_legacy_bypass_protection(self):
        bill = await self.create()
        terms = {
            key: bill["settings"][key]
            for key in (
                "title",
                "bill_date",
                "due_date",
                "discount",
                "adjustment",
                "adjustment_reason",
                "tax_rate",
                "remark",
                "local_currency",
                "fx_rate",
                "fx_source",
                "fx_date",
            )
        }
        response = await self.client.put(
            f"crm-billing/bills/{bill['id']}", json={**terms, "discount": "100", "adjustment_reason": "Offer"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["amount"], "4250.00")
        await self.action(bill, "issue")
        self.assertEqual((await self.client.put(f"crm-billing/bills/{bill['id']}", json=terms)).status_code, 409)
        self.assertEqual((await self.client.delete(f"customer-center/bills/{bill['bill_id']}")).status_code, 409)
        self.assertEqual(
            (
                await self.client.put(
                    f"customer-center/bills/{bill['bill_id']}",
                    json={"customer_id": self.customer.id, "title": "Bypass", "amount": 1},
                )
            ).status_code,
            409,
        )
        self.assertEqual((await self.client.delete(f"product-center/orders/{self.order.id}")).status_code, 409)
        await self.action(bill, "void", 422)
        # Historical void records remain readable and do not reserve a billing period.
        await CrmCustomerBill.filter(id=bill["bill_id"]).update(status="void")
        replacement = await self.create(request_key="TEST-REPLACEMENT")
        self.assertEqual(replacement["amount"], "4350.00")
        self.assertGreaterEqual(await CrmBillingAudit.all().count(), 3)

    async def test_validation_scope_and_unpriced_orders(self):
        for changes in (
            {"months": 2},
            {"order_ids": []},
            {"service_end": "2025-01-01"},
            {"discount": "5"},
            {"tax_rate": "101"},
            {"fx_rate": "0"},
            {"local_currency": "USD", "fx_rate": "7"},
            {"discount": "50000", "adjustment_reason": "Invalid"},
            {"calendar_mode": "anniversary", "period_start": "2026-11-02"},
        ):
            await self.post("preview", {**self.payload, **changes}, 422)
        other = await CrmCustomer.create(name="Other")
        await self.post("generate", {**self.payload, "customer_id": other.id}, 422)
        await ProductOrderItem.filter(order=self.order).update(mrc=None)
        await self.post("generate", self.payload, 422)
        self.assertEqual(await CrmBillingDocument.all().count(), 0)

    async def test_auth_and_sales_data_scope(self):
        bill = await self.create()
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get("crm-billing/bills")).status_code, 401)
        self.user = await User.create(username="someone", email="sales@test.invalid")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.assertEqual((await self.client.get("crm-billing/bills")).status_code, 403)
        role = await Role.create(name="sales")
        await self.user.roles.add(role)
        for path in ("/api/v1/crm-billing/bills", "/api/v1/crm-billing/bills/{document_id}"):
            await role.apis.add(await Api.create(path=path, method="GET", summary="Billing", tags="Billing"))
        self.assertEqual((await self.client.get("crm-billing/bills")).json()["total"], 0)
        self.assertEqual((await self.client.get(f"crm-billing/bills/{bill['id']}")).status_code, 404)
        await CrmCustomer.filter(id=self.customer.id).update(sales_owner=self.user.username)
        self.assertEqual((await self.client.get("crm-billing/bills")).json()["total"], 1)

    async def test_automatic_plans_snapshot_retry_and_end(self):
        plan = await self.post("plans", {**self.payload, "service_end": "2026-12-15"})
        await self.post("plans", self.payload, 409)
        await ProductOrderItem.filter(order=self.order).update(mrc=1)
        with patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)):
            first = await run_plan(plan["id"])
            self.assertIsNotNone(first)
            self.assertEqual((await first.bill).amount, Decimal("4350"))
            self.assertIsNone(await run_plan(plan["id"]))
        with patch("app.services.crm_billing.today", return_value=date(2026, 12, 1)):
            await run_due_plans()
        self.assertEqual(await CrmBillingDocument.all().count(), 2)
        saved = await CrmBillingPlan.get(id=plan["id"])
        self.assertFalse(saved.enabled)
        latest = await CrmBillingDocument.all().order_by("-id").first()
        self.assertEqual(latest.lines[0]["nrc_amount"], "0.00")
        self.assertEqual(latest.lines[0]["mrc_amount"], "1959.68")
        self.assertEqual((await self.client.delete(f"product-center/orders/{self.order.id}")).status_code, 409)

    async def test_failed_plan_preserves_next_period_and_logs_reason(self):
        plan = await self.post("plans", self.payload)
        await CrmCustomer.filter(id=self.customer.id).update(status=False)
        with patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)):
            await run_due_plans()
        saved = await CrmBillingPlan.get(id=plan["id"])
        self.assertTrue(saved.last_error)
        self.assertEqual(saved.next_period, date(2026, 11, 1))
        self.assertEqual(await CrmBillingDocument.all().count(), 0)
        await CrmCustomer.filter(id=self.customer.id).update(status=True)
        with patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)):
            await run_plan(plan["id"], force=True)
        self.assertEqual(await CrmBillingDocument.all().count(), 1)

    async def test_rollback_and_migration_contents(self):
        with patch("app.services.crm_billing.audit", side_effect=RuntimeError("test rollback")):
            with self.assertRaises(RuntimeError):
                await self.create()
        self.assertEqual(await CrmCustomerBill.all().count(), 0)
        self.assertEqual(await CrmBillingDocument.all().count(), 0)
        migration = importlib.import_module("migrations.models.186_20261106120000_crm_billing")
        sql = await migration.upgrade(None)
        self.assertEqual(sql.count("CREATE TABLE"), 6)
        self.assertIn('"request_key" VARCHAR(80) NOT NULL UNIQUE', sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertIn("ON DELETE RESTRICT", sql)

    async def test_multi_currency_and_new_line_nrc(self):
        other = await ProductItem.create(name="Cross connect", code="XC")
        await ProductOrderItem.create(order=self.order, product=other, quantity=2, currency="CNY", mrc="10.10", nrc="5")
        usd = await self.create()
        cny = await self.create(currency="CNY", local_currency="CNY", request_key="TEST-CNY-001")
        self.assertEqual(usd["amount"], "4350.00")
        self.assertEqual(cny["amount"], "30.20")
        await ProductOrderItem.filter(order=self.order, product=other).update(currency="USD")
        next_bill = await self.create(period_start="2026-12-01", request_key="TEST-DEC-NEW")
        nrc_by_product = {row["product_id"]: row["nrc_amount"] for row in next_bill["lines"]}
        self.assertEqual(nrc_by_product[self.product.id], "0.00")
        self.assertEqual(nrc_by_product[other.id], "10.00")

    async def test_anniversary_quarter_and_postpaid_plan(self):
        terms = {
            **self.payload,
            "calendar_mode": "anniversary",
            "service_start": "2024-01-31",
            "period_start": "2024-01-31",
            "months": 3,
            "payment_timing": "postpaid",
        }
        preview = await self.post("preview", terms)
        self.assertEqual(preview["period_end"], "2024-04-29")
        self.assertEqual(preview["lines"][0]["mrc_amount"], "12150.00")
        plan = await self.post("plans", terms)
        self.assertEqual(plan["next_run"], "2024-04-30")
        with patch("app.services.crm_billing.today", return_value=date(2024, 4, 29)):
            self.assertIsNone(await run_plan(plan["id"]))
        with patch("app.services.crm_billing.today", return_value=date(2024, 4, 30)):
            await run_plan(plan["id"])
        saved = await CrmBillingPlan.get(id=plan["id"])
        self.assertEqual(saved.next_period, date(2024, 4, 30))
        self.assertEqual(saved.next_run, date(2024, 7, 31))
        await self.post(f"plans/{saved.id}/stop", {})
        with patch("app.services.crm_billing.today", return_value=date(2024, 8, 1)):
            self.assertIsNone(await run_plan(saved.id))

    async def test_order_customer_change_guard_and_legacy_bill_compatibility(self):
        await self.create()
        other = await CrmCustomer.create(name="Other customer")
        response = await self.client.put(
            f"product-center/orders/{self.order.id}",
            json={
                "name": self.order.name,
                "customer_id": other.id,
                "items": [{"product_id": self.product.id, "quantity": 3}],
            },
        )
        self.assertEqual(response.status_code, 409, response.text)
        old = await CrmCustomerBill.create(customer=self.customer, title="Legacy", amount=1)
        self.assertEqual((await self.client.delete(f"customer-center/bills/{old.id}")).status_code, 200)

    async def test_finance_permission_bootstrap_does_not_grant_noc_write(self):
        from app.core.init_app import (
            ensure_business_api_permissions,
            ensure_customer_center_menu,
            ensure_product_center_menu,
        )

        finance = await Role.create(name="finance")
        noc = await Role.create(name="noc")
        for method, path in [("GET", "/api/v1/crm-billing/bills"), ("POST", "/api/v1/crm-billing/generate")]:
            await Api.create(method=method, path=path, summary="Billing", tags="Billing")
        await ensure_customer_center_menu()
        customer_menu = await Menu.get(path="/customer-center")
        previous = await Menu.create(
            name="账单管理", path="billing", parent_id=customer_menu.id, component="/customer-center/billing"
        )
        await finance.menus.add(previous)
        await ensure_product_center_menu()
        await ensure_product_center_menu()
        moved = await Menu.get(id=previous.id)
        self.assertEqual(moved.component, "/product-center/billing")
        self.assertEqual(moved.parent_id, (await Menu.get(path="/product-center")).id)
        self.assertEqual(await Menu.filter(component="/product-center/billing").count(), 1)
        self.assertFalse(await Menu.filter(component="/customer-center/billing").exists())
        self.assertTrue(await finance.menus.filter(id=previous.id).exists())
        await ensure_business_api_permissions()
        self.assertTrue(await finance.apis.filter(path="/api/v1/crm-billing/generate").exists())
        self.assertFalse(await noc.apis.filter(path="/api/v1/crm-billing/generate").exists())
        self.assertTrue(await noc.apis.filter(path="/api/v1/crm-billing/bills").exists())

    async def test_preview_change_detection(self):
        preview = await self.post("preview", self.payload)
        await ProductOrderItem.filter(order=self.order).update(quantity=4)
        await self.post("generate", {**self.payload, "preview_token": preview["preview_token"]}, 409)
        self.assertEqual(await CrmBillingDocument.all().count(), 0)
        refreshed = await self.post("preview", self.payload)
        result = await self.post("generate", {**self.payload, "preview_token": refreshed["preview_token"]})
        self.assertEqual(result["amount"], "5800.00")

    async def test_plan_enable_resume_and_conflict(self):
        first = await self.post("plans", self.payload)
        await self.post(f"plans/{first['id']}/stop", {})
        second = await self.post("plans", self.payload)
        await self.post(f"plans/{first['id']}/enable", {}, 409)
        await self.post(f"plans/{second['id']}/stop", {})
        await CrmBillingPlan.filter(id=first["id"]).update(last_attempt=date(2026, 11, 6), last_error="Failed")
        await self.post(f"plans/{first['id']}/enable", {})
        await self.post(f"plans/{first['id']}/enable", {})
        saved = await CrmBillingPlan.get(id=first["id"])
        self.assertTrue(saved.enabled)
        self.assertIsNone(saved.last_attempt)
        self.assertEqual(saved.last_error, "")
        self.assertEqual(saved.next_period, date(2026, 11, 1))
        with patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)):
            await run_due_plans()
        self.assertEqual(await CrmBillingDocument.all().count(), 1)
        await self.post(f"plans/{first['id']}/stop", {})
        await self.post(f"plans/{first['id']}/enable", {})
        self.assertEqual((await CrmBillingPlan.get(id=first["id"])).next_period, date(2026, 12, 1))

    async def test_plan_deletion_stops_schedule_and_preserves_bills(self):
        plan = await self.post("plans", self.payload)
        with patch("app.services.crm_billing.today", return_value=date(2026, 11, 6)):
            await run_plan(plan["id"])
        path = f"crm-billing/plans/{plan['id']}"
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": ""})).status_code, 422)
        response = await self.client.request("DELETE", path, json={"reason": "Stop recurring billing"})
        self.assertEqual(response.status_code, 200, response.text)
        saved = await CrmBillingPlan.get(id=plan["id"])
        self.assertFalse(saved.enabled)
        self.assertIsNotNone(saved.deleted_at)
        self.assertEqual(saved.deleted_by_id, self.user.id)
        self.assertEqual(saved.deletion_reason, "Stop recurring billing")
        self.assertEqual((await self.client.get("crm-billing/plans")).json()["data"], [])
        await self.post(f"plans/{plan['id']}/enable", {}, 404)
        await self.post(f"plans/{plan['id']}/run", {}, 404)
        with patch("app.services.crm_billing.today", return_value=date(2026, 12, 6)):
            self.assertIsNone(await run_plan(plan["id"], force=True))
            await run_due_plans()
        self.assertEqual(await CrmBillingDocument.all().count(), 1)
        self.assertEqual((await CrmBillingDocument.first()).lines[0]["mrc_amount"], "4050.00")
        await self.post("plans", {**self.payload, "period_start": "2026-12-01"})

    async def test_plan_enable_checks_expiry_customer_and_permissions(self):
        plan = await self.post("plans", {**self.payload, "service_end": "2026-11-30"})
        await self.post(f"plans/{plan['id']}/stop", {})
        await CrmBillingPlan.filter(id=plan["id"]).update(next_period=date(2026, 12, 1))
        await self.post(f"plans/{plan['id']}/enable", {}, 409)
        await CrmBillingPlan.filter(id=plan["id"]).update(next_period=date(2026, 11, 1))
        await CrmCustomer.filter(id=self.customer.id).update(status=False)
        await self.post(f"plans/{plan['id']}/enable", {}, 422)
        self.app.dependency_overrides.clear()
        await self.post(f"plans/{plan['id']}/enable", {}, 401)
        self.assertEqual(
            (
                await self.client.request("DELETE", f"crm-billing/plans/{plan['id']}", json={"reason": "Denied"})
            ).status_code,
            401,
        )
        self.user = await User.create(username="plan-reader", email="plan-reader@test.invalid")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        await self.post(f"plans/{plan['id']}/enable", {}, 403)
        self.assertEqual(
            (
                await self.client.request("DELETE", f"crm-billing/plans/{plan['id']}", json={"reason": "Denied"})
            ).status_code,
            403,
        )

    async def test_soft_delete_releases_period_and_preserves_history(self):
        bill = await self.create()
        path = f"crm-billing/bills/{bill['id']}"
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": " "})).status_code, 422)
        for _ in range(2):
            response = await self.client.request("DELETE", path, json={"reason": "Wrong billing period"})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.get("crm-billing/bills")).json()["total"], 0)
        archived = (await self.client.get("crm-billing/bills", params={"status": "deleted"})).json()
        self.assertEqual(archived["total"], 1)
        self.assertEqual(archived["summary"], [])
        self.assertEqual(archived["data"][0]["outstanding"], "0.00")
        self.assertEqual((await self.client.get("customer-center/bills")).json()["total"], 0)
        detail = (await self.client.get(path)).json()["data"]
        self.assertEqual(detail["status"], "deleted")
        self.assertEqual(len(detail["lines"]), 1)
        self.assertEqual(await CrmBillingAudit.filter(document_id=bill["id"], action="delete").count(), 1)
        self.assertEqual(detail["audits"][0]["comment"], "Wrong billing period")
        await self.action(bill, "void", 422)
        await self.post("generate", self.payload, 409)
        replacement = await self.create(request_key="AFTER-DELETE")
        self.assertEqual(replacement["amount"], "4350.00")
        self.assertEqual(await CrmBillingDocument.all().count(), 2)

    async def test_delete_requires_permission_and_preserves_historical_void_support(self):
        bill = await self.create()
        path = f"crm-billing/bills/{bill['id']}"
        await self.action(bill, "issue")
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": "Invalid"})).status_code, 409)
        await self.action(bill, "void", 422)
        await CrmCustomerBill.filter(id=bill["bill_id"]).update(status="void")
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": "Archive"})).status_code, 200)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": "Denied"})).status_code, 401)
        self.user = await User.create(username="reader", email="reader@test.invalid")

        async def authed():
            return self.user

        self.app.dependency_overrides[AuthControl.is_authed] = authed
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": "Denied"})).status_code, 403)
        role = await Role.create(name="reader")
        await self.user.roles.add(role)
        await role.apis.add(
            await Api.create(
                method="DELETE", path="/api/v1/crm-billing/bills/{document_id}", summary="Delete", tags="Billing"
            )
        )
        self.assertEqual((await self.client.request("DELETE", path, json={"reason": "Other owner"})).status_code, 404)

    async def test_concurrent_requests_are_not_double_charged(self):
        responses = await asyncio.gather(
            *[
                self.client.post("crm-billing/generate", json={**self.payload, "request_key": f"PARALLEL-{index}"})
                for index in range(2)
            ]
        )
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        self.assertEqual(await CrmBillingDocument.all().count(), 1)
        document = await CrmBillingDocument.first()
        bill = await self.action({"id": document.id}, "issue")
        responses = await asyncio.gather(
            *[
                self.client.post(
                    f"crm-billing/bills/{bill['id']}/payments",
                    json={
                        "reference": f"PARALLEL-PAY-{index}",
                        "payment_date": "2026-11-02",
                        "amount": "3000",
                        "currency": "USD",
                        "method": "Bank",
                    },
                )
                for index in range(2)
            ]
        )
        self.assertEqual(sorted(response.status_code for response in responses), [200, 422])
        self.assertEqual(await CrmBillingPayment.all().count(), 1)
