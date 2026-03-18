"""
合同 CRUD + 子资源路由

路由结构：
  GET/POST   /api/contracts
  GET/PUT    /api/contracts/{id}
  GET/POST   /api/contracts/{id}/weigh-tickets
  PUT/DELETE /api/contracts/{id}/weigh-tickets/{ticket_id}
  GET/POST   /api/contracts/{id}/assay-reports
  PUT/DELETE /api/contracts/{id}/assay-reports/{report_id}
  GET/PUT    /api/contracts/{id}/recipe
  GET        /api/contracts/{id}/settlement
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_store
from api.schemas import (
    AssayReportCreate,
    AssayReportUpdate,
    ContractCreate,
    ContractUpdate,
    SettlementItemOut,
    SettlementResponse,
    SettlementSummaryOut,
    WeighTicketCreate,
    WeighTicketUpdate,
)
from store.json_store import JsonFileStore

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


# ── 合同 CRUD ────────────────────────────────────────────────

@router.get("")
def list_contracts(store: JsonFileStore = Depends(get_store)):
    """列出所有合同。"""
    return store.list("contracts")


@router.post("", status_code=201)
def create_contract(body: ContractCreate, store: JsonFileStore = Depends(get_store)):
    """新建合同。"""
    data = body.model_dump(exclude_none=False)
    # 日期序列化为字符串
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
    return store.create("contracts", data)


@router.get("/{contract_id}")
def get_contract(contract_id: str, store: JsonFileStore = Depends(get_store)):
    """获取单个合同。"""
    record = store.get("contracts", contract_id)
    if record is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    return record


@router.put("/{contract_id}")
def update_contract(
    contract_id: str,
    body: ContractUpdate,
    store: JsonFileStore = Depends(get_store),
):
    """更新合同。"""
    _require_contract(store, contract_id)
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    for k, v in data.items():
        if hasattr(v, "isoformat"):
            data[k] = v.isoformat()
    updated = store.update("contracts", contract_id, data)
    return updated


# ── 磅单子资源 ───────────────────────────────────────────────

@router.get("/{contract_id}/weigh-tickets")
def list_weigh_tickets(contract_id: str, store: JsonFileStore = Depends(get_store)):
    """列出合同下的所有磅单。"""
    _require_contract(store, contract_id)
    return store.list("weigh_tickets", filters={"contract_id": contract_id})


@router.post("/{contract_id}/weigh-tickets", status_code=201)
def create_weigh_ticket(
    contract_id: str,
    body: WeighTicketCreate,
    store: JsonFileStore = Depends(get_store),
):
    """新建磅单。"""
    _require_contract(store, contract_id)
    data = _serialize(body.model_dump())
    data["contract_id"] = contract_id
    return store.create("weigh_tickets", data)


@router.put("/{contract_id}/weigh-tickets/{ticket_id}")
def update_weigh_ticket(
    contract_id: str,
    ticket_id: str,
    body: WeighTicketUpdate,
    store: JsonFileStore = Depends(get_store),
):
    """更新磅单。"""
    _require_ticket(store, contract_id, ticket_id)
    data = {k: v for k, v in _serialize(body.model_dump()).items() if v is not None}
    return store.update("weigh_tickets", ticket_id, data)


@router.delete("/{contract_id}/weigh-tickets/{ticket_id}", status_code=204)
def delete_weigh_ticket(
    contract_id: str,
    ticket_id: str,
    store: JsonFileStore = Depends(get_store),
):
    """删除磅单。"""
    _require_ticket(store, contract_id, ticket_id)
    store.delete("weigh_tickets", ticket_id)


# ── 化验单子资源 ─────────────────────────────────────────────

@router.get("/{contract_id}/assay-reports")
def list_assay_reports(contract_id: str, store: JsonFileStore = Depends(get_store)):
    """列出合同下的所有化验单。"""
    _require_contract(store, contract_id)
    return store.list("assay_reports", filters={"contract_id": contract_id})


@router.post("/{contract_id}/assay-reports", status_code=201)
def create_assay_report(
    contract_id: str,
    body: AssayReportCreate,
    store: JsonFileStore = Depends(get_store),
):
    """新建化验单。"""
    _require_contract(store, contract_id)
    data = _serialize(body.model_dump())
    data["contract_id"] = contract_id
    return store.create("assay_reports", data)


@router.put("/{contract_id}/assay-reports/{report_id}")
def update_assay_report(
    contract_id: str,
    report_id: str,
    body: AssayReportUpdate,
    store: JsonFileStore = Depends(get_store),
):
    """更新化验单。"""
    _require_report(store, contract_id, report_id)
    data = {k: v for k, v in _serialize(body.model_dump()).items() if v is not None}
    return store.update("assay_reports", report_id, data)


@router.delete("/{contract_id}/assay-reports/{report_id}", status_code=204)
def delete_assay_report(
    contract_id: str,
    report_id: str,
    store: JsonFileStore = Depends(get_store),
):
    """删除化验单。"""
    _require_report(store, contract_id, report_id)
    store.delete("assay_reports", report_id)


# ── Recipe ───────────────────────────────────────────────────

@router.get("/{contract_id}/recipe")
def get_recipe(contract_id: str, store: JsonFileStore = Depends(get_store)):
    """获取合同配方。"""
    _require_contract(store, contract_id)
    recipes = store.list("recipes", filters={"contract_id": contract_id})
    if not recipes:
        raise HTTPException(status_code=404, detail="配方不存在")
    return recipes[0]


@router.put("/{contract_id}/recipe")
def upsert_recipe(
    contract_id: str,
    body: dict,
    store: JsonFileStore = Depends(get_store),
):
    """保存/更新合同配方（upsert）。"""
    _require_contract(store, contract_id)
    body["contract_id"] = contract_id

    existing = store.list("recipes", filters={"contract_id": contract_id})
    if existing:
        return store.update("recipes", existing[0]["id"], body)
    else:
        return store.create("recipes", body)


# ── 结算计算 ─────────────────────────────────────────────────

@router.get("/{contract_id}/settlement")
def get_settlement(contract_id: str, store: JsonFileStore = Depends(get_store)):
    """计算并返回结算结果。

    前置条件：磅单、化验单、配方均已录入。
    """
    contract_record = _require_contract(store, contract_id)

    # 就绪检查
    weigh_tickets_raw = store.list("weigh_tickets", filters={"contract_id": contract_id})
    assay_reports_raw = store.list("assay_reports", filters={"contract_id": contract_id})
    recipes_raw = store.list("recipes", filters={"contract_id": contract_id})

    ready_check = {
        "weigh_tickets": len(weigh_tickets_raw) > 0,
        "assay_reports": len(assay_reports_raw) > 0,
        "recipe": len(recipes_raw) > 0,
    }

    if not all(ready_check.values()):
        missing = [k for k, v in ready_check.items() if not v]
        raise HTTPException(
            status_code=422,
            detail=f"结算前置条件未满足，缺少：{', '.join(missing)}",
        )

    # 构建 Pydantic 模型
    from core.models.batch import AssayReportRecord, ContractRecord, WeighTicketRecord
    from core.linking import build_batch_view
    from engine.recipe import evaluate_recipe
    from engine.schema import Recipe

    contract = ContractRecord(
        contract_id=contract_record["id"],
        contract_number=contract_record.get("contract_number", ""),
        direction=contract_record.get("direction", "采购"),
        counterparty=contract_record.get("counterparty", ""),
    )

    weigh_tickets = [WeighTicketRecord(**_deserialize_ticket(wt)) for wt in weigh_tickets_raw]
    assay_reports = [AssayReportRecord(**_deserialize_report(ar)) for ar in assay_reports_raw]
    recipe_raw = recipes_raw[0]
    recipe = Recipe(**recipe_raw)

    batch_view, _ = build_batch_view(contract, weigh_tickets, assay_reports)
    direction = contract_record.get("direction", "采购")
    items = evaluate_recipe(recipe, batch_view, direction)

    # 转换为输出格式
    items_out = [_item_to_out(i) for i in items]

    # 计算汇总
    from core.models.settlement_item import SettlementDirection, SettlementRowType
    total_element = sum(
        i.amount for i in items if i.row_type == SettlementRowType.ELEMENT_PAYMENT
    )
    total_deduction = sum(
        i.amount for i in items if i.row_type == SettlementRowType.IMPURITY_DEDUCTION
    )
    total_income = sum(
        i.amount for i in items if i.direction == SettlementDirection.INCOME
    )
    total_expense = sum(
        i.amount for i in items if i.direction == SettlementDirection.EXPENSE
    )
    net = total_income - total_expense

    summary = SettlementSummaryOut(
        total_element_payment=str(total_element),
        total_impurity_deduction=str(total_deduction),
        total_income=str(total_income),
        total_expense=str(total_expense),
        net_amount=str(net),
    )

    return SettlementResponse(
        contract_id=contract_id,
        direction=direction,
        items=items_out,
        summary=summary,
        ready_check=ready_check,
    )


# ── 私有工具函数 ─────────────────────────────────────────────

def _require_contract(store: JsonFileStore, contract_id: str) -> dict:
    record = store.get("contracts", contract_id)
    if record is None:
        raise HTTPException(status_code=404, detail="合同不存在")
    return record


def _require_ticket(store: JsonFileStore, contract_id: str, ticket_id: str) -> dict:
    record = store.get("weigh_tickets", ticket_id)
    if record is None or record.get("contract_id") != contract_id:
        raise HTTPException(status_code=404, detail="磅单不存在")
    return record


def _require_report(store: JsonFileStore, contract_id: str, report_id: str) -> dict:
    record = store.get("assay_reports", report_id)
    if record is None or record.get("contract_id") != contract_id:
        raise HTTPException(status_code=404, detail="化验单不存在")
    return record


def _serialize(data: dict) -> dict:
    """将 Pydantic 模型数据序列化为 JSON 友好格式（Decimal → str，date → str）。"""
    result = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            result[k] = str(v)
        elif hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def _deserialize_ticket(data: dict) -> dict:
    """将 JSON 存储的磅单数据转换为 WeighTicketRecord 所需格式。"""
    result = {**data}
    result["ticket_id"] = data.get("id", "")
    return result


def _deserialize_report(data: dict) -> dict:
    """将 JSON 存储的化验单数据转换为 AssayReportRecord 所需格式。"""
    result = {**data}
    result["report_id"] = data.get("id", "")
    return result


def _item_to_out(item: Any) -> SettlementItemOut:
    """将 SettlementItemRecord 转换为 API 响应格式。"""
    def _d(v):
        return str(v) if v is not None else None

    return SettlementItemOut(
        sample_id=item.sample_id,
        row_type=item.row_type.value,
        direction=item.direction.value,
        element=item.element,
        pricing_basis=item.pricing_basis.value if item.pricing_basis else None,
        wet_weight=_d(item.wet_weight),
        h2o_pct=_d(item.h2o_pct),
        dry_weight=_d(item.dry_weight),
        assay_grade=_d(item.assay_grade),
        grade_deduction_val=_d(item.grade_deduction_val),
        effective_grade=_d(item.effective_grade),
        metal_quantity=_d(item.metal_quantity),
        unit_price=_d(item.unit_price),
        unit=item.unit,
        amount=str(item.amount),
        note=item.note,
    )
