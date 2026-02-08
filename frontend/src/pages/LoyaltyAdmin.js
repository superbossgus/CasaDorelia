import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { 
  Users, Gift, TrendingUp, Star, Crown, Coffee, 
  Search, Loader2, Award, Ticket, QrCode, Calendar
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const LEVEL_CONFIG = {
  bronce: { icon: Coffee, color: "text-amber-600", bg: "bg-amber-600/20" },
  plata: { icon: Star, color: "text-slate-300", bg: "bg-slate-300/20" },
  oro: { icon: Crown, color: "text-yellow-400", bg: "bg-yellow-400/20" }
};

const LoyaltyAdmin = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [rewards, setRewards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [couponCode, setCouponCode] = useState("");
  const [validatingCoupon, setValidatingCoupon] = useState(false);
  const [validatedCoupon, setValidatedCoupon] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, customersRes, rewardsRes] = await Promise.all([
        axios.get(`${API}/api/loyalty/admin/stats`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/api/loyalty/admin/customers`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/api/loyalty/admin/rewards`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      setStats(statsRes.data);
      setCustomers(customersRes.data);
      setRewards(rewardsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos del programa de lealtad");
    } finally {
      setLoading(false);
    }
  };

  const handleValidateCoupon = async () => {
    if (!couponCode.trim()) {
      toast.error("Ingresa un código de cupón");
      return;
    }

    setValidatingCoupon(true);
    setValidatedCoupon(null);

    try {
      const response = await axios.post(
        `${API}/api/loyalty/validate-coupon?coupon_code=${couponCode}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setValidatedCoupon(response.data);
      toast.success("Cupón válido");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Cupón no válido");
    } finally {
      setValidatingCoupon(false);
    }
  };

  const handleUseCoupon = async (saleId) => {
    try {
      await axios.post(
        `${API}/api/loyalty/use-coupon?coupon_code=${couponCode}&sale_id=${saleId}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success("Cupón aplicado exitosamente");
      setValidatedCoupon(null);
      setCouponCode("");
    } catch (error) {
      toast.error("Error al aplicar el cupón");
    }
  };

  const handleProcessBirthdays = async () => {
    try {
      const response = await axios.post(
        `${API}/api/loyalty/admin/process-birthdays`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`${response.data.rewards_sent} recompensas de cumpleaños enviadas`);
    } catch (error) {
      toast.error("Error al procesar cumpleaños");
    }
  };

  const filteredCustomers = customers.filter(c => 
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="loyalty-admin">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white font-manrope flex items-center gap-2">
            <Gift className="h-6 w-6 text-[#708238]" />
            Programa de Lealtad
          </h1>
          <p className="text-[#A1A1AA]">Gestiona tu programa de recompensas</p>
        </div>
        <Button
          onClick={handleProcessBirthdays}
          variant="outline"
          className="bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
        >
          <Calendar className="h-4 w-4 mr-2" />
          Procesar Cumpleaños
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Clientes Registrados</p>
                  <p className="text-2xl font-bold text-white mt-1">{stats.total_customers}</p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <Users className="h-5 w-5 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Puntos Emitidos</p>
                  <p className="text-2xl font-bold text-white mt-1">{stats.total_points_issued.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/20">
                  <Star className="h-5 w-5 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Puntos Canjeados</p>
                  <p className="text-2xl font-bold text-white mt-1">{stats.points_redeemed.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-lg bg-orange-500/20">
                  <Ticket className="h-5 w-5 text-orange-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Clientes Oro</p>
                  <p className="text-2xl font-bold text-yellow-400 mt-1">{stats.customers_by_level?.oro || 0}</p>
                </div>
                <div className="p-3 rounded-lg bg-yellow-400/20">
                  <Crown className="h-5 w-5 text-yellow-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Coupon Validation */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <QrCode className="h-5 w-5 text-[#708238]" />
            Validar Cupón
          </CardTitle>
          <CardDescription className="text-[#A1A1AA]">
            Ingresa el código del cupón del cliente para aplicar el descuento
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Input
              placeholder="Código del cupón (ej: DORE-ABC123)"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
              className="bg-[#0D0D0D] border-[#27272A] text-white font-mono"
            />
            <Button
              onClick={handleValidateCoupon}
              disabled={validatingCoupon}
              className="bg-[#708238] hover:bg-[#5a692d]"
            >
              {validatingCoupon ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Validar"
              )}
            </Button>
          </div>

          {validatedCoupon && (
            <div className="mt-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-400 font-bold">✓ Cupón Válido</p>
                  <p className="text-white">{validatedCoupon.coupon.reward_name}</p>
                  <p className="text-sm text-[#A1A1AA]">Cliente: {validatedCoupon.customer_name}</p>
                  <p className="text-[#708238] font-bold mt-1">
                    {validatedCoupon.discount_percent}% de descuento
                    {validatedCoupon.max_discount && ` (máx $${validatedCoupon.max_discount})`}
                  </p>
                </div>
                <Button
                  onClick={() => handleUseCoupon("manual-" + Date.now())}
                  className="bg-green-600 hover:bg-green-700"
                >
                  Aplicar
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Customers by Level */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(stats.customers_by_level || {}).map(([level, count]) => {
            const config = LEVEL_CONFIG[level];
            const Icon = config?.icon || Star;
            return (
              <Card key={level} className={`bg-[#161616] border-[#27272A] ${config?.bg}`}>
                <CardContent className="p-4 flex items-center gap-3">
                  <Icon className={`h-8 w-8 ${config?.color}`} />
                  <div>
                    <p className="text-2xl font-bold text-white">{count}</p>
                    <p className={`text-sm ${config?.color} capitalize`}>{level}</p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Customers Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <CardTitle className="text-white font-manrope flex items-center gap-2">
              <Users className="h-5 w-5 text-[#708238]" />
              Clientes del Programa
            </CardTitle>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
              <Input
                placeholder="Buscar cliente..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-[#0D0D0D] border-[#27272A] text-white pl-10 w-64"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#27272A]">
                  <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Cliente</th>
                  <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Nivel</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Puntos</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Puntos Históricos</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Visitas/Mes</th>
                  <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Registro</th>
                </tr>
              </thead>
              <tbody>
                {filteredCustomers.map((customer) => {
                  const config = LEVEL_CONFIG[customer.current_level];
                  const Icon = config?.icon || Coffee;
                  return (
                    <tr key={customer.id} className="border-b border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <td className="py-4 px-4">
                        <div>
                          <p className="text-white font-medium">{customer.name}</p>
                          <p className="text-sm text-[#71717A]">{customer.email}</p>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <Badge className={`${config?.bg} ${config?.color} border-none`}>
                          <Icon className="h-3 w-3 mr-1" />
                          {customer.current_level}
                        </Badge>
                      </td>
                      <td className="py-4 px-4 text-right text-[#708238] font-bold">
                        {customer.total_points.toLocaleString()}
                      </td>
                      <td className="py-4 px-4 text-right text-white">
                        {customer.lifetime_points.toLocaleString()}
                      </td>
                      <td className="py-4 px-4 text-right text-[#A1A1AA]">
                        {customer.visits_this_month}
                      </td>
                      <td className="py-4 px-4 text-[#71717A] text-sm">
                        {new Date(customer.created_at).toLocaleDateString("es-MX")}
                      </td>
                    </tr>
                  );
                })}
                {filteredCustomers.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#71717A]">
                      No se encontraron clientes
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Rewards Catalog */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Award className="h-5 w-5 text-[#708238]" />
            Catálogo de Recompensas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {rewards.map((reward) => (
              <div 
                key={reward.id} 
                className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A]"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-bold">{reward.name}</span>
                  {reward.is_default && (
                    <Badge variant="outline" className="text-[#71717A] border-[#71717A]">
                      Por defecto
                    </Badge>
                  )}
                </div>
                <p className="text-[#708238] font-bold">{reward.points_required} puntos</p>
                <p className="text-sm text-[#A1A1AA]">
                  {reward.discount_percent}% descuento
                  {reward.max_discount && ` (máx $${reward.max_discount})`}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LoyaltyAdmin;
