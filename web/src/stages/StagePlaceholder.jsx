import React from 'react';
import { T } from '../theme.js';

const STAGE_NAMES = ['测算', '解析', '跟单', '定价', '结算', '资金'];

export default function StagePlaceholder({ stage }) {
  const name = STAGE_NAMES[stage] ?? `阶段 ${stage}`;
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 12,
      color: T.muted,
      padding: 40,
    }}>
      <div style={{ fontSize: 40, opacity: 0.3 }}>◻</div>
      <div style={{ fontSize: 16, fontWeight: 500, color: T.dim }}>
        {name}（开发中）
      </div>
      <div style={{ fontSize: 12, color: T.hint }}>
        阶段 {stage} 功能尚未实现
      </div>
    </div>
  );
}
