import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { T } from '../theme.js';

const NAV_ITEMS = [
  { label: '驾驶舱', icon: '◫', path: '/dashboard', disabled: true },
  { label: '合同', icon: '☰', path: '/contracts', disabled: false },
  { label: '资金', icon: '◇', path: '/finance', disabled: true },
  { label: '库存', icon: '▤', path: '/inventory', disabled: true },
  { label: '行情', icon: '△', path: '/market', disabled: true },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div style={{
      width: 56,
      minWidth: 56,
      background: T.surface,
      borderRight: `1px solid ${T.border}`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: 12,
      paddingBottom: 12,
      gap: 4,
    }}>
      {/* Logo */}
      <div style={{
        width: 36,
        height: 36,
        borderRadius: 6,
        background: T.accent,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontWeight: 700,
        color: '#0f1014',
        marginBottom: 16,
        fontFamily: T.mono,
        letterSpacing: 0,
        flexShrink: 0,
      }}>
        TH
      </div>

      {/* Nav Items */}
      {NAV_ITEMS.map((item) => {
        const isActive = location.pathname.startsWith(item.path);
        return (
          <button
            key={item.path}
            title={item.label}
            disabled={item.disabled}
            onClick={() => !item.disabled && navigate(item.path)}
            style={{
              width: 40,
              height: 40,
              borderRadius: 6,
              border: 'none',
              background: isActive ? T.accentBg : 'transparent',
              color: isActive ? T.accent : item.disabled ? T.hint : T.muted,
              cursor: item.disabled ? 'default' : 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2,
              fontSize: 16,
              opacity: item.disabled ? 0.4 : 1,
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!item.disabled && !isActive) {
                e.currentTarget.style.background = T.card;
              }
            }}
            onMouseLeave={(e) => {
              if (!item.disabled && !isActive) {
                e.currentTarget.style.background = 'transparent';
              }
            }}
          >
            <span style={{ fontSize: 15, lineHeight: 1 }}>{item.icon}</span>
          </button>
        );
      })}
    </div>
  );
}
