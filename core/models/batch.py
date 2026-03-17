"""
批次数据模型

从 Bitable 读取的原始记录（ContractRecord / WeighTicketRecord / AssayReportRecord）
和 M3C 串联后的视图模型（BatchUnit / BatchView）。

纯 Pydantic，无外部依赖。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class ContractRecord(BaseModel):
    """合同表原始记录"""
    contract_id: str                     # Bitable record ID
    contract_number: str                 # 合同编号（原件编号）
    direction: str                       # 采购 / 销售
    commodity: str                       # 货品名称
    counterparty: str                    # 交易对手
    signing_date: Optional[date] = None  # 签订日期
    # 阶段二扩展字段
    tax_included: Optional[bool] = None      # 是否含税
    freight_bearer: Optional[str] = None    # 运费承担方（我方/对方）
    assay_fee_bearer: Optional[str] = None  # 化验费承担方
    pricing_elements: list[str] = []        # 计价元素列表，如 ["Cu", "Au"]
    settlement_ticket_rule: Optional[str] = None   # 结算磅单约定
    settlement_assay_rule: Optional[str] = None    # 结算化验单约定


class WeighTicketRecord(BaseModel):
    """磅单表原始记录（阶段二扩展后的完整字段）"""
    ticket_id: str                           # Bitable record ID
    ticket_number: str                       # 磅单编号
    contract_id: str                         # 关联合同 record ID
    commodity: str                           # 货物品名
    wet_weight: Decimal                      # 净重(吨) = 磅单净重，即湿重
    weighing_date: Optional[date] = None     # 过磅日期
    # 阶段二扩展字段
    sample_id: Optional[str] = None          # 样号（与化验单关联的核心字段）
    vehicle_number: Optional[str] = None     # 车号
    gross_weight: Optional[Decimal] = None   # 毛重(吨)
    tare_weight: Optional[Decimal] = None    # 皮重(吨)
    deduction_weight: Optional[Decimal] = None  # 扣重(吨)
    is_settlement: bool = True               # 是否结算磅单
    price_group: Optional[int] = None        # 基准价组号（均价模式使用）

    @field_validator("wet_weight", mode="before")
    @classmethod
    def parse_weight(cls, v: object) -> Decimal:
        return Decimal(str(v))


class AssayReportRecord(BaseModel):
    """化验单表原始记录"""
    report_id: str                           # Bitable record ID
    contract_id: str                         # 关联合同 record ID
    sample_id: str                           # 样号（核心串联字段）
    assay_type: str = "结算化验"             # 快速摸底 / 结算化验
    is_settlement: bool = True               # 是否结算化验单
    assay_date: Optional[date] = None        # 化验日期
    assay_lab: Optional[str] = None          # 化验机构
    # 各元素品位（None = 未检测）
    cu_pct: Optional[Decimal] = None         # Cu%
    au_gt: Optional[Decimal] = None          # Au(g/t)
    ag_gt: Optional[Decimal] = None          # Ag(g/t)
    pb_pct: Optional[Decimal] = None         # Pb%
    zn_pct: Optional[Decimal] = None         # Zn%
    s_pct: Optional[Decimal] = None          # S%
    as_pct: Optional[Decimal] = None         # As%
    h2o_pct: Optional[Decimal] = None        # H2O%（水分，计算干重必需）

    @field_validator("cu_pct", "au_gt", "ag_gt", "pb_pct", "zn_pct",
                     "s_pct", "as_pct", "h2o_pct", mode="before")
    @classmethod
    def parse_grade(cls, v: object) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v))


class BatchUnit(BaseModel):
    """单个样号的批次单元（M3C 串联输出）

    一张化验单 + 该样号对应的全部磅单。
    湿重合计 = 所有磅单 wet_weight 之和。
    """
    sample_id: str
    weigh_tickets: list[WeighTicketRecord]
    assay_report: AssayReportRecord

    @property
    def total_wet_weight(self) -> Decimal:
        return sum((t.wet_weight for t in self.weigh_tickets), Decimal("0"))


class BatchView(BaseModel):
    """某合同的完整批次视图（M3C 串联输出，M3D 计算输入）"""
    contract: ContractRecord
    batch_units: list[BatchUnit]

    @property
    def total_wet_weight(self) -> Decimal:
        return sum((u.total_wet_weight for u in self.batch_units), Decimal("0"))

    @property
    def batch_count(self) -> int:
        return len(self.batch_units)
