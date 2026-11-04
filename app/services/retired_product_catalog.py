"""Remove unused product placeholders created by the retired IDC catalog seeder."""

from loguru import logger
from tortoise.transactions import in_transaction

from app.models.asset import CloudDhcpLease
from app.models.product_order import ProductOrderItem
from app.models.company import BillingProductTemplate, BillingSubscription
from app.models.idc import CustomerService, IdcOrderLine
from app.models.product_center import (ProductItem, ProductPrice,
                                       ProductPriceHistory,
                                       ProductPriceVersion, ProductSpecConfig)

# Exact codes/names from the retired catalog. Never infer placeholders from a name alone.
RETIRED_CATALOG_PRODUCTS = {
    "DC.RACK": "整柜整租",
    "DC.COLO": "散柜机位",
    "DC.XC": "Cross Connect",
    "COMPUTE.BMS": "物理服务器",
    "COMPUTE.VM": "云主机",
    "IP.V4": "IPv4",
    "IP.V6": "IPv6",
    "IP.ASN": "ASN",
    "CLOUD.IX": "IX Peering",
    "CLOUD.CONNECT": "Cloud Connect",
    "NET.TRANSIT": "IP Transit",
    "NET.DIA.DC": "DIA / Datacenter",
    "NET.DIA.RETAIL": "DIA / Retail Building",
    "NET.CHINA": "China Route 回国带宽",
    "NET.IEPL": "IEPL",
    "NET.WAVE": "Wave",
    "VAS.RH": "Remote Hands",
    "ADDON.LOCAL_LOOP": "附加本地传输",
}


async def remove_unused_retired_catalog_products() -> int:
    removed = 0
    async with in_transaction() as conn:
        products = await ProductItem.filter(code__in=list(RETIRED_CATALOG_PRODUCTS)).using_db(conn).select_for_update()
        for product in products:
            category = await product.category if product.category_id else None
            if (
                product.name != RETIRED_CATALOG_PRODUCTS[product.code]
                or not category
                or category.code != f"IDC.{product.code}.LEAF"
                or category.name != product.name
                or product.region is not None
                or product.description is not None
                or product.status != "active"
                or product.billing_mode != "fixed"
                or product.billing_unit != "month"
                or product.min_contract_months != 1
            ):
                continue
            referenced = False
            for model in (
                ProductSpecConfig,
                ProductPrice,
                ProductPriceHistory,
                ProductPriceVersion,
                ProductOrderItem,
                CloudDhcpLease,
                IdcOrderLine,
                CustomerService,
            ):
                if await model.filter(product_id=product.id).using_db(conn).exists():
                    referenced = True
                    break
            if referenced:
                continue
            if await BillingProductTemplate.filter(product_code=product.code).using_db(conn).exists():
                continue
            if await BillingSubscription.filter(product_code=product.code).using_db(conn).exists():
                continue
            await product.delete(using_db=conn)
            removed += 1
    if removed:
        logger.info("Removed {} unused retired IDC catalog product placeholders", removed)
    return removed
