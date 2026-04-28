import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from tortoise.expressions import Q

from app.controllers.vendor import vendor_controller
from app.models.company import Company
from app.schemas.base import Success, SuccessExtra
from app.schemas.vendors import VendorCreate, VendorUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="查看供应商列表")
async def list_vendor(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    name: str = Query("", description="供应商名称，用于搜索"),
    code: str = Query("", description="供应商编号"),
    status: bool | None = Query(None, description="启用状态"),
):
    q = Q()
    if name:
        q &= Q(name__contains=name)
    if code:
        q &= Q(code__contains=code)
    if status is not None:
        q &= Q(status=status)

    total, vendor_objs = await vendor_controller.list_vendors(page=page, page_size=page_size, search=q)
    data = [await obj.to_dict() for obj in vendor_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看供应商")
async def get_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    vendor_obj = await vendor_controller.get(id=vendor_id)
    return Success(data=await vendor_obj.to_dict())


@router.post("/create", summary="创建供应商")
async def create_vendor(
    vendor_in: VendorCreate,
):
    vendor_obj = await vendor_controller.create_vendor(vendor_in)
    return Success(msg="Created Successfully", data=await vendor_obj.to_dict())


@router.post("/update", summary="更新供应商")
async def update_vendor(
    vendor_in: VendorUpdate,
):
    vendor_obj = await vendor_controller.update_vendor(id=vendor_in.id, obj_in=vendor_in)
    return Success(msg="Updated Successfully", data=await vendor_obj.to_dict())


@router.delete("/delete", summary="删除供应商")
async def delete_vendor(
    vendor_id: int = Query(..., description="供应商ID"),
):
    await vendor_controller.remove(id=vendor_id)
    return Success(msg="Deleted Successfully")


@router.get("/export", summary="导出供应商")
async def export_vendor():
    """导出所有供应商为CSV格式"""
    # 查询所有供应商
    vendors = await Company.filter(role=2).all()
    
    # 获取签约主体公司列表
    companies = await Company.filter(role=0).all()
    company_map = {c.id: c.name for c in companies}
    
    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 写入表头
    writer.writerow([
        '编号', '名称', '国家/地区', '地址', '公司邮箱', '公司电话',
        'NOC邮箱', 'NOC电话', '税号', '注册号', '签约主体', '备注', '状态'
    ])
    
    # 写入数据
    for v in vendors:
        writer.writerow([
            v.code or '',
            v.name or '',
            v.country or '',
            v.address or '',
            v.company_email or '',
            v.company_phone or '',
            v.noc_email or '',
            v.noc_phone or '',
            v.tax_no or '',
            v.registration_no or '',
            company_map.get(v.contract_company_id, '') if v.contract_company_id else '',
            v.remark or '',
            '启用' if v.status else '禁用',
        ])
    
    # 返回CSV文件
    output.seek(0)
    filename = f"vendors_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/import", summary="导入供应商")
async def import_vendor(
    file: UploadFile = File(..., description="CSV文件"),
):
    # 检查文件类型
    if not file.filename.lower().endswith('.csv'):
        return Success(msg="请上传 CSV 文件", code=400)
    
    # 读取文件内容
    content = await file.read()
    
    # 解析CSV
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            decoded = content.decode('gbk')
        except UnicodeDecodeError:
            return Success(msg="文件编码不支持，请使用 UTF-8 或 GBK 编码", code=400)
    
    reader = csv.DictReader(io.StringIO(decoded))
    
    # 获取签约主体公司列表
    companies = await Company.filter(role=0).all()
    company_map = {c.name: c.id for c in companies}
    
    success_count = 0
    error_rows = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            # 查找签约主体公司ID
            contract_company_id = None
            contract_company_name = row.get('签约主体', '').strip()
            if contract_company_name and contract_company_name in company_map:
                contract_company_id = company_map[contract_company_name]
            
            # 解析状态
            status = True
            status_str = row.get('状态', '').strip()
            if status_str in ['禁用', '停用', 'disabled', 'inactive']:
                status = False
            
            # 创建供应商
            vendor_data = {
                'name': row.get('名称', '').strip(),
                'code': row.get('编号', '').strip(),
                'country': row.get('国家/地区', '').strip(),
                'address': row.get('地址', '').strip(),
                'company_email': row.get('公司邮箱', '').strip(),
                'company_phone': row.get('公司电话', '').strip(),
                'noc_email': row.get('NOC邮箱', '').strip(),
                'noc_phone': row.get('NOC电话', '').strip(),
                'tax_no': row.get('税号', '').strip(),
                'registration_no': row.get('注册号', '').strip(),
                'contract_company_id': contract_company_id,
                'remark': row.get('备注', '').strip(),
                'status': status,
                'role': 2,
            }
            
            # 如果没有提供编号，自动生成
            if not vendor_data['code']:
                vendor_data['code'] = await vendor_controller.generate_code(vendor_data.get('contract_company_id'))
            
            await Company.create(**vendor_data)
            success_count += 1
            
        except Exception as e:
            error_rows.append(f"第{row_num}行: {str(e)}")
    
    msg = f"导入成功 {success_count} 条"
    if error_rows:
        msg += f"，错误: {'; '.join(error_rows[:5])}"
        if len(error_rows) > 5:
            msg += f" ... 等{len(error_rows)}条错误"
    
    return Success(msg=msg)
