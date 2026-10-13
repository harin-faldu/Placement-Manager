import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { AccessPage } from "./pages/Access";
import { AuditPage } from "./pages/Audit";
import { Dashboard } from "./pages/Dashboard";
import { ExceptionsPage } from "./pages/Exceptions";
import { Login } from "./pages/Login";
import { PolicyPage } from "./pages/Policy";
import { Recruitment } from "./pages/Recruitment";
import { Reports } from "./pages/Reports";
import { StudentDetail } from "./pages/StudentDetail";
import { Students } from "./pages/Students";
import { RequireAuth, Shell } from "./ui";

export function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route element={<RequireAuth />}>
        <Route element={<Shell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/students" element={<Students />} />
          <Route path="/students/:id" element={<StudentDetail />} />
          <Route path="/recruitment" element={<Recruitment />} />
          <Route path="/policy" element={<PolicyPage />} />
          <Route path="/exceptions" element={<ExceptionsPage />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/access" element={<AccessPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
