import { useState } from "react";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  const [authRequired, setAuthRequired] = useState(false);

  if (authRequired) {
    return <LoginPage />;
  }

  return <DashboardPage onAuthRequired={() => setAuthRequired(true)} />;
}
