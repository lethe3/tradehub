import React, { useEffect, useCallback } from 'react';
import { useSettlementStore } from '../stores/settlementStore.js';
import { T, fmt } from '../theme.js';

function ReadyBadge({ label, ok }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      padding: '3px 10px',
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 500,
      background: ok ? T.greenBg : T.redBg,
      color: ok ? T.green : T.red,
      border: `1px solid ${ok ? '#1a5c38' : '#5c1a1a'}`,
    }}>
      <span>{ok ? '✓' : '✗'}</span>
      {label}
    </span>
  );
}

function DataRow({ label, value, mono = true, highlight = false, indent = false }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'baseline',
      justifyContent: 'space-between',
      padding: '4px 0',
      paddingLeft: indent ? 12 : 0,
      borderBottom: `1px solid ${T.hint}`,
    }}>
      <span style={{ color: T.muted, fontSize: 12 }}>{label}</span>
      <span style={{
        fontFamily: mono ? T.mono : T.sans,
        fontSize: 12,
        fontWeight: highlight ? 600 : 400,
        color: highlight ? T.text : T.text,
      }}>
        {value}
      </span>
    </div>
  );
}

function ElementCard({ item }) {
  return (
    <div style={{
      background: T.bg,
      border: `1px solid ${T.border}`,
      borderRadius: 6,
      padding: '10px 14px',
      marginBottom: 8,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <span style={{
          fontWeight: 600,
          color: T.text,
          fontSize: 13,
          fontFamily: T.mono,
        }}>
          {item.element}
        </span>
        <span style={{
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 10,
          background: item.direction === '付' ? T.amberBg : T.greenBg,
          color: item.direction === '付' ? T.amber : T.green,
          fontWeight: 500,
        }}>
          {item.direction} · {item.row_type}
        </span>
      </div>

      {/* Dry weight calculation */}
      <DataRow
        label="湿重"
        value={`${fmt(item.wet_weight, 3)} 吨`}
        indent
      />
      {item.h2o_pct && (
        <DataRow
          label={`水分 ${fmt(item.h2o_pct, 2)}%`}
          value={`干重 = ${fmt(item.dry_weight, 3)} 吨`}
          indent
        />
      )}
      {item.metal_quantity && (
        <DataRow
          label={`化验品位 ${fmt(item.assay_grade, 2)}% − 扣除 ${fmt(item.grade_deduction_val, 2)}% = ${fmt(item.effective_grade, 2)}%`}
          value={`金属量 = ${fmt(item.metal_quantity, 3)} 吨`}
          indent
        />
      )}
      <DataRow
        label={`单价 ${item.unit_price ? fmt(item.unit_price, 0) + ' ' + item.unit : '—'}`}
        value={
          <span style={{ color: item.direction === '付' ? T.amber : T.green, fontWeight: 600, fontFamily: T.mono }}>
            {fmt(item.amount)} 元
          </span>
        }
        highlight
      />
      {item.note && (
        <div style={{ marginTop: 4, fontSize: 11, color: T.muted, fontStyle: 'italic' }}>
          {item.note}
        </div>
      )}
    </div>
  );
}

function DeductionCard({ item }) {
  return (
    <div style={{
      background: T.redBg,
      border: `1px solid #5c1a1a`,
      borderRadius: 6,
      padding: '10px 14px',
      marginBottom: 8,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 8,
      }}>
        <span style={{ fontWeight: 600, color: T.red, fontSize: 13, fontFamily: T.mono }}>
          {item.element}
        </span>
        <span style={{
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 10,
          background: '#5c1a1a',
          color: T.red,
          fontWeight: 500,
        }}>
          {item.direction} · {item.row_type}
        </span>
      </div>

      <DataRow
        label="湿重"
        value={`${fmt(item.wet_weight, 3)} 吨`}
        indent
      />
      {item.assay_grade && (
        <DataRow
          label={`化验品位 ${fmt(item.assay_grade, 2)}%`}
          value={`扣款计算`}
          indent
        />
      )}
      <DataRow
        label="扣款金额"
        value={
          <span style={{ color: T.red, fontWeight: 600, fontFamily: T.mono }}>
            −{fmt(item.amount)} 元
          </span>
        }
        highlight
      />
      {item.note && (
        <div style={{ marginTop: 4, fontSize: 11, color: '#c07070', fontStyle: 'italic' }}>
          {item.note}
        </div>
      )}
    </div>
  );
}

function SampleGroup({ sampleId, items }) {
  const totalWetWeight = items.reduce((sum, it) => {
    const w = parseFloat(it.wet_weight);
    return sum + (isNaN(w) ? 0 : w);
  }, 0);

  return (
    <div style={{
      background: T.card,
      border: `1px solid ${T.border}`,
      borderRadius: 8,
      marginBottom: 12,
      overflow: 'hidden',
    }}>
      {/* Sample header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 14px',
        background: T.surface,
        borderBottom: `1px solid ${T.border}`,
      }}>
        <span style={{
          fontFamily: T.mono,
          fontWeight: 600,
          color: T.accent,
          fontSize: 13,
        }}>
          样品 {sampleId}
        </span>
        <span style={{ fontFamily: T.mono, fontSize: 12, color: T.muted }}>
          湿重 {fmt(totalWetWeight, 3)} 吨
        </span>
      </div>

      {/* Item cards */}
      <div style={{ padding: '12px 14px 4px' }}>
        {items.map((item, i) => (
          item.row_type === '杂质扣款'
            ? <DeductionCard key={i} item={item} />
            : <ElementCard key={i} item={item} />
        ))}
      </div>
    </div>
  );
}

function SummaryPanel({ summary }) {
  if (!summary) return null;

  const net = parseFloat(summary.net_amount);
  const netIsPositive = net > 0;
  const netColor = netIsPositive ? T.green : T.red;
  const netLabel = netIsPositive ? '应收' : '应付';

  const rows = [
    { label: '元素货款合计', value: summary.total_element_payment, color: T.amber },
    { label: '杂质扣款合计', value: summary.total_impurity_deduction, color: T.red },
    { label: '总收入', value: summary.total_income, color: T.green },
    { label: '总支出', value: summary.total_expense, color: T.amber },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Summary card */}
      <div style={{
        background: T.card,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '10px 14px',
          background: T.surface,
          borderBottom: `1px solid ${T.border}`,
          fontWeight: 600,
          fontSize: 13,
          color: T.text,
        }}>
          结算汇总
        </div>
        <div style={{ padding: '12px 14px' }}>
          {rows.map((row) => (
            <div key={row.label} style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              padding: '5px 0',
              borderBottom: `1px solid ${T.hint}`,
            }}>
              <span style={{ fontSize: 12, color: T.muted }}>{row.label}</span>
              <span style={{
                fontFamily: T.mono,
                fontSize: 12,
                color: row.color,
              }}>
                {fmt(row.value)} 元
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Net amount card */}
      <div style={{
        background: netIsPositive ? T.greenBg : T.redBg,
        border: `1px solid ${netIsPositive ? '#1a5c38' : '#5c1a1a'}`,
        borderRadius: 8,
        padding: '16px 14px',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 11, color: T.muted, marginBottom: 4, letterSpacing: '0.05em' }}>
          净额（{netLabel}）
        </div>
        <div style={{
          fontFamily: T.mono,
          fontSize: 22,
          fontWeight: 700,
          color: netColor,
          letterSpacing: '-0.02em',
        }}>
          {fmt(Math.abs(net))}
        </div>
        <div style={{ fontSize: 11, color: netColor, marginTop: 2, opacity: 0.7 }}>元</div>
      </div>
    </div>
  );
}

export default function StageSettlement({ contractId }) {
  const { items, summary, loading, error, readyCheck, fetchSettlement } = useSettlementStore();

  const load = useCallback(() => {
    fetchSettlement(contractId);
  }, [contractId, fetchSettlement]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 12, color: T.muted,
      }}>
        <div style={{ fontSize: 24, opacity: 0.5 }}>⟳</div>
        <div style={{ fontSize: 13 }}>计算结算数据…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 12, padding: 40,
      }}>
        <div style={{ color: T.red, fontSize: 13 }}>结算计算失败：{error}</div>
        <button onClick={load} style={{
          background: T.card, border: `1px solid ${T.border}`,
          color: T.text, borderRadius: 4, padding: '6px 14px',
          fontSize: 12, cursor: 'pointer', fontFamily: T.sans,
        }}>
          重试
        </button>
      </div>
    );
  }

  // Group items by sample_id
  const grouped = {};
  for (const item of items) {
    const sid = item.sample_id ?? '—';
    if (!grouped[sid]) grouped[sid] = [];
    grouped[sid].push(item);
  }
  const sampleIds = Object.keys(grouped);

  // Ready check
  const rc = readyCheck || {};
  const hasWeighTickets = rc.weigh_tickets !== false;
  const hasAssayReports = rc.assay_reports !== false;
  const hasRecipe = rc.recipe !== false;
  const isReady = hasWeighTickets && hasAssayReports && hasRecipe;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top bar */}
      <div style={{
        padding: '10px 20px',
        borderBottom: `1px solid ${T.border}`,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: T.surface,
        flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 12, color: T.muted, marginRight: 4 }}>就绪检查</span>
        <ReadyBadge label="磅单" ok={hasWeighTickets} />
        <ReadyBadge label="化验单" ok={hasAssayReports} />
        <ReadyBadge label="配方" ok={hasRecipe} />
        <div style={{ flex: 1 }} />
        <button
          onClick={load}
          style={{
            background: T.accentBg,
            border: `1px solid ${T.accent}`,
            color: T.accent,
            borderRadius: 4,
            padding: '5px 14px',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: T.sans,
          }}
        >
          重新计算
        </button>
      </div>

      {/* Not ready warning */}
      {!isReady && (
        <div style={{
          margin: '16px 20px 0',
          padding: '12px 16px',
          background: T.amberBg,
          border: `1px solid #5c3a08`,
          borderRadius: 6,
          color: T.amber,
          fontSize: 12,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>数据不完整，无法计算结算</div>
          <ul style={{ paddingLeft: 16, margin: 0 }}>
            {!hasWeighTickets && <li>缺少磅单数据</li>}
            {!hasAssayReports && <li>缺少化验单数据</li>}
            {!hasRecipe && <li>缺少计价配方</li>}
          </ul>
        </div>
      )}

      {/* Main content */}
      {isReady && sampleIds.length > 0 ? (
        <div style={{
          flex: 1,
          display: 'flex',
          gap: 0,
          overflow: 'hidden',
        }}>
          {/* Left: detail cards (2/3) */}
          <div style={{
            flex: 2,
            overflow: 'auto',
            padding: '16px 20px',
            borderRight: `1px solid ${T.border}`,
          }}>
            {sampleIds.map((sid) => (
              <SampleGroup key={sid} sampleId={sid} items={grouped[sid]} />
            ))}
          </div>

          {/* Right: summary panel (1/3) */}
          <div style={{
            flex: 1,
            overflow: 'auto',
            padding: '16px',
            minWidth: 220,
          }}>
            <SummaryPanel summary={summary} />
          </div>
        </div>
      ) : isReady && sampleIds.length === 0 ? (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: T.muted, fontSize: 13,
        }}>
          暂无结算数据
        </div>
      ) : null}
    </div>
  );
}
