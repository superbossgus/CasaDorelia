import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import Sales from "./pages/Sales";
import Inventory from "./pages/Inventory";
import Products from "./pages/Products";
import Ingredients from "./pages/Ingredients";
import IngredientInventory from "./pages/IngredientInventory";
import Recipes from "./pages/Recipes";
import Suppliers from "./pages/Suppliers";
import Purchases from "./pages/Purchases";
import Reports from "./pages/Reports";
import Users from "./pages/Users";
import Cafeterias from "./pages/Cafeterias";
import WhatsAppAlerts from "./pages/WhatsAppAlerts";
import Subscription from "./pages/Subscription";
import SubscriptionSuccess from "./pages/SubscriptionSuccess";
import SuperAdmin from "./pages/SuperAdmin";
import BusinessSettings from "./pages/BusinessSettings";
import Layout from "./components/Layout";

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // Super admin should go to their panel
  if (user.role === "superadmin" && !allowedRoles?.includes("superadmin")) {
    return <Navigate to="/superadmin" replace />;
  }
  
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          
          <Route path="/subscription" element={
            <ProtectedRoute>
              <Subscription />
            </ProtectedRoute>
          } />
          
          <Route path="/subscription/success" element={
            <ProtectedRoute>
              <SubscriptionSuccess />
            </ProtectedRoute>
          } />
          
          <Route path="/superadmin" element={
            <ProtectedRoute allowedRoles={["superadmin"]}>
              <SuperAdmin />
            </ProtectedRoute>
          } />
          
          <Route path="/dashboard" element={
            <ProtectedRoute>
              <Layout><Dashboard /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/sales" element={
            <ProtectedRoute>
              <Layout><Sales /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/inventory" element={
            <ProtectedRoute>
              <Layout><Inventory /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/products" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Products /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/ingredients" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Ingredients /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/ingredient-inventory" element={
            <ProtectedRoute>
              <Layout><IngredientInventory /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/recipes" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Recipes /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/suppliers" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Suppliers /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/purchases" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Purchases /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/reports" element={
            <ProtectedRoute allowedRoles={["admin", "gerente"]}>
              <Layout><Reports /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/users" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><Users /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/cafeterias" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><Cafeterias /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/whatsapp-alerts" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><WhatsAppAlerts /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/business-settings" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><BusinessSettings /></Layout>
            </ProtectedRoute>
          } />
        </Routes>
        <Toaster 
          position="top-right" 
          toastOptions={{
            style: {
              background: '#161616',
              border: '1px solid #27272A',
              color: '#EDEDED',
            },
          }}
        />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
