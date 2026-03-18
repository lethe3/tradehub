import React, { useState, useEffect } from 'react';
import { useContractStore } from '../stores/contractStore.js';
import { T, inputStyle, btnPrimary, btnSecondary, btnDanger } from '../theme.js';

const BASIS_OPTIONS = [
  { value: 'metal_quantity', label: '金属量' },
  { value: 'dry_weight', label: '干重' },
  { value: 'wet_weight', label: '湿重' },
];

const UNIT_OPTIONS = [
  { value: '元/金属吨', label: '元/金属吨' },
  { value: '元/吨', label: '元/吨' },
  { value: '元/干吨', label: '元/干吨' },
];

function makeElement(name = '') {
  return {
    name,
    type: 'element',
    quantity: { basis: 'metal_quantity', grade_field: '' },
    unit_price: { source: 'fixed', value: '', unit: '元/金属吨' },
    operations: [],
    tiers: [],
  };
}

function makeDeduction(name = '') {
  return {
    name,
    type: 'deduction',
    quantity: { basis: 'wet_weight', grade_field: '' },
    unit_price: { source: 'fixed', value: null, unit: '元/吨' },
    operations: [],
    tiers: [],
  };
}

function makeTier() {
  return { lower: '', upper: '', rate: '' };
}

function makeEmptyRecipe() {
  return {
    version: '1.0',
    elements: [],
    assay_fee: null,
  };
}

function SelectField({ value, onChange, options, style = {} }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        ...inputStyle,
        ...style,
        appearance: 'none',
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath fill='%238b8d96' d='M0 0l5 6 5-6z'/%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 10px center',
        paddingRight: 28,
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

function FieldLabel({ children }) {
  return (
    <span style={{ fontSize: 11, color: T.muted, display: 'block', marginBottom: 3 }}>
      {children}
    </span>
  );
}

function TierEditor({ tiers, onChange }) {
  const addTier = () => onChange([...tiers, makeTier()]);
  const removeTier = (i) => onChange(tiers.filter((_, idx) => idx !== i));
  const updateTier = (i, field, val) => {
    const next = tiers.map((t, idx) => idx === i ? { ...t, [field]: val } : t);
    onChange(next);
  };

  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 11, color: T.muted, marginBottom: 6 }}>阶梯扣款档位</div>
      {tiers.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          {/* Header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr auto',
            gap: 6,
            marginBottom: 4,
          }}>
            {['下限 (%)', '上限 (%)', '费率 (元/吨)', ''].map((h, i) => (
              <span key={i} style={{ fontSize: 10, color: T.dim }}>{h}</span>
            ))}
          </div>
          {tiers.map((tier, i) => (
            <div key={i} style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr auto',
              gap: 6,
              marginBottom: 4,
              alignItems: 'center',
            }}>
              <input
                value={tier.lower}
                onChange={(e) => updateTier(i, 'lower', e.target.value)}
                placeholder="0.30"
                style={inputStyle}
              />
              <input
                value={tier.upper}
                onChange={(e) => updateTier(i, 'upper', e.target.value)}
                placeholder="∞"
                style={inputStyle}
              />
              <input
                value={tier.rate}
                onChange={(e) => updateTier(i, 'rate', e.target.value)}
                placeholder="20"
                style={inputStyle}
              />
              <button onClick={() => removeTier(i)} style={btnDanger}>×</button>
            </div>
          ))}
        </div>
      )}
      <button onClick={addTier} style={{ ...btnSecondary, fontSize: 11, padding: '4px 10px' }}>
        + 添加档位
      </button>
    </div>
  );
}

function ElementCard({ el, index, onChange, onRemove }) {
  const update = (path, val) => {
    const next = JSON.parse(JSON.stringify(el));
    const parts = path.split('.');
    let cur = next;
    for (let i = 0; i < parts.length - 1; i++) cur = cur[parts[i]];
    cur[parts[parts.length - 1]] = val;
    onChange(index, next);
  };

  const isDeduction = el.type === 'deduction';

  return (
    <div style={{
      background: isDeduction ? T.redBg : T.card,
      border: `1px solid ${isDeduction ? '#5c1a1a' : T.border}`,
      borderRadius: 8,
      padding: '14px',
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{
          fontSize: 12,
          fontWeight: 600,
          color: isDeduction ? T.red : T.accent,
          background: isDeduction ? '#5c1a1a' : T.accentBg,
          padding: '2px 8px',
          borderRadius: 10,
        }}>
          {isDeduction ? '杂质扣款' : '计价元素'}
        </span>
        <button onClick={() => onRemove(index)} style={btnDanger}>移除</button>
      </div>

      {/* Name */}
      <div style={{ marginBottom: 10 }}>
        <FieldLabel>元素名称</FieldLabel>
        <input
          value={el.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder="Cu / As / Pb …"
          style={inputStyle}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <FieldLabel>计价基准</FieldLabel>
          <SelectField
            value={el.quantity.basis}
            onChange={(v) => update('quantity.basis', v)}
            options={BASIS_OPTIONS}
          />
        </div>
        <div>
          <FieldLabel>化验字段</FieldLabel>
          <input
            value={el.quantity.grade_field}
            onChange={(e) => update('quantity.grade_field', e.target.value)}
            placeholder="cu_pct / as_pct …"
            style={inputStyle}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
        <div>
          <FieldLabel>单价</FieldLabel>
          <input
            value={el.unit_price.value ?? ''}
            onChange={(e) => update('unit_price.value', e.target.value)}
            placeholder="65000"
            style={inputStyle}
            disabled={isDeduction && el.tiers.length > 0}
          />
        </div>
        <div>
          <FieldLabel>单价单位</FieldLabel>
          <SelectField
            value={el.unit_price.unit}
            onChange={(v) => update('unit_price.unit', v)}
            options={UNIT_OPTIONS}
          />
        </div>
      </div>

      {/* Tiers (for deductions) */}
      {isDeduction && (
        <TierEditor
          tiers={el.tiers}
          onChange={(tiers) => update('tiers', tiers)}
        />
      )}
    </div>
  );
}

