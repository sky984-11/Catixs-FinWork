from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.asset import AssetCabinet, AssetDevice, AssetInventory, AssetLocation, AssetRegion
from app.schemas.assets import (
    AssetCabinetCreate,
    AssetCabinetUpdate,
    AssetDeviceCreate,
    AssetDeviceUpdate,
    AssetInventoryCreate,
    AssetInventoryUpdate,
    AssetLocationCreate,
    AssetLocationUpdate,
    AssetRegionCreate,
    AssetRegionUpdate,
)


class AssetRegionController(CRUDBase[AssetRegion, AssetRegionCreate, AssetRegionUpdate]):
    def __init__(self):
        super().__init__(model=AssetRegion)

    async def list_regions(self, page: int, page_size: int, search: Q = Q()):
        return await self.list(page=page, page_size=page_size, search=search, order=["code", "id"])


class AssetLocationController(CRUDBase[AssetLocation, AssetLocationCreate, AssetLocationUpdate]):
    def __init__(self):
        super().__init__(model=AssetLocation)

    async def list_locations(self, page: int, page_size: int, search: Q = Q()):
        return await self.list(page=page, page_size=page_size, search=search, order=["region_id", "type", "id"])


class AssetCabinetController(CRUDBase[AssetCabinet, AssetCabinetCreate, AssetCabinetUpdate]):
    def __init__(self):
        super().__init__(model=AssetCabinet)

    async def list_cabinets(self, page: int, page_size: int, search: Q = Q()):
        return await self.list(page=page, page_size=page_size, search=search, order=["location_id", "code", "id"])


class AssetDeviceController(CRUDBase[AssetDevice, AssetDeviceCreate, AssetDeviceUpdate]):
    def __init__(self):
        super().__init__(model=AssetDevice)

    async def list_devices(self, page: int, page_size: int, search: Q = Q()):
        return await self.list(page=page, page_size=page_size, search=search, order=["-u_position", "-id"])

    async def create_device(self, obj_in: AssetDeviceCreate) -> AssetDevice:
        data = obj_in.model_dump()
        await self.fill_location_fields(data)
        return await self.create(data)

    async def update_device(self, id: int, obj_in: AssetDeviceUpdate) -> AssetDevice:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        if "cabinet_id" in data:
            await self.fill_location_fields(data)
        return await self.update(id=id, obj_in=data)

    async def fill_location_fields(self, data: dict) -> None:
        cabinet = await AssetCabinet.get(id=data["cabinet_id"])
        location = await AssetLocation.get(id=cabinet.location_id)
        data["location_id"] = location.id
        data["region_id"] = location.region_id


class AssetInventoryController(CRUDBase[AssetInventory, AssetInventoryCreate, AssetInventoryUpdate]):
    def __init__(self):
        super().__init__(model=AssetInventory)

    async def list_inventory(self, page: int, page_size: int, search: Q = Q()):
        return await self.list(page=page, page_size=page_size, search=search, order=["type", "subtype", "id"])

    async def create_inventory(self, obj_in: AssetInventoryCreate) -> AssetInventory:
        data = obj_in.model_dump()
        await self.fill_region_field(data)
        return await self.create(data)

    async def update_inventory(self, id: int, obj_in: AssetInventoryUpdate) -> AssetInventory:
        data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        if "location_id" in data:
            await self.fill_region_field(data)
        return await self.update(id=id, obj_in=data)

    async def fill_region_field(self, data: dict) -> None:
        location = await AssetLocation.get(id=data["location_id"])
        data["region_id"] = location.region_id


asset_region_controller = AssetRegionController()
asset_location_controller = AssetLocationController()
asset_cabinet_controller = AssetCabinetController()
asset_device_controller = AssetDeviceController()
asset_inventory_controller = AssetInventoryController()
