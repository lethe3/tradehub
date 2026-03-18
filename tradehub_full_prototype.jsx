import { useState, useMemo } from "react";

// ═══════════════════════════════════════════════════
// Design Tokens
// ═══════════════════════════════════════════════════
const T = {
  bg: "#0f1014", surface: "#16171c", card: "#1c1d23", cardHover: "#22232a",
  border: "#2a2b32", borderLight: "#35363e",
  text: "#e2e2e6", muted: "#8b8d96", dim: "#55565f", hint: "#3e3f47",
  accent: "#5b9aff", accentBg: "#1a2d4d",
  green: "#3dd68c", greenBg: "#0f2e22",
  amber: "#f0a030", amberBg: "#332508",
  red: "#f06060", redBg: "#301515",
  purple: "#a78bfa", purpleBg: "#1f1a33",
  sans: "'IBM Plex Sans', system-ui, sans-serif",
  mono: "'IBM Plex Mono', 'SF Mono', monospace",
};

const pill = (bg, fg, text) => (
  <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 4, background: bg, color: fg, letterSpacing: "0.02em" }}>{text}</span>
);

const fmt = (n, d=2) => n == null ? "—" : Number(n).toLocaleString("zh-CN", { minimumFractionDigits: d, maximumFractionDigits: d });

// ═══════════════════════════════════════════════════
// Mock Data
// ═══════════════════════════════════════════════════
const CONTRACTS = [
  { id: "CU-2025-017", counterparty: "XX矿业", direction: "采购", commodity: "铜精矿", stage: 4, signDate: "2025-03-01",
    tickets: 12, ticketsTotal: 15, assays: 4, assaysTotal: 5, basePriceLocked: 2, basePriceTotal: 2,
    totalWeight: 385.6, settlementAmount: 2850000, prepaid: 2000000 },
  { id: "CU-2025-018", counterparty: "YY冶炼", direction: "销售", commodity: "铜精矿", stage: 2, signDate: "2025-03-10",
    tickets: 5, ticketsTotal: 15, assays: 2, assaysTotal: 5, basePriceLocked: 0, basePriceTotal: 2,
    totalWeight: 142.3, settlementAmount: null, prepaid: 500000 },
  { id: "PB-2025-003", counterparty: "ZZ贸易", direction: "采购", commodity: "铅精矿", stage: 5, signDate: "2025-02-15",
    tickets: 20, ticketsTotal: 20, assays: 8, assaysTotal: 8, basePriceLocked: 3, basePriceTotal: 3,
    totalWeight: 620.0, settlementAmount: 1520000, prepaid: 1200000 },
  { id: "EST-2025-009", counterparty: "AA矿山", direction: "采购", commodity: "铜精矿", stage: -1, signDate: null,
    tickets: 0, ticketsTotal: 0, assays: 0, assaysTotal: 0, basePriceLocked: 0, basePriceTotal: 0,
    totalWeight: 0, settlementAmount: null, prepaid: 0 },
];

const TODOS = [
  { type: "urgent", text: "CU-2025-017 有 3 张磅单待录入", contract: "CU-2025-017" },
  { type: "action", text: "CU-2025-017 Cu 均价锚定期已结束，可计算", contract: "CU-2025-017" },
  { type: "action", text: "CU-2025-018 已收到 2 份化验单，待配对", contract: "CU-2025-018" },
  { type: "info", text: "PB-2025-003 结算已完成，尾款 ¥320,000 待收", contract: "PB-2025-003" },
  { type: "info", text: "AA矿山报价测算已保存，待决定是否签约", contract: "EST-2025-009" },
];

const STAGE_NAMES = ["测算", "解析", "跟单", "定价", "结算", "资金"];
const STAGE_COLORS = [T.purple, T.accent, T.green, T.amber, T.accent, T.green];

