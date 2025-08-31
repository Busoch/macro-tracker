import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import EntriesPage from "./pages/EntriesPage"; // adjust path
import SummariesPage from "./pages/SummariesPage";
import Register from "./pages/Register";


export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/entries" element={<EntriesPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/summaries" element={<SummariesPage />} />
      </Routes>
    </Router>
  );
}
