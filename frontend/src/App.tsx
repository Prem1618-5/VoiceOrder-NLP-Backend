import { BrowserRouter, Routes, Route } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import Auth from '@/pages/Auth';
import Dashboard from '@/pages/Dashboard';
import Parse from '@/pages/Parse';
import Session from '@/pages/Session';
import History from '@/pages/History';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public auth routes — outside AppShell */}
        <Route path="/login" element={<Auth />} />
        <Route path="/register" element={<Auth />} />

        {/* Protected routes — inside AppShell (handles auth redirect) */}
        <Route element={<AppShell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/parse" element={<Parse />} />
          <Route path="/session" element={<Session />} />
          <Route path="/history" element={<History />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
