/**
 * JS Recipe Evaluator — 前端实时预览引擎（Number 精度）
 *
 * 与 engine/recipe.py 逻辑完全一致，但使用 Number 类型（非 Decimal）。
 * 用于前端即时结算预览，正式结算走 Python/Decimal 引擎，容差 0.01 元可接受。
 *
 * 主函数：evaluateRecipe(recipe, batchView, direction) → SettlementItem[]
 *
 * 使用方式（前端）：
 *   import { evaluateRecipe } from '../engine/recipe.js'
 *   const items = evaluateRecipe(recipe, batchView, '采购')
 */

// ── 精度工具 ────────────────────────────────────────────────

/** 四舍五入到 n 位小数 */
function round(value, dp) {
  const factor = Math.pow(10, dp);
  return Math.round(value * factor) / factor;
}

/** 干重 = 湿重 × (1 - H2O% / 100)，保留 4 位小数 */
function calcDryWeight(wetWeight, h2oPct) {
  return round(wetWeight * (1 - h2oPct / 100), 4);
}

/** 金属量 = 干重 × 有效品位 / 100，保留 3 位小数 */
function calcMetalQuantity(dryWeight, assayPct, gradeDeduction) {
  const effGrade = assayPct - gradeDeduction;
  return round(dryWeight * (effGrade / 100), 3);
}

/** 货款 = 金属量 × 单价，保留 2 位小数 */
function calcElementPayment(metalQuantity, unitPrice) {
  return round(metalQuantity * unitPrice, 2);
}

/** 扣款金额 = 湿重 × 费率，保留 2 位小数 */
function calcImpurityAmount(wetWeight, rate) {
  return round(wetWeight * rate, 2);
}

// ── 档位查找 ─────────────────────────────────────────────────

/**
 * 找到 grade 对应的扣款档位。
 * 区间规则：lower 含（闭），upper 不含（开）；upper=null 表示无上限。
 */
function findTier(grade, tiers) {
  const sorted = [...tiers].sort((a, b) => Number(a.lower) - Number(b.lower));
  for (const tier of sorted) {
    const lower = Number(tier.lower);
    if (grade < lower) continue;
    if (tier.upper === null || tier.upper === undefined) return tier;
    const upper = Number(tier.upper);
    if (grade < upper) return tier;
  }
  return null;
}

// ── 主函数 ───────────────────────────────────────────────────

/**
 * 用 Recipe 对 batchView 中的每个批次单元计算结算明细。
 *
 * @param {Object} recipe - Recipe 对象（与 engine/schema.py 的 Recipe 结构一致）
 * @param {Object} batchView - 批次视图 { contract, batchUnits }
 *   batchUnits: Array of { sampleId, totalWetWeight, assayReport }
 *   assayReport: { cuPct, h2oPct, asPct, ... }（驼峰命名）
 * @param {string} direction - "采购" | "销售"
 * @returns {SettlementItem[]}
 */
export function evaluateRecipe(recipe, batchView, direction) {
  const settleDirection = direction === '采购' ? '付' : '收';
  const items = [];

  const elementItems = recipe.elements.filter(e => e.type === 'element');
  const deductionItems = recipe.elements.filter(e => e.type === 'deduction');

  // ── 元素货款 ────────────────────────────────────────────
  for (const unit of batchView.batchUnits) {
    const assay = unit.assayReport;
    const wetWeight = Number(unit.totalWetWeight);
    const h2oPct = Number(assay.h2oPct);

    if (isNaN(h2oPct)) {
      throw new Error(`样号 ${unit.sampleId} 化验单缺少 h2o_pct`);
    }

    const dryWeight = calcDryWeight(wetWeight, h2oPct);

    for (const elem of elementItems) {
      if (elem.unitPrice.source !== 'fixed') {
        throw new Error(`仅支持 source=fixed，元素 ${elem.name} 使用了 ${elem.unitPrice.source}`);
      }
      if (elem.operations && elem.operations.length > 0) {
        throw new Error(`元素 ${elem.name} 含 operations，Phase 1 暂不支持`);
      }

      const unitPrice = Number(elem.unitPrice.value);
      const basis = elem.quantity.basis;

      if (basis === 'wet_weight') {
        const payment = round(wetWeight * unitPrice, 2);
        items.push({
          sampleId: unit.sampleId,
          rowType: '元素货款',
          direction: settleDirection,
          element: elem.name,
          pricingBasis: '湿重',
          wetWeight,
          h2oPct,
          unitPrice,
          unit: elem.unitPrice.unit,
          amount: payment,
        });

      } else if (basis === 'dry_weight') {
        const payment = round(dryWeight * unitPrice, 2);
        items.push({
          sampleId: unit.sampleId,
          rowType: '元素货款',
          direction: settleDirection,
          element: elem.name,
          pricingBasis: '干重',
          wetWeight,
          h2oPct,
          dryWeight,
          unitPrice,
          unit: elem.unitPrice.unit,
          amount: payment,
        });

      } else if (basis === 'metal_quantity') {
        const gradeField = elem.quantity.gradeField;
        if (!gradeField) {
          throw new Error(`元素 ${elem.name} basis=metal_quantity 必须指定 gradeField`);
        }
        const assayGrade = Number(assay[gradeField]);
        if (isNaN(assayGrade)) {
          throw new Error(`样号 ${unit.sampleId} 化验单缺少字段 ${gradeField}`);
        }
        const metalQty = calcMetalQuantity(dryWeight, assayGrade);
        const payment = calcElementPayment(metalQty, unitPrice);

        items.push({
          sampleId: unit.sampleId,
          rowType: '元素货款',
          direction: settleDirection,
          element: elem.name,
          pricingBasis: '金属量',
          wetWeight,
          h2oPct,
          dryWeight,
          assayGrade,
          metalQuantity: metalQty,
          unitPrice,
          unit: elem.unitPrice.unit,
          amount: payment,
        });
      }
    }
  }

  // ── 杂质扣款 ────────────────────────────────────────────
  for (const elem of deductionItems) {
    const gradeField = elem.quantity.gradeField;
    if (!gradeField) {
      throw new Error(`杂质 ${elem.name} 必须指定 gradeField`);
    }

    for (const unit of batchView.batchUnits) {
      const assay = unit.assayReport;
      const gradeRaw = assay[gradeField];
      if (gradeRaw === null || gradeRaw === undefined) continue;

      const grade = Number(gradeRaw);
      const tier = findTier(grade, elem.tiers || []);
      if (!tier) continue;

      const rate = Number(tier.rate);
      const wetWeight = Number(unit.totalWetWeight);
      const amount = calcImpurityAmount(wetWeight, rate);

      const tierNote = tier.upper === null || tier.upper === undefined
        ? `${elem.name} ≥${tier.lower}% → ${tier.rate}元/吨`
        : `${elem.name} [${tier.lower}%, ${tier.upper}%) → ${tier.rate}元/吨`;

      items.push({
        sampleId: unit.sampleId,
        rowType: '杂质扣款',
        direction: '付',   // 杂质扣款永远是支出
        element: elem.name,
        pricingBasis: '湿重',
        wetWeight,
        assayGrade: grade,
        unitPrice: rate,
        unit: '元/吨',
        amount,
        note: tierNote,
      });
    }
  }

  return items;
}

