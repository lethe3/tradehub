import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useContractStore } from '../stores/contractStore.js';
import StageBar from '../components/StageBar.jsx';
import StageSettlement from '../stages/StageSettlement.jsx';
import StageParsing from '../stages/StageParsing.jsx';
import StagePlaceholder from '../stages/StagePlaceholder.jsx';
import { T, inputStyle, btnPrimary, btnDanger, btnSecondary } from '../theme.js';
import { fmt } from '../theme.js';

function DirectionBadge({ direction }) {
  const isPurchase = direction === '采购' || direction === 'buy' || direction === 'purchase';
  return (
    <span style={{
      fontSize: 11,
      padding: '2px 8px',
      borderRadius: 10,
      background: isPurchase ? T.amberBg : T.greenBg,
      color: isPurchase ? T.amber : T.green,
      fontWeight: 500,
      border: `1px solid ${isPurchase ? '#5c3a08' : '#1a5c38'}`,
    }}>
      {direction}
    </span>
  );
}

function WeighTicketPanel({ contractId }) {
  const { weigh_tickets, addWeighTicket, deleteWeighTicket } = useContractStore();
  const [form, setForm] = useState({ ticket_number: '', commodity: '', wet_weight: '', sample_id: '', is_settlement: true });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr('');
    if (!form.ticket_number || !form.wet_weight) {
      setErr('磅单号和湿重为必填');
      return;
    }
    setSubmitting(true);
    try {
      await addWeighTicket(contractId, {
        ...form,
        wet_weight: form.wet_weight,
        is_settlement: form.is_settlement,
      });
      setForm({ ticket_number: '', commodity: '', wet_weight: '', sample_id: '', is_settlement: true });
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 6, marginBottom: 6, alignItems: 'end' }}>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>磅单号 *</span>
            <input value={form.ticket_number} onChange={(e) => set('ticket_number', e.target.value)} placeholder="W001" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>湿重 (吨) *</span>
            <input value={form.wet_weight} onChange={(e) => set('wet_weight', e.target.value)} placeholder="50.225" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>样品编号</span>
            <input value={form.sample_id} onChange={(e) => set('sample_id', e.target.value)} placeholder="S2501" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>货品</span>
            <input value={form.commodity} onChange={(e) => set('commodity', e.target.value)} placeholder="铜精矿" style={inputStyle} />
          </div>
          <button type="submit" disabled={submitting} style={{ ...btnPrimary, height: 30, whiteSpace: 'nowrap' }}>
            添加
          </button>
        </div>
        {err && <div style={{ fontSize: 11, color: T.red, marginBottom: 6 }}>{err}</div>}
      </form>

      {/* List */}
      {weigh_tickets.length > 0 && (
        <div style={{
          background: T.bg,
          border: `1px solid ${T.border}`,
          borderRadius: 6,
          overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: T.surface }}>
                {['磅单号', '货品', '湿重 (吨)', '样品编号', ''].map((h) => (
                  <th key={h} style={{ padding: '6px 10px', fontSize: 11, color: T.muted, textAlign: 'left', fontWeight: 500, borderBottom: `1px solid ${T.border}` }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weigh_tickets.map((t) => (
                <tr key={t.id} style={{ borderBottom: `1px solid ${T.hint}` }}>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono }}>{t.ticket_number}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, color: T.muted }}>{t.commodity || '—'}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono }}>{fmt(t.wet_weight, 3)}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono, color: T.accent }}>{t.sample_id || '—'}</td>
                  <td style={{ padding: '5px 10px', textAlign: 'right' }}>
                    <button onClick={() => deleteWeighTicket(contractId, t.id)} style={btnDanger}>删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AssayReportPanel({ contractId }) {
  const { assay_reports, addAssayReport, deleteAssayReport } = useContractStore();
  const [form, setForm] = useState({ sample_id: '', cu_pct: '', h2o_pct: '', as_pct: '' });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr('');
    if (!form.sample_id) {
      setErr('样品编号为必填');
      return;
    }
    setSubmitting(true);
    try {
      await addAssayReport(contractId, form);
      setForm({ sample_id: '', cu_pct: '', h2o_pct: '', as_pct: '' });
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 6, marginBottom: 6, alignItems: 'end' }}>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>样品编号 *</span>
            <input value={form.sample_id} onChange={(e) => set('sample_id', e.target.value)} placeholder="S2501" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>Cu (%)</span>
            <input value={form.cu_pct} onChange={(e) => set('cu_pct', e.target.value)} placeholder="18.50" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>H₂O (%)</span>
            <input value={form.h2o_pct} onChange={(e) => set('h2o_pct', e.target.value)} placeholder="10.00" style={inputStyle} />
          </div>
          <div>
            <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>As (%)</span>
            <input value={form.as_pct} onChange={(e) => set('as_pct', e.target.value)} placeholder="0.35" style={inputStyle} />
          </div>
          <button type="submit" disabled={submitting} style={{ ...btnPrimary, height: 30, whiteSpace: 'nowrap' }}>
            添加
          </button>
        </div>
        {err && <div style={{ fontSize: 11, color: T.red, marginBottom: 6 }}>{err}</div>}
      </form>

      {/* List */}
      {assay_reports.length > 0 && (
        <div style={{
          background: T.bg,
          border: `1px solid ${T.border}`,
          borderRadius: 6,
          overflow: 'hidden',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: T.surface }}>
                {['样品编号', 'Cu (%)', 'H₂O (%)', 'As (%)', ''].map((h) => (
                  <th key={h} style={{ padding: '6px 10px', fontSize: 11, color: T.muted, textAlign: 'left', fontWeight: 500, borderBottom: `1px solid ${T.border}` }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {assay_reports.map((r) => (
                <tr key={r.id} style={{ borderBottom: `1px solid ${T.hint}` }}>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono, color: T.accent }}>{r.sample_id}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono }}>{r.cu_pct ?? '—'}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono }}>{r.h2o_pct ?? '—'}</td>
                  <td style={{ padding: '5px 10px', fontSize: 12, fontFamily: T.mono }}>{r.as_pct ?? '—'}</td>
                  <td style={{ padding: '5px 10px', textAlign: 'right' }}>
                    <button onClick={() => deleteAssayReport(contractId, r.id)} style={btnDanger}>删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function DataEntryPanel({ contractId }) {
  const [open, setOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('weighTicket');

  return (
    <div style={{
      borderBottom: `1px solid ${T.border}`,
      background: T.surface,
    }}>
      {/* Toggle header */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: '100%',
          background: 'none',
          border: 'none',
          borderBottom: open ? `1px solid ${T.border}` : 'none',
          padding: '8px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          cursor: 'pointer',
          color: T.muted,
          fontSize: 12,
          fontFamily: T.sans,
          textAlign: 'left',
        }}
      >
        <span style={{
          fontSize: 10,
          transform: open ? 'rotate(90deg)' : 'rotate(0)',
          display: 'inline-block',
          transition: 'transform 0.15s',
        }}>▶</span>
        数据录入
        <span style={{ fontSize: 11, color: T.hint }}>（磅单 / 化验单）</span>
      </button>

      {open && (
        <div style={{ padding: '12px 20px 16px' }}>
          {/* Sub-tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 12 }}>
            {[
              { key: 'weighTicket', label: '磅单录入' },
              { key: 'assayReport', label: '化验单录入' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: '4px 12px',
                  borderRadius: 4,
                  border: `1px solid ${activeTab === tab.key ? T.accent : T.border}`,
                  background: activeTab === tab.key ? T.accentBg : 'transparent',
                  color: activeTab === tab.key ? T.accent : T.muted,
                  fontSize: 12,
                  cursor: 'pointer',
                  fontFamily: T.sans,
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'weighTicket' && <WeighTicketPanel contractId={contractId} />}
          {activeTab === 'assayReport' && <AssayReportPanel contractId={contractId} />}
        </div>
      )}
    </div>
  );
}

function deriveStage(recipe, weigh_tickets, assay_reports) {
  if (!recipe || !recipe.elements || recipe.elements.length === 0) return 1;
  if (weigh_tickets.length > 0 && assay_reports.length > 0) return 4;
  return 2;
}

export default function ContractDetail() {
  const { id } = useParams();
  const { currentContract, weigh_tickets, assay_reports, recipe, detailLoading, detailError, fetchContractDetail } = useContractStore();
  const [activeStage, setActiveStage] = useState(null); // null = auto-derive

  useEffect(() => {
    fetchContractDetail(id);
    setActiveStage(null); // reset stage when contract changes
  }, [id]);

  if (detailLoading) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: 12, color: T.muted,
      }}>
        <div style={{ fontSize: 24, opacity: 0.5 }}>⟳</div>
        <div style={{ fontSize: 13 }}>加载合同数据…</div>
      </div>
    );
  }

  if (detailError) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ color: T.red, fontSize: 13 }}>加载失败：{detailError}</div>
        <button onClick={() => fetchContractDetail(id)} style={{ ...btnSecondary }}>重试</button>
      </div>
    );
  }

  if (!currentContract) return null;

  const derivedStage = deriveStage(recipe, weigh_tickets, assay_reports);
  const displayStage = activeStage !== null ? activeStage : derivedStage;

  const renderStageContent = () => {
    switch (displayStage) {
      case 1: return <StageParsing contractId={id} />;
      case 4: return <StageSettlement contractId={id} />;
      default: return <StagePlaceholder stage={displayStage} />;
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Contract header */}
      <div style={{
        padding: '12px 20px',
        borderBottom: `1px solid ${T.border}`,
        background: T.surface,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}>
        <span style={{
          fontFamily: T.mono,
          fontWeight: 600,
          fontSize: 15,
          color: T.text,
          letterSpacing: '0.02em',
        }}>
          {currentContract.contract_number}
        </span>
        <DirectionBadge direction={currentContract.direction} />
        <span style={{ color: T.muted, fontSize: 13 }}>{currentContract.counterparty}</span>
        {currentContract.commodity && (
          <span style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 10,
            background: T.purpleBg,
            color: T.purple,
            border: `1px solid #3d2d66`,
          }}>
            {currentContract.commodity}
          </span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: T.hint }}>ID: {currentContract.id}</span>
      </div>

      {/* Stage bar */}
      <StageBar activeStage={displayStage} onSelect={setActiveStage} />

      {/* Data entry panel */}
      <DataEntryPanel contractId={id} />

      {/* Stage content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {renderStageContent()}
      </div>
    </div>
  );
}
