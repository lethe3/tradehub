import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useContractStore } from '../stores/contractStore.js';
import Modal from '../components/Modal.jsx';
import { T, inputStyle, btnPrimary, btnSecondary } from '../theme.js';

const DIRECTION_OPTIONS = [
  { value: '采购', label: '采购' },
  { value: '销售', label: '销售' },
];

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
    }}>
      {direction}
    </span>
  );
}

function StageBadge({ stage }) {
  const stageNames = { 0: '测算', 1: '解析', 2: '跟单', 3: '定价', 4: '结算', 5: '资金' };
  const stageColors = {
    0: { bg: T.purpleBg, color: T.purple },
    1: { bg: T.accentBg, color: T.accent },
    2: { bg: T.card, color: T.muted },
    3: { bg: T.amberBg, color: T.amber },
    4: { bg: T.greenBg, color: T.green },
    5: { bg: T.card, color: T.muted },
  };
  const { bg, color } = stageColors[stage] || stageColors[2];
  return (
    <span style={{
      fontSize: 11,
      padding: '2px 8px',
      borderRadius: 10,
      background: bg,
      color,
      fontWeight: 500,
    }}>
      {stage} · {stageNames[stage] || '—'}
    </span>
  );
}

function NewContractModal({ onClose, onCreate }) {
  const [form, setForm] = useState({
    contract_number: '',
    direction: '采购',
    counterparty: '',
    commodity: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErr('');
    if (!form.contract_number || !form.counterparty) {
      setErr('合同号和对手方为必填');
      return;
    }
    setSubmitting(true);
    try {
      await onCreate(form);
      onClose();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="新建合同" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: T.muted, display: 'block', marginBottom: 4 }}>合同号 *</label>
            <input
              value={form.contract_number}
              onChange={(e) => set('contract_number', e.target.value)}
              placeholder="TH-2501-001"
              style={inputStyle}
              autoFocus
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: T.muted, display: 'block', marginBottom: 4 }}>方向 *</label>
            <select
              value={form.direction}
              onChange={(e) => set('direction', e.target.value)}
              style={{
                ...inputStyle,
                appearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%238b8d96' d='M0 0l5 6 5-6z'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 10px center',
                paddingRight: 28,
              }}
            >
              {DIRECTION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: 12, color: T.muted, display: 'block', marginBottom: 4 }}>对手方 *</label>
            <input
              value={form.counterparty}
              onChange={(e) => set('counterparty', e.target.value)}
              placeholder="铜陵有色…"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: T.muted, display: 'block', marginBottom: 4 }}>货品</label>
            <input
              value={form.commodity}
              onChange={(e) => set('commodity', e.target.value)}
              placeholder="铜精矿"
              style={inputStyle}
            />
          </div>

          {err && (
            <div style={{ fontSize: 12, color: T.red, padding: '6px 10px', background: T.redBg, borderRadius: 4 }}>
              {err}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 4 }}>
            <button type="button" onClick={onClose} style={btnSecondary}>取消</button>
            <button type="submit" disabled={submitting} style={{ ...btnPrimary, opacity: submitting ? 0.7 : 1 }}>
              {submitting ? '创建中…' : '创建合同'}
            </button>
          </div>
        </div>
      </form>
    </Modal>
  );
}

export default function ContractList() {
  const navigate = useNavigate();
  const { contracts, loading, error, fetchContracts, createContract } = useContractStore();
  const [showModal, setShowModal] = useState(false);
  const [hoveredId, setHoveredId] = useState(null);

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleCreate = async (data) => {
    const contract = await createContract(data);
    navigate(`/contracts/${contract.id}`);
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Page header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: `1px solid ${T.border}`,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        background: T.surface,
      }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: T.text }}>合同管理</span>
        <span style={{ fontSize: 12, color: T.dim }}>{contracts.length} 个合同</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => setShowModal(true)} style={btnPrimary}>
          + 新建合同
        </button>
      </div>

      {/* Table area */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, flexDirection: 'column', gap: 12, color: T.muted }}>
            <div style={{ fontSize: 24, opacity: 0.5 }}>⟳</div>
            <div style={{ fontSize: 13 }}>加载中…</div>
          </div>
        ) : error ? (
          <div style={{ padding: 20, color: T.red, fontSize: 13 }}>加载失败：{error}</div>
        ) : contracts.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: 300, gap: 12,
          }}>
            <div style={{ fontSize: 40, opacity: 0.2 }}>☰</div>
            <div style={{ fontSize: 14, color: T.dim }}>暂无合同</div>
            <div style={{ fontSize: 12, color: T.hint }}>点击右上角「新建合同」创建第一个合同</div>
            <button onClick={() => setShowModal(true)} style={{ ...btnPrimary, marginTop: 4 }}>
              新建合同
            </button>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
              <tr style={{ background: T.surface }}>
                {['合同号', '方向', '对手方', '货品', '阶段', ''].map((h, i) => (
                  <th
                    key={i}
                    style={{
                      padding: '8px 16px',
                      fontSize: 11,
                      color: T.muted,
                      textAlign: 'left',
                      fontWeight: 500,
                      borderBottom: `1px solid ${T.border}`,
                      letterSpacing: '0.04em',
                      textTransform: 'uppercase',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => {
                const isHovered = hoveredId === c.id;
                return (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/contracts/${c.id}`)}
                    onMouseEnter={() => setHoveredId(c.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    style={{
                      cursor: 'pointer',
                      background: isHovered ? T.cardHover : 'transparent',
                      borderBottom: `1px solid ${T.hint}`,
                      transition: 'background 0.1s',
                    }}
                  >
                    <td style={{ padding: '10px 16px', fontFamily: T.mono, fontWeight: 500, fontSize: 13, color: T.text }}>
                      {c.contract_number}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <DirectionBadge direction={c.direction} />
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 13, color: T.muted }}>
                      {c.counterparty || '—'}
                    </td>
                    <td style={{ padding: '10px 16px', fontSize: 12, color: T.dim }}>
                      {c.commodity || '—'}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <StageBadge stage={c.current_stage ?? 1} />
                    </td>
                    <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                      <span style={{ color: T.accent, fontSize: 12 }}>→</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <NewContractModal onClose={() => setShowModal(false)} onCreate={handleCreate} />
      )}
    </div>
  );
}