/**
 * 从 SettlementItem[] 计算汇总数据。
 *
 * @param {Object[]} items
 * @returns {{ totalElementPayment, totalImpurityDeduction, totalIncome, totalExpense, netAmount }}
 */
export function summarizeItems(items) {
  let totalElementPayment = 0;
  let totalImpurityDeduction = 0;
  let totalIncome = 0;
  let totalExpense = 0;

  for (const item of items) {
    if (item.rowType === '元素货款') {
      totalElementPayment = round(totalElementPayment + item.amount, 2);
    } else if (item.rowType === '杂质扣款') {
      totalImpurityDeduction = round(totalImpurityDeduction + item.amount, 2);
    }

    if (item.direction === '收') {
      totalIncome = round(totalIncome + item.amount, 2);
    } else {
      totalExpense = round(totalExpense + item.amount, 2);
    }
  }

  const netAmount = round(totalIncome - totalExpense, 2);

  return {
    totalElementPayment,
    totalImpurityDeduction,
    totalIncome,
    totalExpense,
    netAmount,
  };
}

// ── 字段名适配器 ─────────────────────────────────────────────
// API 返回 snake_case，JS 引擎用 camelCase
// 前端从 API 获取数据后需要先经过此函数转换

/**
 * 将 API 返回的 batchView（snake_case）转换为 JS 引擎使用的 camelCase 格式。
 *
 * API batchUnit: { sample_id, total_wet_weight, assay_report: { cu_pct, h2o_pct, ... } }
 * JS engine: { sampleId, totalWetWeight, assayReport: { cuPct, h2oPct, ... } }
 */
export function adaptBatchView(apiBatchView) {
  return {
    contract: apiBatchView.contract,
    batchUnits: apiBatchView.batch_units.map(unit => ({
      sampleId: unit.sample_id,
      totalWetWeight: unit.total_wet_weight,
      assayReport: adaptAssayReport(unit.assay_report),
    })),
  };
}

function adaptAssayReport(ar) {
  return {
    cuPct: ar.cu_pct,
    auGt: ar.au_gt,
    agGt: ar.ag_gt,
    pbPct: ar.pb_pct,
    znPct: ar.zn_pct,
    sPct: ar.s_pct,
    asPct: ar.as_pct,
    h2oPct: ar.h2o_pct,
  };
}

/**
 * 将 Recipe（snake_case，来自 API/YAML）转换为 JS 引擎使用的 camelCase 格式。
 */
export function adaptRecipe(apiRecipe) {
  return {
    contractId: apiRecipe.contract_id,
    version: apiRecipe.version || '1.0',
    elements: (apiRecipe.elements || []).map(elem => ({
      name: elem.name,
      type: elem.type,
      quantity: {
        basis: elem.quantity?.basis || 'metal_quantity',
        gradeField: _snakeToCamel(elem.quantity?.grade_field),
      },
      unitPrice: {
        source: elem.unit_price?.source || 'fixed',
        value: elem.unit_price?.value,
        unit: elem.unit_price?.unit || '元/金属吨',
      },
      operations: elem.operations || [],
      tiers: (elem.tiers || []).map(t => ({
        lower: t.lower,
        upper: t.upper,
        rate: t.rate,
      })),
    })),
    assayFee: apiRecipe.assay_fee,
  };
}

/** grade_field 从 snake_case 转 camelCase（cu_pct → cuPct）*/
function _snakeToCamel(s) {
  if (!s) return s;
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}
