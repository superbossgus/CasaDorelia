import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import Landing from "./pages/Landing";
import CustomerLanding from "./pages/CustomerLanding";
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
import LoyaltyAdmin from "./pages/LoyaltyAdmin";
import LoyaltyLogin from "./pages/LoyaltyLogin";
import LoyaltyRegister from "./pages/LoyaltyRegister";
import LoyaltyRewards from "./pages/LoyaltyRewards";
import SalespeopleAdmin from "./pages/SalespeopleAdmin";
import PartnersLanding from "./pages/PartnersLanding";
import PartnersRegister from "./pages/PartnersRegister";
import PartnersLogin from "./pages/PartnersLogin";
import PartnersDashboard from "./pages/PartnersDashboard";
import PartnersPurchaseSuccess from "./pages/PartnersPurchaseSuccess";
import PartnersAdmin from "./pages/PartnersAdmin";
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
    return <Navigate to="/admin" replace />;
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
          {/* ========== CUSTOMER ROUTES (Public) ========== */}
          <Route path="/" element={<CustomerLanding />} />
          <Route path="/loyalty/login" element={<LoyaltyLogin />} />
          <Route path="/loyalty/register" element={<LoyaltyRegister />} />
          <Route path="/loyalty/rewards" element={<LoyaltyRewards />} />
          
          {/* ========== PARTNER/INVESTOR ROUTES (Public) ========== */}
          <Route path="/socios" element={<PartnersLanding />} />
          <Route path="/socios/registro" element={<PartnersRegister />} />
          <Route path="/socios/login" element={<PartnersLogin />} />
          <Route path="/socios/dashboard" element={<PartnersDashboard />} />
          <Route path="/socios/success" element={<PartnersPurchaseSuccess />} />
          
          {/* ========== BUSINESS/ADMIN ROUTES ========== */}
          <Route path="/admin" element={<Login />} />
          <Route path="/admin/forgot-password" element={<ForgotPassword />} />
          <Route path="/registro-negocio" element={<Landing />} />
          
          {/* Legacy route redirect */}
          <Route path="/login" element={<Navigate to="/admin" replace />} />
          <Route path="/forgot-password" element={<Navigate to="/admin/forgot-password" replace />} />
          
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
          
          <Route path="/loyalty-admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><LoyaltyAdmin /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/salespeople" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><SalespeopleAdmin /></Layout>
            </ProtectedRoute>
          } />
          
          <Route path="/partners-admin" element={
            <ProtectedRoute allowedRoles={["admin"]}>
              <Layout><PartnersAdmin /></Layout>
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