export default function StageParsing({ contractId }) {
  const { recipe, saveRecipe, currentContract } = useContractStore();
  const [contractText, setContractText] = useState('');
  const [localRecipe, setLocalRecipe] = useState(makeEmptyRecipe());
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    if (recipe) {
      setLocalRecipe(JSON.parse(JSON.stringify(recipe)));
    } else {
      setLocalRecipe(makeEmptyRecipe());
    }
  }, [recipe]);

  const updateElement = (index, updated) => {
    const next = { ...localRecipe, elements: localRecipe.elements.map((el, i) => i === index ? updated : el) };
    setLocalRecipe(next);
  };

  const removeElement = (index) => {
    const next = { ...localRecipe, elements: localRecipe.elements.filter((_, i) => i !== index) };
    setLocalRecipe(next);
  };

  const addElement = () => {
    const next = { ...localRecipe, elements: [...localRecipe.elements, makeElement()] };
    setLocalRecipe(next);
  };

  const addDeduction = () => {
    const next = { ...localRecipe, elements: [...localRecipe.elements, makeDeduction()] };
    setLocalRecipe(next);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      await saveRecipe(contractId, localRecipe);
      setSaveMsg('保存成功');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (err) {
      setSaveMsg(`保存失败：${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      {/* Left: contract text */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        padding: '16px',
        borderRight: `1px solid ${T.border}`,
        overflow: 'hidden',
      }}>
        <div style={{
          fontSize: 12,
          fontWeight: 600,
          color: T.muted,
          marginBottom: 8,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}>
          合同文本
        </div>
        <textarea
          value={contractText}
          onChange={(e) => setContractText(e.target.value)}
          placeholder="粘贴或输入合同条款…"
          style={{
            flex: 1,
            background: '#22232a',
            border: `1px solid ${T.border}`,
            color: T.text,
            padding: '10px',
            borderRadius: 6,
            fontSize: 12,
            fontFamily: T.mono,
            lineHeight: 1.7,
            resize: 'none',
            outline: 'none',
          }}
        />
      </div>

      {/* Right: recipe editor */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '12px 16px',
          borderBottom: `1px solid ${T.border}`,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: T.surface,
          flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: T.muted, marginRight: 4, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            计价配方
          </span>
          <button onClick={addElement} style={{ ...btnSecondary, fontSize: 11, padding: '4px 10px' }}>
            + 计价元素
          </button>
          <button onClick={addDeduction} style={{ ...btnSecondary, fontSize: 11, padding: '4px 10px', color: T.red, borderColor: '#5c1a1a' }}>
            + 杂质扣款
          </button>
          <div style={{ flex: 1 }} />
          <button onClick={handleSave} disabled={saving} style={{ ...btnPrimary, fontSize: 11, padding: '5px 14px', opacity: saving ? 0.7 : 1 }}>
            {saving ? '保存中…' : '保存配方'}
          </button>
          {saveMsg && (
            <span style={{ fontSize: 11, color: saveMsg.includes('失败') ? T.red : T.green }}>
              {saveMsg}
            </span>
          )}
        </div>

        {/* Scrollable element list */}
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 16px' }}>
          {localRecipe.elements.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              justifyContent: 'center', height: '100%', gap: 8, color: T.muted,
            }}>
              <div style={{ fontSize: 30, opacity: 0.3 }}>◻</div>
              <div style={{ fontSize: 12 }}>点击上方按钮添加计价元素或杂质扣款</div>
            </div>
          ) : (
            localRecipe.elements.map((el, i) => (
              <ElementCard
                key={i}
                el={el}
                index={i}
                onChange={updateElement}
                onRemove={removeElement}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
