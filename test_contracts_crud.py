"""
测试合同表 CRUD 操作
"""
from feishu.contracts import ContractsCRUD, list_contracts, create_contract


def test_list():
    """测试列表查询"""
    print("\n=== 测试：列出所有合同 ===")
    contracts = list_contracts()
    print(f"共 {len(contracts)} 条记录")
    for c in contracts[:3]:  # 只显示前3条
        print(f"  - {c}")
    return contracts


def test_create():
    """测试创建"""
    print("\n=== 测试：创建合同 ===")
    crud = ContractsCRUD()

    # 测试数据
    data = {
        "合同编号": "HT-TEST-001",
        "我方主体": "公司A",
        "合同方向": "采购",
        "交易对手": "测试供应商",
        "签订日期": "2026-03-14",
    }

    record_id = crud.create(data)
    if record_id:
        print(f"✓ 创建成功！record_id: {record_id}")
        return record_id
    return None


def test_get(record_id: str):
    """测试获取单条"""
    print("\n=== 测试：获取合同 ===")
    crud = ContractsCRUD()
    contract = crud.get(record_id)
    if contract:
        print(f"✓ 获取成功: {contract}")
    return contract


def test_update(record_id: str):
    """测试更新"""
    print("\n=== 测试：更新合同 ===")
    crud = ContractsCRUD()
    success = crud.update(record_id, {"交易对手": "测试供应商-已更新"})
    if success:
        print(f"✓ 更新成功")
        # 验证更新
        contract = crud.get(record_id)
        print(f"  更新后: {contract}")
    return success


def test_delete(record_id: str):
    """测试删除"""
    print("\n=== 测试：删除合同 ===")
    crud = ContractsCRUD()
    success = crud.delete(record_id)
    if success:
        print(f"✓ 删除成功")
    return success


def main():
    print("=" * 50)
    print("合同表 CRUD 测试")
    print("=" * 50)

    # 1. 列出现有合同
    test_list()

    # 2. 创建新合同
    record_id = test_create()
    if not record_id:
        print("创建失败，跳过后续测试")
        return

    # 3. 获取刚创建的合同
    test_get(record_id)

    # 4. 更新合同
    test_update(record_id)

    # 5. 删除合同
    test_delete(record_id)

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    main()
