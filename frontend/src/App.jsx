import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";

import MainLayout from "./layouts/MainLayout";

import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import Dashboard from "./pages/dashboard/Dashboard";
import Cameras from "./pages/cameras/Cameras";
import Events from "./pages/events/Events";
import Household from "./pages/household/Household";
import Profile from "./pages/profile/Profile";
import { HouseholdProvider } from "./contexts/HouseholdContext";
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <HouseholdProvider>
          <Routes>
            {/* Public Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected Routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<MainLayout />}>
                <Route
                  path="/dashboard"
                  element={<Dashboard />}
                />

                <Route
                  path="/cameras"
                  element={<Cameras />}
                />

                <Route
                  path="/events"
                  element={<Events />}
                />

                <Route
                  path="/household"
                  element={<Household />}
                />

                <Route
                  path="/profile"
                  element={<Profile />}
                />
              </Route>
            </Route>

            {/* Default Route */}
            <Route
              path="/"
              element={<Navigate to="/dashboard" replace />}
            />

            {/* Not Found */}
            <Route
              path="*"
              element={<Navigate to="/dashboard" replace />}
            />
          </Routes>
        </HouseholdProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;