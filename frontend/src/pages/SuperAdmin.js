import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import axios from "axios";
import { 
  Building2, 
  Users, 
  DollarSign, 
  TrendingUp, 
  Search,
  Crown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  BarChart3,
  RefreshCw,
  LogOut
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const SuperAdmin = () => {
  const navigate = useNavigate();
  const { user, token, logout } = useAuth();
  const [stats, setStats] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (!user || user.role !== "superadmin") {
      navigate("/login");
      return;
    }
    fetchData();
  }, [user, navigate]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, tenantsRes] = await Promise.all([
        axios.get(`${API}/api/admin/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/admin/tenants`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setStats(statsRes.data);
      setTenants(tenantsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/");
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(amount);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getStatusBadge = (status) => {
    const config = {
      trial: { label: "Prueba", className: "bg-yellow-500/20 text-yellow-400" },
      active: { label: "Activo", className: "bg-green-500/20 text-green-400" },
      suspended: { label: "Suspendido", className: "bg-red-500/20 text-red-400" },
      cancelled: { label: "Cancelado", className: "bg-gray-500/20 text-gray-400" }
    };
    const { label, className } = config[status] || config.cancelled;
    return <Badge className={className}>{label}</Badge>;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case "active": return <CheckCircle className="h-4 w-4 text-green-400" />;
      case "trial": return <Clock className="h-4 w-4 text-yellow-400" />;
      case "suspended": return <XCircle className="h-4 w-4 text-red-400" />;
      default: return <AlertTriangle className="h-4 w-4 text-gray-400" />;
    }
  };

  const filteredTenants = tenants.filter(t => 
    t.business_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.owner_email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Header */}
      <header className="border-b border-[#27272A] bg-[#161616] sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-[#708238] to-[#5a692d] flex items-center justify-center">
              <Crown className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white font-manrope">Panel Super Admin</h1>
              <p className="text-xs text-[#71717A]">Casa Dorelia SaaS Management</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={fetchData} className="text-[#A1A1AA] hover:text-white">
              <RefreshCw className="h-4 w-4 mr-2" />
              Actualizar
            </Button>
            <Button variant="ghost" onClick={handleLogout} className="text-[#A1A1AA] hover:text-white">
              <LogOut className="h-4 w-4 mr-2" />
              Salir
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Total Negocios</p>
                  <p className="text-3xl font-bold text-white">{stats?.total_tenants || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <Building2 className="h-6 w-6 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Activos</p>
                  <p className="text-3xl font-bold text-green-400">{stats?.active_tenants || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-green-500/20">
                  <CheckCircle className="h-6 w-6 text-green-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">En Prueba</p>
                  <p className="text-3xl font-bold text-yellow-400">{stats?.trial_tenants || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-yellow-500/20">
                  <Clock className="h-6 w-6 text-yellow-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Ingresos Totales</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(stats?.total_revenue || 0)}</p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <DollarSign className="h-6 w-6 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tenants Table */}
        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-white font-manrope flex items-center gap-2">
                <Building2 className="h-5 w-5 text-[#708238]" />
                Negocios Registrados
              </CardTitle>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-[#71717A]" />
                <Input
                  placeholder="Buscar negocio..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 bg-[#0D0D0D] border-[#27272A] text-white"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="border-[#27272A] hover:bg-transparent">
                  <TableHead className="text-[#A1A1AA]">Negocio</TableHead>
                  <TableHead className="text-[#A1A1AA]">Email</TableHead>
                  <TableHead className="text-[#A1A1AA]">Estado</TableHead>
                  <TableHead className="text-[#A1A1AA]">Plan</TableHead>
                  <TableHead className="text-[#A1A1AA]">Sucursales</TableHead>
                  <TableHead className="text-[#A1A1AA]">Usuarios</TableHead>
                  <TableHead className="text-[#A1A1AA]">Registro</TableHead>
                  <TableHead className="text-[#A1A1AA]">Vence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTenants.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-8 text-[#71717A]">
                      No se encontraron negocios
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredTenants.map((tenant) => (
                    <TableRow key={tenant.id} className="border-[#27272A] hover:bg-[#1a1a1a]">
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(tenant.status)}
                          <span className="text-white font-medium">{tenant.business_name}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-[#A1A1AA]">{tenant.owner_email}</TableCell>
                      <TableCell>{getStatusBadge(tenant.status)}</TableCell>
                      <TableCell className="text-[#A1A1AA]">
                        {tenant.plan_id?.replace("plan_", "") || "1"} sucursal(es)
                      </TableCell>
                      <TableCell>
                        <span className="text-white">{tenant.branch_count || 0}</span>
                        <span className="text-[#71717A]"> / {tenant.max_branches || 1}</span>
                      </TableCell>
                      <TableCell className="text-[#A1A1AA]">{tenant.user_count || 1}</TableCell>
                      <TableCell className="text-[#71717A] text-sm">
                        {formatDate(tenant.created_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {tenant.status === "trial" ? (
                          <span className="text-yellow-400">{formatDate(tenant.trial_ends_at)}</span>
                        ) : tenant.subscription_ends_at ? (
                          <span className="text-[#A1A1AA]">{formatDate(tenant.subscription_ends_at)}</span>
                        ) : (
                          <span className="text-[#71717A]">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <div className="mt-8 grid md:grid-cols-3 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <h3 className="text-white font-semibold mb-2">Estadísticas Rápidas</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#A1A1AA]">Tasa de conversión</span>
                  <span className="text-white">
                    {stats?.total_tenants > 0 
                      ? ((stats?.active_tenants / stats?.total_tenants) * 100).toFixed(1)
                      : 0}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#A1A1AA]">En prueba por convertir</span>
                  <span className="text-yellow-400">{stats?.trial_tenants || 0}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <h3 className="text-white font-semibold mb-2">Acciones</h3>
              <div className="space-y-2">
                <Button variant="outline" className="w-full justify-start bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white" disabled>
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Ver reportes detallados
                </Button>
                <Button variant="outline" className="w-full justify-start bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white" disabled>
                  <Users className="h-4 w-4 mr-2" />
                  Gestionar usuarios
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <h3 className="text-white font-semibold mb-2">Sistema</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#A1A1AA]">Versión</span>
                  <span className="text-[#708238]">1.0.0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#A1A1AA]">Estado</span>
                  <Badge className="bg-green-500/20 text-green-400">Online</Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default SuperAdmin;
