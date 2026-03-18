import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import ContractList from './pages/ContractList.jsx';
import ContractDetail from './pages/ContractDetail.jsx';
import { T } from './theme.js';

function Layout({ children }) {
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      background: T.bg,
      overflow: 'hidden',
    }}>
      <Sidebar />
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        background: T.bg,
      }}>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/contracts" replace />} />
          <Route path="/contracts" element={<ContractList />} />
          <Route path="/contracts/:id" element={<ContractDetail />} />
          {/* Placeholder routes */}
          <Route path="/dashboard" element={
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 14 }}>
              驾驶舱（开发中）
            </div>
          } />
          <Route path="/finance" element={
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 14 }}>
              资金（开发中）
            </div>
          } />
          <Route path="/inventory" element={
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 14 }}>
              库存（开发中）
            </div>
          } />
          <Route path="/market" element={
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 14 }}>
              行情（开发中）
            </div>
          } />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
