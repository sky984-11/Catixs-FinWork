import json
import unittest

from tortoise import Tortoise

from app.api.v1.product_center import list_attributes
from app.models.product_center import ProductCategory, ProductSpecAttribute


class ProductAttributeFilterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()
        old_parent = await ProductCategory.create(name="Compute", code="CAT002")
        new_parent = await ProductCategory.create(name="Compute", code="IDC.COMPUTE")
        self.old = await ProductCategory.create(name="Physical", parent=old_parent)
        self.current = await ProductCategory.create(name="Physical", parent=new_parent)
        cloud = await ProductCategory.create(name="Cloud", parent=old_parent)
        other_parent = await ProductCategory.create(name="Other")
        other = await ProductCategory.create(name="Physical", parent=other_parent)
        for code in ("disk_total", "mem_total", "cpu_core", "cpu_num", "cpu_model"):
            await ProductSpecAttribute.create(
                name=code, code=code, category=self.old,
                category_ids=[cloud.id, self.old.id] if code != "cpu_model" else [],
            )
        await ProductSpecAttribute.create(name="Unrelated", code="unrelated", category=other)

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def query(self, category_id, page=1, page_size=20):
        response = await list_attributes(
            page=page, page_size=page_size, keyword="", attr_type="", category_id=category_id,
        )
        return json.loads(response.body)

    async def test_duplicate_paths_include_multi_category_and_legacy_attributes(self):
        old = await self.query(self.old.id)
        current = await self.query(self.current.id)
        self.assertEqual(current["total"], 5)
        self.assertEqual({row["id"] for row in old["data"]}, {row["id"] for row in current["data"]})
        self.assertNotIn("unrelated", {row["code"] for row in current["data"]})
        self.assertEqual(await ProductCategory.all().count(), 7)
        self.assertEqual(await ProductSpecAttribute.filter(category_id=self.old.id).count(), 5)

    async def test_pagination_clear_and_missing_category(self):
        first = await self.query(self.current.id, page_size=2)
        last = await self.query(self.current.id, page=3, page_size=2)
        self.assertEqual(first["total"], 5)
        self.assertEqual(len(first["data"]), 2)
        self.assertEqual(len(last["data"]), 1)
        self.assertEqual((await self.query(None))["total"], 6)
        self.assertEqual((await self.query(999999))["total"], 0)