// ═══════════════════════════════════════════════════
// Sidebar
// ═══════════════════════════════════════════════════
function Sidebar({ page, setPage }) {
  const items = [
    { key: "dash", icon: "◫", label: "驾驶舱" },
    { key: "contracts", icon: "□", label: "合同" },
    { key: "funds", icon: "◇", label: "资金" },
    { key: "inventory", icon: "▤", label: "库存" },
    { key: "market", icon: "△", label: "行情" },
  ];
  return (
    <div style={{ width: 56, background: T.surface, borderRight: `1px solid ${T.border}`, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 12, gap: 4, flexShrink: 0 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: T.accent, marginBottom: 16, letterSpacing: -1 }}>TH</div>
      {items.map(it => (
        <button key={it.key} onClick={() => setPage(it.key)} style={{
          width: 44, height: 44, borderRadius: 8, border: "none", cursor: "pointer",
          background: page === it.key ? T.accentBg : "transparent",
          color: page === it.key ? T.accent : T.dim,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2,
          fontSize: 16, transition: "all 0.15s",
        }}>
          <span>{it.icon}</span>
          <span style={{ fontSize: 9, fontWeight: 500 }}>{it.label}</span>
        </button>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════
function Dashboard({ onOpenContract }) {
  return (
    <div style={{ padding: 24, maxWidth: 960 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: T.text, margin: "0 0 20px" }}>驾驶舱</h2>

      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "在跟合同", value: "3", sub: "1 测算中", color: T.accent },
          { label: "应收未收", value: "¥320,000", sub: "1 笔逾期", color: T.amber },
          { label: "应付未付", value: "¥850,000", sub: "2 笔待付", color: T.red },
          { label: "库存金属量", value: "28.5t Cu", sub: "敞口 ¥185万", color: T.green },
        ].map((k, i) => (
          <div key={i} style={{ background: T.card, borderRadius: 10, padding: "14px 16px", border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 11, color: T.muted, marginBottom: 6 }}>{k.label}</div>
            <div style={{ fontSize: 20, fontWeight: 600, color: k.color, fontFamily: T.mono }}>{k.value}</div>
            <div style={{ fontSize: 11, color: T.dim, marginTop: 4 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* Two columns: Todos + Contracts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Todos */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 10 }}>待办事项</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {TODOS.map((t, i) => (
              <div key={i} onClick={() => onOpenContract(t.contract)} style={{
                padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                background: T.card, border: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", gap: 10, transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = T.cardHover}
              onMouseLeave={e => e.currentTarget.style.background = T.card}>
                <span style={{
                  width: 6, height: 6, borderRadius: 3, flexShrink: 0,
                  background: t.type === "urgent" ? T.red : t.type === "action" ? T.amber : T.dim
                }} />
                <span style={{ fontSize: 12, color: T.text, lineHeight: 1.5 }}>{t.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Active contracts */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 10 }}>活跃合同</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {CONTRACTS.map(c => (
              <div key={c.id} onClick={() => onOpenContract(c.id)} style={{
                padding: "10px 14px", borderRadius: 8, cursor: "pointer",
                background: T.card, border: `1px solid ${T.border}`, transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = T.cardHover}
              onMouseLeave={e => e.currentTarget.style.background = T.card}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: T.mono }}>{c.id}</span>
                  {pill(c.direction === "采购" ? T.accentBg : T.greenBg, c.direction === "采购" ? T.accent : T.green, c.direction)}
                  {c.stage === -1 ? pill(T.purpleBg, T.purple, "测算") : pill(
                    T.border, STAGE_COLORS[c.stage] || T.muted, STAGE_NAMES[c.stage] || "—"
                  )}
                  <span style={{ fontSize: 12, color: T.dim }}>{c.counterparty}</span>
                </div>
                {c.stage >= 0 && (
                  <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.dim, fontFamily: T.mono }}>
                    <span>磅单 {c.tickets}/{c.ticketsTotal}</span>
                    <span>化验 {c.assays}/{c.assaysTotal}</span>
                    <span>基准价 {c.basePriceLocked}/{c.basePriceTotal}</span>
                    {c.settlementAmount && <span style={{ color: T.green }}>¥{fmt(c.settlementAmount, 0)}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// Contract Detail — Stage Panels
// ═══════════════════════════════════════════════════

function StageEstimate() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, padding: 20 }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 12 }}>输入假设</div>
        {[
          { label: "预估品位 Cu%", value: "18.5" }, { label: "预估品位 Au g/t", value: "4.2" },
          { label: "预估湿重", value: "500 吨" }, { label: "预估水份", value: "8%" },
          { label: "对方报价条件", value: "系数法 + 品位扣减1%" },
        ].map((f, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${T.border}22`, fontSize: 13 }}>
            <span style={{ color: T.muted }}>{f.label}</span>
            <span style={{ color: T.text, fontFamily: T.mono }}>{f.value}</span>
          </div>
        ))}
        <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 8, background: T.purpleBg, border: `1px solid ${T.purple}33` }}>
          <div style={{ fontSize: 11, color: T.purple, marginBottom: 4 }}>测算结果</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: T.purple, fontFamily: T.mono }}>¥2,850,000</div>
          <div style={{ fontSize: 11, color: T.dim, marginTop: 4 }}>预估吨利润 ¥380</div>
        </div>
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 12 }}>计价配方（草稿）</div>
        <div style={{ background: T.card, borderRadius: 8, padding: 14, border: `1px solid ${T.border}`, fontSize: 12, fontFamily: T.mono, color: T.muted, lineHeight: 2 }}>
          <div>Cu: metal_content · fixed_price</div>
          <div>  └ tier_multiply(base_price) → 5档系数</div>
          <div>  └ segment_accumulate(cu_pct, anchor=18)</div>
          <div>Au: metal_content · tier_multiply(au_gt)</div>
          <div>As: dry_weight · tier_fixed(as_pct)</div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button style={{ flex: 1, padding: "10px 0", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.muted, fontSize: 12, cursor: "pointer" }}>保存测算</button>
          <button style={{ flex: 1, padding: "10px 0", borderRadius: 6, border: "none", background: T.accent, color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>转为合同 →</button>
        </div>
      </div>
    </div>
  );
}

function StageParseContract() {
  const [activeEl, setActiveEl] = useState("Cu");
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, height: "100%" }}>
      {/* Left: contract text */}
      <div style={{ borderRight: `1px solid ${T.border}`, padding: 20, overflow: "auto" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 12 }}>合同原文</div>
        {["Cu", "Au", "As"].map(el => (
          <div key={el} style={{
            padding: "12px 14px", marginBottom: 8, borderRadius: 8, fontSize: 12, lineHeight: 1.8,
            color: T.muted, fontFamily: T.sans,
            background: activeEl === el ? T.accentBg + "40" : T.card,
            border: `1px solid ${activeEl === el ? T.accent + "60" : T.border}`,
            cursor: "pointer", transition: "all 0.15s",
          }} onClick={() => setActiveEl(el)}>
            <div style={{ marginBottom: 4 }}>{pill(el === "As" ? T.redBg : T.accentBg, el === "As" ? T.red : T.accent, el)}</div>
            {el === "Cu" && "铜价格：以发货日后上海有色网1#铜连续5个交易日平均价为基准价格，乘以相应的计价系数，再加减品位金额。计价系数：50000-54999→88%, 55000-59999→89%..."}
            {el === "Au" && "金价格：含金≥1克/干吨开始计价，以发货日后上海黄金交易所Au(T+D)连续5个交易日加权平均价为基准价格乘以相应计价系数。"}
            {el === "As" && "砷含量≥0.3%时开始扣款：0.3-0.5%→20元/干吨，0.5-1.0%→50元/干吨，≥1.0%另议。"}
          </div>
        ))}
      </div>
      {/* Right: structured extraction */}
      <div style={{ padding: 20, overflow: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: T.muted }}>结构化摘录</span>
          {pill(T.amberBg, T.amber, "LLM草稿 · 待确认")}
        </div>
        <div style={{ background: T.card, borderRadius: 8, padding: 14, border: `1px solid ${activeEl === "Cu" ? T.accent + "60" : T.border}`, marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            {pill(T.accentBg, T.accent, "Cu")}
            <span style={{ fontSize: 11, color: T.dim }}>金属量计价 · 需基准价</span>
          </div>
          <div style={{ fontSize: 12, fontFamily: T.mono, color: T.muted, lineHeight: 2 }}>
            <div>数量 = 干重 × (Cu% - <span style={{ color: T.amber, cursor: "pointer" }}>1.0</span>%)</div>
            <div>基准价 = 均价(上海有色1#铜, <span style={{ color: T.amber, cursor: "pointer" }}>5</span>交易日)</div>
            <div>× 阶梯系数(按基准价查表, <span style={{ color: T.amber, cursor: "pointer" }}>7</span>档)</div>
            <div>+ 品位调整(基准<span style={{ color: T.amber, cursor: "pointer" }}>18</span>%, 分段累计, <span style={{ color: T.amber, cursor: "pointer" }}>5</span>段)</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button style={{ flex: 1, padding: "10px 0", borderRadius: 6, border: "none", background: T.green, color: "#000", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>确认全部配方 ✓</button>
        </div>
      </div>
    </div>
  );
}

function StageTracking() {
  const samples = [
    { id: "S-001", tickets: [{ no: "P001", weight: 32.5 }, { no: "P002", weight: 31.8 }], assay: { cu: 17.82, au: 5.3, h2o: 7.8, as: 0.35 } },
    { id: "S-002", tickets: [{ no: "P003", weight: 28.4 }, { no: "P004", weight: 29.1 }], assay: { cu: 18.45, au: 4.1, h2o: 8.2, as: 0.22 } },
    { id: "S-003", tickets: [{ no: "P005", weight: 33.2 }], assay: null },
  ];
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
        {[
          { label: "磅单", done: 5, total: 6, color: T.green },
          { label: "化验单", done: 2, total: 3, color: T.amber },
          { label: "已配对", done: 2, total: 3, color: T.accent },
        ].map((p, i) => (
          <div key={i} style={{ flex: 1, background: T.card, borderRadius: 8, padding: "10px 14px", border: `1px solid ${T.border}` }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: T.muted, marginBottom: 6 }}><span>{p.label}</span><span style={{ fontFamily: T.mono, color: p.done === p.total ? T.green : T.amber }}>{p.done}/{p.total}</span></div>
            <div style={{ height: 3, borderRadius: 2, background: T.border }}>
              <div style={{ height: 3, borderRadius: 2, background: p.color, width: `${p.done / p.total * 100}%`, transition: "width 0.3s" }} />
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 10 }}>配对视图（按样号）</div>
      {samples.map(s => (
        <div key={s.id} style={{ background: T.card, borderRadius: 8, padding: "12px 16px", marginBottom: 8, border: `1px solid ${s.assay ? T.border : T.red + "40"}` }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{s.id}</span>
              {s.assay ? pill(T.greenBg, T.green, "已配对") : pill(T.redBg, T.red, "缺化验单")}
            </div>
            <span style={{ fontSize: 12, fontFamily: T.mono, color: T.muted }}>
              {s.tickets.reduce((a, t) => a + t.weight, 0).toFixed(1)}t
            </span>
          </div>
          <div style={{ display: "flex", gap: 20, fontSize: 11, fontFamily: T.mono, color: T.dim }}>
            <span>磅单: {s.tickets.map(t => `${t.no}(${t.weight}t)`).join(", ")}</span>
            {s.assay && <span style={{ color: T.muted }}>Cu {s.assay.cu}% · Au {s.assay.au}g/t · H₂O {s.assay.h2o}%</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function StagePricing() {
  const prices = [
    { element: "Cu", source: "均价", srcName: "上海有色1#铜", range: "03/06 ~ 03/12", value: 67200, unit: "元/吨", status: "locked" },
    { element: "Au", source: "均价", srcName: "上海金交所Au(T+D)", range: "03/06 ~ 03/12", value: 565, unit: "元/克", status: "locked" },
  ];
  return (
    <div style={{ padding: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 12 }}>基准价确认</div>
      {prices.map((p, i) => (
        <div key={i} style={{ background: T.card, borderRadius: 8, padding: "14px 18px", marginBottom: 10, border: `1px solid ${p.status === "locked" ? T.border : T.amber}` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{p.element}</span>
              {pill(T.amberBg, T.amber, p.source)}
            </div>
            {p.status === "locked" ? pill(T.greenBg, T.green, "已锁定") : pill(T.amberBg, T.amber, "待确认")}
          </div>
          <div style={{ fontSize: 12, color: T.dim, fontFamily: T.mono, lineHeight: 2 }}>
            <div>来源: {p.srcName}</div>
            <div>锚定期: {p.range}</div>
            <div>覆盖: 全部磅单</div>
          </div>
          <div style={{ marginTop: 8 }}>
            <span style={{ fontSize: 22, fontWeight: 600, color: T.text, fontFamily: T.mono }}>¥{p.value.toLocaleString()}</span>
            <span style={{ fontSize: 11, color: T.dim, marginLeft: 6 }}>{p.unit}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function StageSettlement() {
  const samples = [
    { id: "S-001", wet: 64.3, h2o: 7.8, elements: [
      { el: "Cu", type: "element", qty: "10.103t金属", price: "60,280", amount: 608868 },
      { el: "Au", type: "element", qty: "0.314kg", price: "469/克", amount: 147466 },
      { el: "As", type: "deduction", qty: "59.28t干重", price: "20/干吨", amount: 1186 },
    ]},
    { id: "S-002", wet: 57.5, h2o: 8.2, elements: [
      { el: "Cu", type: "element", qty: "9.210t金属", price: "61,152", amount: 563210 },
      { el: "Au", type: "element", qty: "0.216kg", price: "469/克", amount: 101304 },
    ]},
  ];
  const totalIncome = 608868 + 147466 + 563210 + 101304;
  const totalDeduction = 1186;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 0, height: "100%" }}>
      <div style={{ borderRight: `1px solid ${T.border}`, padding: 20, overflow: "auto" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {["✓ 磅单齐", "✓ 化验单齐", "✓ 基准价锁定"].map((c, i) => (
            <span key={i} style={{ fontSize: 11, padding: "4px 10px", borderRadius: 4, background: T.greenBg, color: T.green }}>{c}</span>
          ))}
        </div>
        {samples.map(s => (
          <div key={s.id} style={{ background: T.card, borderRadius: 8, marginBottom: 10, border: `1px solid ${T.border}`, overflow: "hidden" }}>
            <div style={{ padding: "10px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>样号 {s.id}</span>
              <span style={{ fontSize: 12, color: T.dim, fontFamily: T.mono }}>{s.wet}t · H₂O {s.h2o}%</span>
            </div>
            {s.elements.map((e, i) => (
              <div key={i} style={{ padding: "8px 16px", borderBottom: i < s.elements.length - 1 ? `1px solid ${T.border}22` : "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {pill(e.type === "deduction" ? T.redBg : T.accentBg, e.type === "deduction" ? T.red : T.accent, e.el)}
                  <span style={{ fontSize: 11, color: T.dim, fontFamily: T.mono }}>{e.qty} × {e.price}</span>
                </div>
                <span style={{ fontSize: 13, fontWeight: 600, fontFamily: T.mono, color: e.type === "deduction" ? T.red : T.text }}>
                  {e.type === "deduction" ? "-" : ""}¥{fmt(e.amount, 0)}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div style={{ padding: 20, display: "flex", flexDirection: "column" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 16 }}>结算汇总</div>
        <div style={{ background: T.card, borderRadius: 8, padding: 16, border: `1px solid ${T.border}`, flex: 1 }}>
          {[
            { label: "元素货款", value: totalIncome, color: T.text },
            { label: "杂质扣款", value: -totalDeduction, color: T.red },
            { label: "化验费", value: -1500, color: T.muted },
            { label: "运费", value: -12000, color: T.muted },
          ].map((r, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${T.border}22`, fontSize: 13 }}>
              <span style={{ color: T.muted }}>{r.label}</span>
              <span style={{ fontFamily: T.mono, color: r.color }}>{r.value < 0 ? "-" : ""}¥{fmt(Math.abs(r.value), 0)}</span>
            </div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between", padding: "14px 0 8px", borderTop: `1px solid ${T.border}`, marginTop: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>结算净额</span>
            <span style={{ fontSize: 20, fontWeight: 700, fontFamily: T.mono, color: T.green }}>¥{fmt(totalIncome - totalDeduction - 1500 - 12000, 0)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 12 }}>
            <span style={{ color: T.dim }}>已预付</span>
            <span style={{ fontFamily: T.mono, color: T.muted }}>-¥2,000,000</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0 12px", fontSize: 12 }}>
            <span style={{ color: T.dim }}>尾款</span>
            <span style={{ fontFamily: T.mono, color: T.amber }}>¥{fmt(totalIncome - totalDeduction - 1500 - 12000 - 2000000, 0)}</span>
          </div>
        </div>
        <button style={{ marginTop: 12, padding: "12px 0", borderRadius: 6, border: "none", background: T.accent, color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          生成结算单 →
        </button>
      </div>
    </div>
  );
}

function StageFunds() {
  const flows = [
    { date: "03/02", type: "预付款", dir: "付", amount: 1000000, note: "首批预付" },
    { date: "03/08", type: "预付款", dir: "付", amount: 1000000, note: "二批预付" },
    { date: "03/15", type: "运费", dir: "付", amount: 12000, note: "3车运费" },
    { date: "03/18", type: "化验费", dir: "付", amount: 1500, note: "SGS化验" },
    { date: "—", type: "结算款", dir: "付", amount: null, note: "待结算确认" },
  ];
  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { label: "已付总额", value: "¥2,013,500", color: T.red },
          { label: "结算应付", value: "¥1,406,162", color: T.amber },
          { label: "余额（多付）", value: "¥607,338", color: T.green },
        ].map((k, i) => (
          <div key={i} style={{ background: T.card, borderRadius: 8, padding: "10px 14px", border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>{k.label}</div>
            <div style={{ fontSize: 17, fontWeight: 600, color: k.color, fontFamily: T.mono }}>{k.value}</div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.muted, marginBottom: 10 }}>资金流水</div>
      <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse", fontFamily: T.mono }}>
        <thead>
          <tr style={{ color: T.dim, borderBottom: `1px solid ${T.border}` }}>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 500 }}>日期</th>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 500 }}>类型</th>
            <th style={{ textAlign: "center", padding: "8px 10px", fontWeight: 500 }}>方向</th>
            <th style={{ textAlign: "right", padding: "8px 10px", fontWeight: 500 }}>金额</th>
            <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 500 }}>摘要</th>
          </tr>
        </thead>
        <tbody>
          {flows.map((f, i) => (
            <tr key={i} style={{ borderBottom: `1px solid ${T.border}22`, color: T.text }}>
              <td style={{ padding: "8px 10px", color: T.muted }}>{f.date}</td>
              <td style={{ padding: "8px 10px" }}>{f.type}</td>
              <td style={{ padding: "8px 10px", textAlign: "center" }}>{pill(f.dir === "付" ? T.redBg : T.greenBg, f.dir === "付" ? T.red : T.green, f.dir)}</td>
              <td style={{ padding: "8px 10px", textAlign: "right", fontWeight: 500, color: f.amount ? T.text : T.dim }}>{f.amount ? `¥${fmt(f.amount, 0)}` : "—"}</td>
              <td style={{ padding: "8px 10px", color: T.dim }}>{f.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// Contract Detail Container
// ═══════════════════════════════════════════════════
function ContractDetail({ contract, onBack }) {
  const isEstimate = contract.stage === -1;
  const stages = isEstimate
    ? [{ key: 0, label: "测算" }]
    : STAGE_NAMES.map((s, i) => ({ key: i, label: s }));
  const [activeStage, setActiveStage] = useState(isEstimate ? 0 : contract.stage);

  const stageComponents = [
    <StageEstimate />,
    <StageParseContract />,
    <StageTracking />,
    <StagePricing />,
    <StageSettlement />,
    <StageFunds />,
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Header */}
      <div style={{ padding: "12px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
        <button onClick={onBack} style={{ background: "transparent", border: "none", color: T.dim, cursor: "pointer", fontSize: 14, padding: "4px 8px" }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 600, color: T.text, fontFamily: T.mono }}>{contract.id}</span>
        {pill(contract.direction === "采购" ? T.accentBg : T.greenBg, contract.direction === "采购" ? T.accent : T.green, contract.direction)}
        <span style={{ fontSize: 13, color: T.muted }}>{contract.counterparty} · {contract.commodity}</span>
      </div>

      {/* Stage tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${T.border}`, padding: "0 16px", flexShrink: 0 }}>
        {stages.map((s, i) => {
          const isActive = s.key === activeStage;
          const isPast = s.key < (isEstimate ? 1 : contract.stage);
          const isCurrent = s.key === (isEstimate ? 0 : contract.stage);
          return (
            <button key={s.key} onClick={() => setActiveStage(s.key)} style={{
              padding: "10px 16px", fontSize: 12, fontWeight: isActive ? 600 : 400, cursor: "pointer",
              color: isActive ? STAGE_COLORS[s.key] || T.accent : isPast ? T.green : isCurrent ? T.text : T.dim,
              background: "transparent", border: "none",
              borderBottom: isActive ? `2px solid ${STAGE_COLORS[s.key] || T.accent}` : "2px solid transparent",
              fontFamily: T.sans, transition: "all 0.15s",
            }}>
              {isPast && !isActive ? "✓ " : ""}{s.label}
            </button>
          );
        })}
      </div>

      {/* Stage content */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {stageComponents[activeStage] || <div style={{ padding: 40, color: T.dim, textAlign: "center" }}>开发中...</div>}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// Placeholder pages
// ═══════════════════════════════════════════════════
function PlaceholderPage({ title, description, items }) {
  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: T.text, margin: "0 0 8px" }}>{title}</h2>
      <p style={{ fontSize: 13, color: T.dim, margin: "0 0 24px" }}>{description}</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {items.map((it, i) => (
          <div key={i} style={{ background: T.card, borderRadius: 8, padding: "12px 16px", border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: T.text, marginBottom: 4 }}>{it.title}</div>
            <div style={{ fontSize: 12, color: T.dim }}>{it.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════
// Main App
// ═══════════════════════════════════════════════════
export default function App() {
  const [page, setPage] = useState("dash");
  const [selectedContract, setSelectedContract] = useState(null);

  const openContract = (id) => {
    setSelectedContract(CONTRACTS.find(c => c.id === id) || null);
    setPage("contracts");
  };

  const mainContent = () => {
    if (page === "contracts" && selectedContract) {
      return <ContractDetail contract={selectedContract} onBack={() => setSelectedContract(null)} />;
    }
    if (page === "dash" || (page === "contracts" && !selectedContract)) {
      return <Dashboard onOpenContract={openContract} />;
    }
    if (page === "funds") {
      return <PlaceholderPage title="资金总览" description="所有合同的资金汇总视图 · Phase 2 实现"
        items={[
          { title: "应收账款", desc: "按合同、按账龄的应收明细和催收状态" },
          { title: "应付账款", desc: "按合同、按到期日的应付明细和付款计划" },
          { title: "费用汇总", desc: "运费、化验费、差旅费等按类型和月份汇总" },
          { title: "利润估算", desc: "采销联动利润 = 销售额 - 采购成本 - 费用" },
        ]} />;
    }
    if (page === "inventory") {
      return <PlaceholderPage title="库存与敞口" description="货物追踪和风险管理 · Phase 3 实现"
        items={[
          { title: "库存明细", desc: "按品种、仓库、采购来源的实物库存" },
          { title: "出入库记录", desc: "历史出入库流水和在途货物" },
          { title: "货物流向", desc: "采购合同 → 库存 → 销售合同的分配关系" },
          { title: "敞口监控", desc: "库存金属量 × 当前市价 vs 加权采购成本" },
        ]} />;
    }
    if (page === "market") {
      return <PlaceholderPage title="行情中心" description="市场价格和基准价管理 · Phase 3 实现"
        items={[
          { title: "实时行情", desc: "铜、金、银、铅等品种的实时/日终价格" },
          { title: "待确认基准价", desc: "跨合同的基准价队列，一处确认多处生效" },
          { title: "历史价格", desc: "价格走势图表和数据导出" },
        ]} />;
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: T.bg, color: T.text, fontFamily: T.sans, fontSize: 13, overflow: "hidden" }}>
      <Sidebar page={page} setPage={(p) => { setPage(p); if (p !== "contracts") setSelectedContract(null); }} />
      <div style={{ flex: 1, overflow: "auto" }}>
        {mainContent()}
      </div>
    </div>
  );
}
