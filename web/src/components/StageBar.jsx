import React from 'react';
import { T } from '../theme.js';

const STAGES = [
  { index: 0, name: '测算' },
  { index: 1, name: '解析' },
  { index: 2, name: '跟单' },
  { index: 3, name: '定价' },
  { index: 4, name: '结算' },
  { index: 5, name: '资金' },
];

export default function StageBar({ activeStage, onSelect }) {
  return (
    <div style={{
      display: 'flex',
      gap: 4,
      padding: '12px 20px',
      borderBottom: `1px solid ${T.border}`,
      background: T.surface,
    }}>
      {STAGES.map((stage) => {
        const isActive = stage.index === activeStage;
        return (
          <button
            key={stage.index}
            onClick={() => onSelect(stage.index)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 12px',
              borderRadius: 4,
              border: isActive ? `1px solid ${T.accent}` : `1px solid ${T.border}`,
              background: isActive ? T.accentBg : 'transparent',
              color: isActive ? T.accent : T.muted,
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: isActive ? 600 : 400,
              fontFamily: T.sans,
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = T.card;
                e.currentTarget.style.color = T.text;
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = T.muted;
              }
            }}
          >
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 16,
              height: 16,
              borderRadius: '50%',
              background: isActive ? T.accent : T.border,
              color: isActive ? '#0f1014' : T.dim,
              fontSize: 10,
              fontWeight: 700,
              flexShrink: 0,
            }}>
              {stage.index}
            </span>
            {stage.name}
          </button>
        );
      })}
    </div>
  );
}
