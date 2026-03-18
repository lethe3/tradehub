export const T = {
  bg: '#0f1014',
  surface: '#16171c',
  card: '#1c1d23',
  cardHover: '#22232a',
  border: '#2a2b32',
  borderLight: '#35363e',
  text: '#e2e2e6',
  muted: '#8b8d96',
  dim: '#55565f',
  hint: '#3e3f47',
  accent: '#5b9aff',
  accentBg: '#1a2d4d',
  green: '#3dd68c',
  greenBg: '#0f2e22',
  amber: '#f0a030',
  amberBg: '#332508',
  red: '#f06060',
  redBg: '#301515',
  purple: '#a78bfa',
  purpleBg: '#1f1a33',
  sans: "'IBM Plex Sans', system-ui, sans-serif",
  mono: "'IBM Plex Mono', 'SF Mono', monospace",
};

export function fmt(val, decimals = 2) {
  const n = Number(val);
  if (isNaN(n)) return val ?? '—';
  return n.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export const inputStyle = {
  background: '#22232a',
  border: `1px solid #2a2b32`,
  color: '#e2e2e6',
  padding: '6px 10px',
  borderRadius: 4,
  fontSize: 13,
  fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
  outline: 'none',
  width: '100%',
};

export const btnPrimary = {
  background: '#5b9aff',
  color: '#0f1014',
  border: 'none',
  borderRadius: 4,
  padding: '6px 14px',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
};

export const btnSecondary = {
  background: '#22232a',
  color: '#e2e2e6',
  border: '1px solid #2a2b32',
  borderRadius: 4,
  padding: '6px 14px',
  fontSize: 13,
  cursor: 'pointer',
  fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
};

export const btnDanger = {
  background: 'transparent',
  color: '#f06060',
  border: '1px solid #301515',
  borderRadius: 4,
  padding: '4px 10px',
  fontSize: 12,
  cursor: 'pointer',
  fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
};
