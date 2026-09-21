"""Versioned product forms; these rules are also sent to the Vue form renderer."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from ipaddress import ip_network

from fastapi import HTTPException

SCHEMA_VERSION = 1
ACTIONS = {
    "quote": "询价",
    "new": "新开通",
    "change": "变更 / 升降配 / 迁移",
    "renew": "续约",
    "suspend": "暂停",
    "resume": "恢复",
    "terminate": "退订",
    "one_time": "一次性服务",
    "incident": "故障",
    "maintenance": "维护",
}


def field(key, label, kind="text", *, required=True, options=None, when=None, unit=""):
    result = {"key": key, "label": label, "type": kind, "required": required, "unit": unit}
    if options:
        result["options"] = [{"label": str(label), "value": value} for value, label in options]
    if when:
        result["when"] = when
    return result


def number(key, label, unit="", **kwargs):
    return field(key, label, "number", unit=unit, **kwargs)


def select(key, label, options, **kwargs):
    return field(key, label, "select", options=options, **kwargs)


def endpoint(side):
    return [
        field(f"{side}_location", f"{side.upper()}端位置 / 机房 / 地址"),
        select(
            f"{side}_access",
            f"{side.upper()}端接入方式",
            [("on_net", "On-net"), ("off_net", "Off-net"), ("survey", "待勘查")],
        ),
        select(
            f"{side}_local_loop",
            f"{side.upper()}端本地传输",
            [("none", "不需要"), ("own", "我方提供（附加明细）"), ("included", "主产品已含"), ("customer", "客户自备")],
        ),
        field(
            f"{side}_carrier", f"{side.upper()}端接入供应商 / 客户线路", when={f"{side}_access": ["off_net", "survey"]}
        ),
    ]


REGION = field("region", "地区")
DC = field("datacenter", "机房")
BANDWIDTH = number("bandwidth", "承诺带宽", "Mbps")
PORT = number("port_speed", "端口速率", "Mbps")
IP_NEED = field("ip_requirement", "IP / 前缀需求")
BURST = [
    select("burst", "是否突发", [("no", "否"), ("yes", "是")]),
    number("burst_limit", "突发上限", "Mbps", when={"burst": ["yes"]}),
    field("burst_rule", "突发计量与结算规则", when={"burst": ["yes"]}),
]
PROTECTION = select("protection", "保护方式", [("none", "无保护"), ("protected", "保护线路"), ("diverse", "双路由")])
DEFINITIONS = [
    (
        "DC.RACK",
        "机房资源",
        "整柜整租",
        [
            DC,
            number("rack_u", "每柜高度", "U"),
            number("power_kw", "每柜电力", "kW"),
            field("power_feed", "A/B路供电要求"),
        ],
        ["实际柜号", "电力交付配置"],
    ),
    (
        "DC.COLO",
        "机房资源",
        "散柜机位",
        [
            DC,
            number("device_count", "设备台数"),
            number("u_height", "每台高度", "U"),
            number("power_kw", "额定电力", "kW"),
        ],
        ["柜号与U位", "设备ID与电力配置"],
    ),
    (
        "DC.XC",
        "机房资源",
        "Cross Connect",
        [
            DC,
            field("a_location", "A端主体与位置"),
            field("z_location", "Z端主体与位置"),
            field("media", "介质"),
            number("pairs", "芯数 / 对数"),
            field("connector", "接头"),
            field("loa", "LOA / 授权资料", required=False),
        ],
        ["XC编号", "两端配线架与端口", "线路测试结果"],
    ),
    (
        "COMPUTE.BMS",
        "计算资源",
        "物理服务器",
        [
            DC,
            field("cpu", "CPU型号与核心"),
            number("memory", "内存", "GiB"),
            field("disk", "磁盘配置"),
            BANDWIDTH,
            field("os", "操作系统"),
            field("node", "四节点名称", required=False),
        ],
        ["设备ID或子节点", "实际配置", "IP与测试结果"],
    ),
    (
        "COMPUTE.VM",
        "计算资源",
        "云主机",
        [
            field("pool", "资源池 / 可用区"),
            number("vcpu", "vCPU"),
            number("memory", "内存", "GiB"),
            number("disk", "磁盘", "GiB"),
            field("os", "操作系统"),
            field("network", "网络 / VLAN / DHCP"),
        ],
        ["remote与vmid", "实际规格", "IP与测试结果"],
    ),
    (
        "IP.V4",
        "互联网资源",
        "IPv4",
        [
            select("source", "资源来源", [("allocated", "新分配"), ("customer", "客户自带")]),
            field("prefix", "CIDR前缀或需求前缀长度"),
            field("purpose", "用途"),
            field("routing", "路由 / 宣告方式"),
            field("asn", "目标ASN", required=False),
        ],
        ["实际地址段", "分配ID与宣告记录"],
    ),
    (
        "IP.V6",
        "互联网资源",
        "IPv6",
        [
            select("source", "资源来源", [("allocated", "新分配"), ("customer", "客户自带")]),
            field("prefix", "CIDR前缀或需求前缀长度"),
            field("purpose", "用途"),
            field("routing", "路由 / 宣告方式"),
            field("asn", "目标ASN", required=False),
        ],
        ["实际IPv6前缀", "分配ID与宣告记录"],
    ),
    (
        "IP.ASN",
        "互联网资源",
        "ASN",
        [
            select("mode", "服务模式", [("apply", "申请代办"), ("manage", "托管管理"), ("change", "变更协助")]),
            field("applicant", "申请主体"),
            field("registry", "注册管理机构"),
            field("purpose", "用途与路由策略"),
        ],
        ["ASN号码", "申请 / 变更凭证"],
    ),
    (
        "CLOUD.IX",
        "上云互联",
        "IX Peering",
        [
            field("ix", "IX名称"),
            select("access", "接入模式", [("direct", "直连"), ("remote", "远程")]),
            PORT,
            BANDWIDTH,
            field("asn", "客户ASN"),
            field("peering", "Route Server / 双边对等策略"),
            field("vlan", "VLAN", required=False),
        ],
        ["端口与接入线路ID", "对等地址", "会话测试"],
    ),
    (
        "CLOUD.CONNECT",
        "上云互联",
        "Cloud Connect",
        [
            field("provider", "云厂商"),
            field("cloud_region", "目标云区域"),
            field("connection_type", "连接类型"),
            BANDWIDTH,
            field("a_location", "客户接入端"),
            PROTECTION,
            field("cloud_cost_owner", "云侧费用承担方"),
        ],
        ["云连接ID", "端口与VLAN", "连通测试"],
    ),
    (
        "NET.TRANSIT",
        "网络传输",
        "IP Transit",
        [*endpoint("a"), PORT, BANDWIDTH, field("routing", "BGP / 静态与ASN"), *BURST],
        ["线路与端口ID", "对等信息与客户前缀", "测试与采样对象"],
    ),
    (
        "NET.DIA.DC",
        "网络传输",
        "DIA / Datacenter",
        [DC, *endpoint("a"), BANDWIDTH, number("uplink", "上行速率", "Mbps"), IP_NEED],
        ["A端线路与端口", "IP与网关", "测试结果"],
    ),
    (
        "NET.DIA.RETAIL",
        "网络传输",
        "DIA / Retail Building",
        [
            field("address", "完整楼宇地址"),
            field("floor", "楼层 / 房间"),
            field("site_contact", "现场联系人"),
            BANDWIDTH,
            number("uplink", "上行速率", "Mbps"),
            IP_NEED,
            field("survey", "覆盖勘查需求"),
        ],
        ["覆盖勘查结果", "供应商线路ID与交接点", "IP与验收测试"],
    ),
    (
        "NET.CHINA",
        "网络传输",
        "China Route 回国带宽",
        [
            *endpoint("a"),
            BANDWIDTH,
            PORT,
            field("target_network", "回国目标地区 / 网络"),
            field("quality", "路由质量档位与测试目标"),
            *BURST,
        ],
        ["线路与端口ID", "交付路由范围", "性能测试"],
    ),
    (
        "NET.IEPL",
        "网络传输",
        "IEPL",
        [
            *endpoint("a"),
            field("z_region", "Z端地区"),
            *endpoint("z"),
            BANDWIDTH,
            PORT,
            field("interface", "接口 / VLAN / MTU"),
            PROTECTION,
            *BURST,
        ],
        ["端到端线路ID", "A/Z端口", "带宽与测试报告"],
    ),
    (
        "NET.WAVE",
        "网络传输",
        "Wave",
        [
            *endpoint("a"),
            field("z_region", "Z端地区"),
            *endpoint("z"),
            number("capacity", "波道容量", "Gbps"),
            field("interface", "光接口"),
            PROTECTION,
        ],
        ["波道 / 电路ID", "A/Z端口与光接口", "测试报告"],
    ),
    (
        "VAS.RH",
        "增值服务",
        "Remote Hands",
        [
            DC,
            field("target", "关联设备 / 服务"),
            field("task_type", "任务类型"),
            field("steps", "操作步骤"),
            field("window", "操作窗口"),
            number("estimated_hours", "预计工时", "小时"),
            field("budget", "预算上限与超额确认方式"),
        ],
        ["操作起止时间", "确认工时与材料", "完成证据"],
    ),
    (
        "ADDON.LOCAL_LOOP",
        "附加服务",
        "附加本地传输",
        [
            select("side", "端别", [("a", "A端"), ("z", "Z端"), ("other", "其他")]),
            field("a_location", "起点"),
            field("z_location", "终点"),
            BANDWIDTH,
            field("carrier", "供应商"),
        ],
        ["供应商线路ID", "两端交接点", "测试结果"],
    ),
]
CATALOG = {
    code: {
        "code": code,
        "category": group,
        "name": name,
        "version": SCHEMA_VERSION,
        "fields": [deepcopy(REGION), *deepcopy(fields)],
        "delivery_fields": delivery,
    }
    for code, group, name, fields, delivery in DEFINITIONS
}


def visible(item, values):
    return all(values.get(key) in allowed for key, allowed in item.get("when", {}).items())


def validate_parameters(code, values, *, complete=True, snapshot=None):
    schema = snapshot or CATALOG.get(code)
    if not schema:
        raise HTTPException(422, "不支持的IDC产品")
    allowed = {item["key"] for item in schema["fields"]}
    if set(values) - allowed:
        raise HTTPException(422, "包含不属于当前产品的参数")
    clean = {}
    for item in schema["fields"]:
        key = item["key"]
        value = values.get(key)
        if not visible(item, values):
            continue
        if value is None or value == "":
            if complete and item["required"]:
                raise HTTPException(422, f"请填写{item['label']}")
            continue
        if item["type"] == "number":
            try:
                numeric = Decimal(str(value))
                if isinstance(value, bool) or not numeric.is_finite() or numeric <= 0 or numeric > 1000000000:
                    raise ValueError
            except (ValueError, InvalidOperation):
                raise HTTPException(422, f"{item['label']}必须为有效正数")
            clean[key] = str(numeric)
        else:
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise HTTPException(422, f"{item['label']}无效或超过2000字")
            if item["type"] == "select" and value not in {option["value"] for option in item["options"]}:
                raise HTTPException(422, f"{item['label']}选项无效")
            clean[key] = value.strip()
    for side in ("a", "z"):
        if clean.get(f"{side}_access") in {"off_net", "survey"} and clean.get(f"{side}_local_loop") == "none":
            raise HTTPException(422, "Off-net需确定本地传输来源")
    bandwidth, port = clean.get("bandwidth"), clean.get("port_speed")
    if bandwidth and port and Decimal(bandwidth) > Decimal(port):
        raise HTTPException(422, "承诺带宽不能超过端口速率")
    if clean.get("burst") == "yes" and clean.get("burst_limit"):
        limit = Decimal(clean["burst_limit"])
        if (bandwidth and limit < Decimal(bandwidth)) or (port and limit > Decimal(port)):
            raise HTTPException(422, "突发上限必须介于承诺带宽和端口速率之间")
    prefix = clean.get("prefix", "")
    if code in {"IP.V4", "IP.V6"} and prefix:
        try:
            version = 4 if code == "IP.V4" else 6
            if prefix.startswith("/"):
                length = int(prefix[1:])
                if not 0 <= length <= (32 if version == 4 else 128):
                    raise ValueError
            elif ip_network(prefix, strict=True).version != version:
                raise ValueError
        except ValueError:
            raise HTTPException(422, "IP前缀格式或地址族不正确")
    return clean
