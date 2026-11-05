import unittest

from tortoise import Tortoise

from app.models.product_center import ProductCategory, ProductItem, ProductSpecAttribute, ProductTemplate
from scripts.merge_duplicate_product_categories import merge_categories


class MergeProductCategoriesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await Tortoise.init(db_url="sqlite://:memory:", modules={"models": ["app.models"]})
        await Tortoise.generate_schemas()

    async def asyncTearDown(self):
        await Tortoise.close_connections()

    async def test_merge_preserves_products_attributes_templates_and_unique_children(self):
        keep = await ProductCategory.create(name="Cloud", code="IDC.CLOUD")
        old = await ProductCategory.create(name="Cloud", code="CAT004")
        leaf = await ProductCategory.create(name="Connect", parent=keep, level=2)
        duplicate = await ProductCategory.create(name="Connect", parent=old, level=2)
        unique = await ProductCategory.create(name="Peering", parent=old, level=2)
        product = await ProductItem.create(name="Service", category=duplicate)
        template = await ProductTemplate.create(name="Template", category=old)
        attribute = await ProductSpecAttribute.create(
            name="Speed", code="speed", category=duplicate, category_ids=[duplicate.id, leaf.id, unique.id]
        )
        preview = await merge_categories()
        self.assertEqual(preview["merged_categories"], 2)
        self.assertEqual(await ProductCategory.all().count(), 5)
        await merge_categories(apply=True)
        await product.refresh_from_db()
        await template.refresh_from_db()
        await attribute.refresh_from_db()
        await unique.refresh_from_db()
        self.assertEqual(product.category_id, leaf.id)
        self.assertEqual(template.category_id, keep.id)
        self.assertEqual(attribute.category_id, leaf.id)
        self.assertEqual(attribute.category_ids, [leaf.id, unique.id])
        self.assertEqual(unique.parent_id, keep.id)
        self.assertEqual(await ProductCategory.all().count(), 3)
        self.assertEqual((await merge_categories(apply=True))["merged_categories"], 0)

    async def test_mismatched_names_abort_without_deleting(self):
        await ProductCategory.create(name="Custom", code="CAT001")
        await ProductCategory.create(name="Datacenter", code="IDC.DC")
        with self.assertRaises(ValueError):
            await merge_categories(apply=True)
        self.assertEqual(await ProductCategory.all().count(), 2)
