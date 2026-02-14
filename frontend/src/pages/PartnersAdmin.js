import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { toast } from "sonner";
import axios from "axios";
import { 
  Users, TrendingUp, DollarSign, Percent, 
  Loader2, Search, Check, Calendar, FileText,
  CreditCard, Building, AlertCircle
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const PartnersAdmin = () => {
  const { token } = useAuth();
  const [stats, setStats] = useState(null);
  const [partners, setPartners] = useState([]);
  const [pendingReturns, setPendingReturns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [generateMonth, setGenerateMonth] = useState(new Date().getMonth() + 1);
  const [generateYear, setGenerateYear] = useState(new Date().getFullYear());
  const [generating, setGenerating] = useState(false);
  const [paying, setPaying] = useState(false);
  const [newPrice, setNewPrice] = useState("");
  const [updatingPrice, setUpdatingPrice] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, partnersRes, returnsRes] = await Promise.all([
        axios.get(`${API}/api/partners/admin/stats`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/partners/admin/all`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/partners/admin/pending-returns`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setStats(statsRes.data);
      setPartners(partnersRes.data);
      setPendingReturns(returnsRes.data);
    } catch (error) {
      toast.error("Error al cargar datos de socios");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReturns = async () => {
    setGenerating(true);
    try {
      const response = await axios.post(
        `${API}/api/partners/admin/generate-returns?month=${generateMonth}&year=${generateYear}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(response.data.message);
      setShowGenerateDialog(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al generar rendimientos");
    } finally {
      setGenerating(false);
    }
  };

  const handlePayAllReturns = async () => {
    if (!pendingReturns?.returns?.length) return;
    
    setPaying(true);
    try {
      const returnIds = pendingReturns.returns.map(r => r.id);
      const response = await axios.post(
        `${API}/api/partners/admin/pay-returns`,
        returnIds,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(response.data.message);
      fetchData();
    } catch (error) {
      toast.error("Error al pagar rendimientos");
    } finally {
      setPaying(false);
    }
  };

  const handleUpdatePrice = async () => {
    if (!newPrice || parseFloat(newPrice) <= stats?.current_lot_price) {
      toast.error("El nuevo precio debe ser mayor al actual");
      return;
    }
    
    setUpdatingPrice(true);
    try {
      const response = await axios.post(
        `${API}/api/partners/admin/update-price?new_price=${newPrice}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(response.data.message);
      setNewPrice("");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al actualizar precio");
    } finally {
      setUpdatingPrice(false);
    }
  };

  const formatCurrency = (amount) => `$${amount?.toLocaleString() || 0}`;

  const filteredPartners = partners.filter(p =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="partners-admin">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white font-manrope flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-[#708238]" />
            Socios Inversionistas
          </h1>
          <p className="text-[#A1A1AA]">Gestiona las participaciones y rendimientos</p>
        </div>
        <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d]">
              <Calendar className="h-4 w-4 mr-2" />
              Generar Rendimientos
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white">Generar Rendimientos Mensuales</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-[#A1A1AA]">Mes</label>
                  <Input
                    type="number"
                    min={1}
                    max={12}
                    value={generateMonth}
                    onChange={(e) => setGenerateMonth(parseInt(e.target.value))}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
                <div>
                  <label className="text-sm text-[#A1A1AA]">Año</label>
                  <Input
                    type="number"
                    value={generateYear}
                    onChange={(e) => setGenerateYear(parseInt(e.target.value))}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
              </div>
              <p className="text-sm text-[#71717A]">
                Esto generará registros de pago pendiente para todos los socios activos.
              </p>
              <Button
                onClick={handleGenerateReturns}
                disabled={generating}
                className="w-full bg-[#708238] hover:bg-[#5a692d]"
              >
                {generating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Generar para {generateMonth}/{generateYear}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Total Socios</p>
                  <p className="text-2xl font-bold text-white mt-1">{stats.total_partners}</p>
                  <p className="text-xs text-[#71717A]">{stats.active_partners} activos</p>
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
                  <p className="text-sm text-[#A1A1AA]">Inversión Total</p>
                  <p className="text-2xl font-bold text-white mt-1">{formatCurrency(stats.total_investment)}</p>
                  <p className="text-xs text-[#71717A]">{stats.total_lots_sold} lotes</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/20">
                  <DollarSign className="h-5 w-5 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Participación Vendida</p>
                  <p className="text-2xl font-bold text-[#708238] mt-1">{stats.total_participation_percent.toFixed(1)}%</p>
                  <p className="text-xs text-[#71717A]">{stats.available_participation.toFixed(1)}% disponible</p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <Percent className="h-5 w-5 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Rendimientos Pendientes</p>
                  <p className="text-2xl font-bold text-orange-400 mt-1">{formatCurrency(stats.pending_returns)}</p>
                  <p className="text-xs text-green-400">{formatCurrency(stats.paid_returns)} pagados</p>
                </div>
                <div className="p-3 rounded-lg bg-orange-500/20">
                  <CreditCard className="h-5 w-5 text-orange-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Price Update */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex-1">
              <p className="text-[#A1A1AA]">Precio actual por lote:</p>
              <p className="text-2xl font-bold text-[#708238]">{formatCurrency(stats?.current_lot_price)}</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                placeholder="Nuevo precio"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                className="bg-[#0D0D0D] border-[#27272A] text-white w-40"
              />
              <Button
                onClick={handleUpdatePrice}
                disabled={updatingPrice || !newPrice}
                variant="outline"
                className="bg-transparent border-[#708238] text-[#708238] hover:bg-[#708238]/20"
              >
                {updatingPrice ? <Loader2 className="h-4 w-4 animate-spin" /> : "Actualizar"}
              </Button>
            </div>
          </div>
          <p className="text-xs text-[#71717A] mt-2">
            <AlertCircle className="h-3 w-3 inline mr-1" />
            El precio solo puede aumentar (mínimo $5,000). Esto incrementa el valor de las participaciones existentes.
          </p>
        </CardContent>
      </Card>

      <Tabs defaultValue="partners" className="space-y-4">
        <TabsList className="bg-[#161616] border border-[#27272A]">
          <TabsTrigger value="partners" className="data-[state=active]:bg-[#708238]">
            Socios
          </TabsTrigger>
          <TabsTrigger value="pending" className="data-[state=active]:bg-[#708238]">
            Pagos Pendientes
            {pendingReturns?.count > 0 && (
              <Badge className="ml-2 bg-orange-500">{pendingReturns.count}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Partners List */}
        <TabsContent value="partners">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white">Lista de Socios</CardTitle>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    placeholder="Buscar..."
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
                      <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Socio</th>
                      <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Código</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Lotes</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Participación</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Inversión</th>
                      <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Banco</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Pagos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPartners.map((partner) => (
                      <tr key={partner.id} className="border-b border-[#27272A] hover:bg-[#1F1F1F]/50">
                        <td className="py-4 px-4">
                          <div>
                            <p className="text-white font-medium">{partner.name}</p>
                            <p className="text-sm text-[#71717A]">{partner.email}</p>
                          </div>
                        </td>
                        <td className="py-4 px-4">
                          <Badge className="bg-[#708238]/20 text-[#708238] border-[#708238]/50 font-mono">
                            {partner.partner_code}
                          </Badge>
                        </td>
                        <td className="py-4 px-4 text-right text-white font-bold">
                          {partner.total_lots}
                        </td>
                        <td className="py-4 px-4 text-right text-[#708238] font-bold">
                          {partner.participation_percent.toFixed(1)}%
                        </td>
                        <td className="py-4 px-4 text-right text-white">
                          {formatCurrency(partner.total_investment)}
                        </td>
                        <td className="py-4 px-4">
                          <div>
                            <p className="text-white text-sm">{partner.bank_name}</p>
                            <p className="text-xs text-[#71717A] font-mono">****{partner.clabe_last4}</p>
                          </div>
                        </td>
                        <td className="py-4 px-4 text-right">
                          <span className="text-white">{partner.payments_made}</span>
                          <span className="text-[#71717A]">/48</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pending Returns */}
        <TabsContent value="pending">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-white">Rendimientos Pendientes de Pago</CardTitle>
                  <p className="text-sm text-[#A1A1AA] mt-1">
                    Total: <span className="text-orange-400 font-bold">{formatCurrency(pendingReturns?.total_pending)}</span>
                  </p>
                </div>
                {pendingReturns?.returns?.length > 0 && (
                  <Button
                    onClick={handlePayAllReturns}
                    disabled={paying}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {paying ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                    Marcar Todos como Pagados
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {pendingReturns?.returns?.length > 0 ? (
                <div className="space-y-3">
                  {pendingReturns.returns.map((ret) => (
                    <div 
                      key={ret.id}
                      className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A] flex items-center justify-between"
                    >
                      <div>
                        <p className="text-white font-medium">{ret.partner_name}</p>
                        <p className="text-sm text-[#71717A]">
                          Pago #{ret.payment_number} • {ret.month_year} • {ret.lots} lotes
                        </p>
                        <p className="text-xs text-[#71717A] mt-1">
                          <Building className="h-3 w-3 inline mr-1" />
                          {ret.bank_name} - ****{ret.clabe_last4}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-orange-400 font-bold text-lg">{formatCurrency(ret.amount)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center text-[#71717A]">
                  <Check className="h-12 w-12 mx-auto mb-4 text-green-400" />
                  <p>No hay rendimientos pendientes de pago</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PartnersAdmin;
