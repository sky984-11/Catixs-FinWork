from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AssetRegionBase(BaseModel):
    name: str = Field(..., example="HK")
    code: str = Field(..., example="HK")
    remark: str = Field("", example="")
    status: bool = Field(True, example=True)


class AssetRegionCreate(AssetRegionBase):
    pass


class AssetRegionUpdate(AssetRegionBase):
    id: int


class AssetLocationBase(BaseModel):
    region_id: int
    name: str = Field(..., example="HK机房")
    type: int = Field(1, description="0-库存，1-机房", example=1)
    address: str = Field("", example="")
    remark: str = Field("", example="")
    status: bool = Field(True, example=True)


class AssetLocationCreate(AssetLocationBase):
    pass


class AssetLocationUpdate(AssetLocationBase):
    id: int


class AssetCabinetBase(BaseModel):
    location_id: int
    name: str = Field(..., example="A01")
    code: str = Field("", example="A01")
    row: str = Field("", example="")
    column: str = Field("", example="")
    capacity_u: int = Field(42, example=42)
    remark: str = Field("", example="")
    status: bool = Field(True, example=True)


class AssetCabinetCreate(AssetCabinetBase):
    pass


class AssetCabinetUpdate(AssetCabinetBase):
    id: int


class AssetDeviceBase(BaseModel):
    cabinet_id: int
    asset_no: str = Field(..., example="ASSET-0001")
    name: str = Field(..., example="Server-01")
    type: int = Field(0, example=0)
    brand: str = Field("", example="Dell")
    model: str = Field("", example="R750")
    serial_no: str = Field("", example="")
    u_position: Optional[int] = Field(None, example=1)
    u_height: int = Field(1, example=1)
    status: int = Field(1, example=1)
    mgmt_ip: str = Field("", example="")
    business_ip: str = Field("", example="")
    owner: str = Field("", example="")
    purchase_date: Optional[date] = None
    warranty_expire: Optional[date] = None
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        example={"CPU数量": "2", "CPU型号": "Intel Xeon Gold 5118", "内存数量": "8", "内存大小": "32G", "IPMI用户名": "admin"},
    )
    remark: str = Field("", example="")


class AssetDeviceCreate(AssetDeviceBase):
    pass


class AssetDeviceUpdate(AssetDeviceBase):
    id: int


class AssetDeviceBrandBase(BaseModel):
    name: str = Field(..., example="Dell", description="品牌名称")
    sort: int = Field(0, example=0)
    status: bool = Field(True, example=True)


class AssetDeviceBrandCreate(AssetDeviceBrandBase):
    pass


class AssetDeviceBrandUpdate(AssetDeviceBrandBase):
    id: int


class AssetDeviceModelBase(BaseModel):
    brand_id: int
    name: str = Field(..., example="R640", description="型号名称")
    sort: int = Field(0, example=0)
    status: bool = Field(True, example=True)


class AssetDeviceModelCreate(AssetDeviceModelBase):
    pass


class AssetDeviceModelUpdate(AssetDeviceModelBase):
    id: int


class AssetInventoryBase(BaseModel):
    location_id: int
    type: str = Field(..., example="光模块", description="分类")
    subtype: str = Field("", example="100G", description="子类")
    quantity: int = Field(1, example=2)
    attributes: dict[str, Any] = Field(default_factory=dict, example={"规格型号": "100G单模", "技术参数": "10km 1310nm", "兼容平台": "huawei&cisco"})
    remark: str = Field("", example="")
    status: bool = Field(True, example=True)


class AssetInventoryCreate(AssetInventoryBase):
    pass


class AssetInventoryUpdate(AssetInventoryBase):
    id: int


class AssetInventoryCategoryBase(BaseModel):
    name: str = Field(..., example="光模块", description="分类名称")
    parent_id: Optional[int] = Field(None, example=None, description="父级分类ID")
    sort: int = Field(0, example=0)
    status: bool = Field(True, example=True)


class AssetInventoryCategoryCreate(AssetInventoryCategoryBase):
    pass


class AssetInventoryCategoryUpdate(AssetInventoryCategoryBase):
    id: int


class AssetTreeNode(BaseModel):
    id: int | str
    label: str
    type: str
    raw_id: Optional[int] = None
    children: list["AssetTreeNode"] = []


class AssetDeviceOut(BaseModel):
    id: int
    cabinet_id: int
    location_id: int
    region_id: int
    asset_no: str
    name: str
    type: int
    status: int
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_no: Optional[str] = None
    mgmt_ip: Optional[str] = None
    business_ip: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
