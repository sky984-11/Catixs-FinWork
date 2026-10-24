"""Explicit read-only projections for the enabled Operations Center modules."""

from app.models import asset
from app.models.remote_assistance import RemoteEngineer, RemoteHands, RemoteHandsPlan
from app.models.ticket import TicketReply


def entry(model, path, fields):
    return model, path, tuple(("id " + fields + " created_at updated_at").split())


OPS_DATASETS = {
    "regions": entry(asset.AssetRegion, "/api/v1/asset/region/list", "name code country city remark status"),
    "locations": entry(asset.AssetLocation, "/api/v1/asset/location/list", "region_id name type address remark status"),
    "devices": entry(
        asset.AssetDevice,
        "/api/v1/asset/device/list",
        "cabinet_id customer_id region_id location_id asset_no name type brand model serial_no "
        "u_position u_height status mgmt_ip business_ip owner purchase_date warranty_expire remark",
    ),
    "device_brands": entry(asset.AssetDeviceBrand, "/api/v1/asset/device-brand/list", "name sort status"),
    "device_models": entry(asset.AssetDeviceModel, "/api/v1/asset/device-brand/list", "brand_id name sort status"),
    "inventory": entry(
        asset.AssetInventory,
        "/api/v1/asset/inventory/list",
        "region_id location_id type subtype quantity threshold cost_price cost_price_currency "
        "sale_price sale_price_currency remark status",
    ),
    "inventory_categories": entry(
        asset.AssetInventoryCategory, "/api/v1/asset/inventory-category/list", "name parent_id sort status"
    ),
    "inventory_flows": entry(
        asset.AssetInventoryStockFlow,
        "/api/v1/asset/inventory-flow/list",
        "inventory_id flow_type quantity_before quantity_change quantity_after biz_type biz_id " "remark created_by",
    ),
    "inventory_sales": entry(
        asset.AssetInventorySaleOrder,
        "/api/v1/asset/inventory-sale/list",
        "sale_no customer_name customer_contact sale_date status total_amount remark created_by "
        "canceled_at canceled_by cancel_reason",
    ),
    "inventory_sale_items": entry(
        asset.AssetInventorySaleItem,
        "/api/v1/asset/inventory-sale/list",
        "sale_order_id inventory_id type subtype quantity cost_price cost_price_currency "
        "unit_price unit_price_currency amount remark",
    ),
    "dhcp_pools": entry(
        asset.CloudDhcpPool,
        "/api/v1/pve/dhcp-pools",
        "name region_id location_id region_code region_name vlan gateway cidr start_ip end_ip dns status remark",
    ),
    "dhcp_leases": entry(
        asset.CloudDhcpLease,
        "/api/v1/pve/dhcp-pools",
        "pool_id product_id price_id ip remote vmid lease_source vlan gateway cidr os_type os_version "
        "cpu_cores memory_gb disk_gb expiry_date status remark",
    ),
    "cloud_bindings": entry(asset.PveNodeBinding, "/api/v1/pve/nodes", "remote region_id location_id device_id remark"),
    "vm_metadata": entry(
        asset.PveVmMetadata,
        "/api/v1/pve/vms",
        "remote vmid vm_name customer_id customer_name cpu_cores memory_gb disk_gb remark",
    ),
    "remote_engineers": entry(
        RemoteEngineer,
        "/api/v1/remote-assistance/overview",
        "source_id name contact wechat_id wechat_group region is_active note billing_rules",
    ),
    "remote_logs": entry(
        RemoteHands,
        "/api/v1/remote-assistance/overview",
        "source_id customer_id customer ticket engineer_id engineer_name region site rack timezone "
        "arrived_at left_at work_minutes status is_settled ops_settlement_status customer_settlement_status note billing_data",
    ),
    "remote_plans": entry(
        RemoteHandsPlan,
        "/api/v1/remote-assistance/overview",
        "customer_id customer ticket engineer_id engineer_name assignee_id assignee_name assignee_names "
        "created_by_id created_by_name region site rack timezone planned_at status notify_status "
        "notified_at remote_hands_id note customer_pricing",
    ),
    "ticket_replies": entry(TicketReply, None, "ticket_id user_id parent_id reply_to_user_id content"),
}
