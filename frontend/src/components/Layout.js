import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Badge } from "./ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Coffee,
  Truck,
  FileText,
  Users,
  Store,
  Menu,
  X,
  LogOut,
  User,
  ChevronDown,
  Receipt,
  Wheat,
  BookOpen,
  Boxes,
  MessageCircle,
  AlertTriangle,
  Crown,
  Settings,
  Gift,
  UserCheck,
  TrendingUp,
} from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [alertCount, setAlertCount] = useState(0);
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [tenantInfo, setTenantInfo] = useState(null);
  const { user, logout, isAdmin, canManage, token } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Fetch alert count and subscription status
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [alertsRes, subRes, tenantRes] = await Promise.all([
          axios.get(`${API}/ingredient-inventory/alerts`),
          axios.get(`${API}/tenants/subscription-status`, {
            headers: { Authorization: `Bearer ${token}` }
          }).catch(() => null),
          axios.get(`${API}/tenants/me`, {
            headers: { Authorization: `Bearer ${token}` }
          }).catch(() => null)
        ]);
        
        const criticalAlerts = (alertsRes.data || []).filter(a => a.alert_type === "critical");
        setAlertCount(criticalAlerts.length);
        
        if (subRes?.data) {
          setSubscriptionStatus(subRes.data);
        }
        
        if (tenantRes?.data) {
          setTenantInfo(tenantRes.data);
        }
      } catch (error) {
        console.error("Error fetching data:", error);
      }
    };

    if (token) {
      fetchData();
      const interval = setInterval(fetchData, 60000); // Update every minute
      return () => clearInterval(interval);
    }
  }, [token]);

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const navItems = [
    { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "gerente", "cajero"] },
    { path: "/sales", label: "Ventas", icon: ShoppingCart, roles: ["admin", "gerente", "cajero"] },
    { path: "/inventory", label: "Inv. Productos", icon: Package, roles: ["admin", "gerente", "cajero"] },
    { path: "/ingredient-inventory", label: "Inv. Ingredientes", icon: Boxes, roles: ["admin", "gerente", "cajero"] },
    { path: "/products", label: "Productos", icon: Coffee, roles: ["admin", "gerente"] },
    { path: "/ingredients", label: "Ingredientes", icon: Wheat, roles: ["admin", "gerente"] },
    { path: "/recipes", label: "Recetas", icon: BookOpen, roles: ["admin", "gerente"] },
    { path: "/suppliers", label: "Proveedores", icon: Truck, roles: ["admin", "gerente"] },
    { path: "/purchases", label: "Compras", icon: Receipt, roles: ["admin", "gerente"] },
    { path: "/reports", label: "Reportes", icon: FileText, roles: ["admin", "gerente"] },
    { path: "/loyalty-admin", label: "Programa Lealtad", icon: Gift, roles: ["admin"] },
    { path: "/salespeople", label: "Vendedores", icon: UserCheck, roles: ["admin"] },
    { path: "/cafeterias", label: "Cafeterías", icon: Store, roles: ["admin"] },
    { path: "/users", label: "Usuarios", icon: Users, roles: ["admin"] },
    { path: "/whatsapp-alerts", label: "Alertas WhatsApp", icon: MessageCircle, roles: ["admin"] },
    { path: "/business-settings", label: "Mi Negocio", icon: Settings, roles: ["admin"] },
  ];

  const filteredNavItems = navItems.filter(item => item.roles.includes(user?.role));

  const NavLink = ({ item, mobile = false, alertCount = 0 }) => {
    const isActive = location.pathname === item.path;
    const Icon = item.icon;
    const showBadge = item.path === "/ingredient-inventory" && alertCount > 0;
    
    return (
      <Link
        to={item.path}
        onClick={() => mobile && setSidebarOpen(false)}
        data-testid={`nav-${item.path.slice(1)}`}
        className={`
          flex items-center gap-3 px-4 py-3 rounded-md transition-all duration-200 relative
          ${isActive 
            ? "bg-[#708238]/20 text-[#708238] border-l-3 border-[#708238]" 
            : "text-[#A1A1AA] hover:bg-[#708238]/10 hover:text-white hover:pl-5"
          }
        `}
      >
        <div className="relative">
          <Icon className="h-5 w-5" />
          {showBadge && (
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
          )}
        </div>
        <span className="font-medium flex-1">{item.label}</span>
        {showBadge && (
          <Badge className="bg-red-500 text-white text-xs px-1.5 py-0.5 h-5 min-w-[20px] flex items-center justify-center">
            {alertCount}
          </Badge>
        )}
      </Link>
    );
  };

  const roleLabels = {
    admin: "Administrador",
    gerente: "Gerente",
    cajero: "Cajero"
  };

  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Mobile Header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-50 glass border-b border-[#27272A]">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <img 
              src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
              alt="Doré" 
              className="h-8 w-auto"
            />
            <span className="font-manrope font-bold text-white">Doré</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            data-testid="mobile-menu-toggle"
            className="text-white hover:bg-[#27272A]"
          >
            {sidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </Button>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 z-50 h-full w-64 bg-[#161616] border-r border-[#27272A]
        transform transition-transform duration-300 ease-in-out
        lg:transform-none lg:translate-x-0
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-[#27272A]">
            {tenantInfo?.logo_url ? (
              <img 
                src={`${process.env.REACT_APP_BACKEND_URL}${tenantInfo.logo_url}`}
                alt={tenantInfo.business_name} 
                className="h-10 w-10 object-contain"
              />
            ) : (
              <img 
                src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
                alt="Doré" 
                className="h-10 w-auto"
              />
            )}
            <div>
              <h1 className="font-manrope font-bold text-xl text-white">
                {tenantInfo?.business_name || "Doré"}
              </h1>
              <p className="text-xs text-[#71717A]">Sistema de Gestión</p>
            </div>
          </div>

          {/* Navigation */}
          <ScrollArea className="flex-1 py-4">
            {/* Subscription Banner */}
            {subscriptionStatus && (subscriptionStatus.is_trial || subscriptionStatus.status === "suspended") && (
              <div className="mx-3 mb-3 p-3 rounded-lg bg-gradient-to-r from-[#708238]/20 to-[#D97706]/20 border border-[#708238]/30">
                <div className="flex items-center gap-2 mb-2">
                  <Crown className="h-4 w-4 text-[#708238]" />
                  <span className="text-xs font-medium text-white">
                    {subscriptionStatus.status === "suspended" ? "Período expirado" : `${subscriptionStatus.trial_days_left} días de prueba`}
                  </span>
                </div>
                <Link to="/subscription">
                  <Button size="sm" className="w-full bg-[#708238] hover:bg-[#5a692d] text-white text-xs h-7">
                    {subscriptionStatus.status === "suspended" ? "Suscribirse" : "Ver planes"}
                  </Button>
                </Link>
              </div>
            )}
            
            <nav className="px-3 space-y-1">
              {filteredNavItems.map((item) => (
                <NavLink key={item.path} item={item} mobile={sidebarOpen} alertCount={alertCount} />
              ))}
            </nav>
          </ScrollArea>

          {/* User Section */}
          <div className="border-t border-[#27272A] p-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  data-testid="user-menu-trigger"
                  className="w-full justify-between text-left hover:bg-[#27272A] p-3 h-auto"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-[#708238]/20 flex items-center justify-center">
                      <User className="h-5 w-5 text-[#708238]" />
                    </div>
                    <div className="flex flex-col items-start">
                      <span className="text-sm font-medium text-white truncate max-w-[120px]">
                        {user?.name}
                      </span>
                      <span className="text-xs text-[#71717A]">
                        {roleLabels[user?.role]}
                      </span>
                    </div>
                  </div>
                  <ChevronDown className="h-4 w-4 text-[#71717A]" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent 
                align="end" 
                className="w-56 bg-[#161616] border-[#27272A]"
              >
                <DropdownMenuLabel className="text-[#A1A1AA]">Mi Cuenta</DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-[#27272A]" />
                <DropdownMenuItem 
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="text-red-400 focus:text-red-400 focus:bg-red-400/10 cursor-pointer"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Cerrar Sesión
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:ml-64 min-h-screen pt-16 lg:pt-0">
        <div className="p-6 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
