import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import NeuroSyncGuard from "./NeuroSyncGuard";
import LandingPage from "./LandingPage";
import AwarenessPage from "./AwarenessPage";

function LandingRoute() {
  const navigate = useNavigate();
  return <LandingPage onGetStarted={() => navigate("/awareness")} />;
}

function AppShell() {
  return (
    <Routes>
      <Route path="/" element={<LandingRoute />} />
      <Route path="/awareness" element={<AwarenessPage />} />
      <Route path="/mobile" element={<NeuroSyncGuard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  </React.StrictMode>
);
