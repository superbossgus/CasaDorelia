import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";
import {
  Ticket, Plus, Trash2, Loader2, Search,
  Percent, DollarSign, TrendingUp, Calendar,
  CheckCircle2, XCircle, BarChart3, FileText
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const CouponsAdmin = () => {
  const [loading, setLoading] = useState(true);
  const [coupons, setCoupons] = useState([]);
  const [report, setReport] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeTab, setActiveTab] = useState("coupons"); // "coupons" or "report"
  const [searchTerm, setSearchTerm] = useState("");
  
  const [newCoupon, setNewCoupon] = useState({
    code: "",
    discount_type: "percent",
    discount_value: "",
    valid_for: "both",
    max_uses: "",
    expires_at: "",
    description: ""
  });

  const token = localStorage.getItem("token");

  useEffect(() => {
    fetchCoupons();
    fetchReport();
  }, []);

  const fetchCoupons = async () => {
    try {
      const response = await axios.get(`${API}/api/coupons`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCoupons(response.data);
    } catch (error) {
      toast.error("Error al cargar cupones");
    } finally {
      setLoading(false);
    }
  };

  const fetchReport = async () => {
    try {
      const response = await axios.get(`${API}/api/coupons/report`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setReport(response.data);
    } catch (error) {
      console.error("Error fetching report:", error);
    }
  };

  const handleCreateCoupon = async (e) => {
    e.preventDefault();
    
    if (!newCoupon.code || !newCoupon.discount_value) {
      toast.error("Completa los campos requeridos");
      return;
    }

    setCreating(true);
    try {
      await axios.post(`${API}/api/coupons`, {
        code: newCoupon.code.toUpperCase(),
        discount_type: newCoupon.discount_type,
        discount_value: parseFloat(newCoupon.discount_value),
        valid_for: newCoupon.valid_for,
        max_uses: newCoupon.max_uses ? parseInt(newCoupon.max_uses) : null,
        expires_at: newCoupon.expires_at || null,
        description: newCoupon.description || null
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success("Cupón creado exitosamente");
      setShowCreateModal(false);
      setNewCoupon({
        code: "",
        discount_type: "percent",
        discount_value: "",
        valid_for: "both",
        max_uses: "",
        expires_at: "",
        description: ""
      });
      fetchCoupons();
      fetchReport();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al crear cupón");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleCoupon = async (couponId, currentStatus) => {
    try {
      await axios.put(`${API}/api/coupons/${couponId}?is_active=${!currentStatus}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(currentStatus ? "Cupón desactivado" : "Cupón activado");
      fetchCoupons();
    } catch (error) {
      toast.error("Error al actualizar cupón");
    }
  };

  const handleDeleteCoupon = async (couponId) => {
    if (!window.confirm("¿Estás seguro de eliminar este cupón?")) return;

    try {
      await axios.delete(`${API}/api/coupons/${couponId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Cupón eliminado");
      fetchCoupons();
      fetchReport();
    } catch (error) {
      toast.error("Error al eliminar cupón");
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "Sin expiración";
    return new Date(dateStr).toLocaleDateString("es-MX");
  };

  const filteredCoupons = coupons.filter(c => 
    c.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.description && c.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Ticket className="h-6 w-6 text-[#708238]" />
            Cupones de Descuento
          </h1>
          <p className="text-[#A1A1AA]">Gestiona cupones para suscripciones e inversiones</p>
        </div>
        <Button
          onClick={() => setShowCreateModal(true)}
          className="bg-[#708238] hover:bg-[#5a692d]"
        >
          <Plus className="h-4 w-4 mr-2" />
          Crear Cupón
        </Button>
      </div>

      {/* Summary Cards */}
      {report && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Ticket className="h-5 w-5 text-[#708238]" />
                <span className="text-sm text-[#A1A1AA]">Total Cupones</span>
              </div>
              <p className="text-2xl font-bold text-white">{report.summary.total_coupons}</p>
              <p className="text-xs text-[#708238]">{report.summary.active_coupons} activos</p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="h-5 w-5 text-[#708238]" />
                <span className="text-sm text-[#A1A1AA]">Total Usos</span>
              </div>
              <p className="text-2xl font-bold text-white">{report.summary.total_uses}</p>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-[#708238]/20 to-transparent border-[#708238]/30">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="h-5 w-5 text-[#708238]" />
                <span className="text-sm text-[#A1A1AA]">Descuento Total</span>
              </div>
              <p className="text-2xl font-bold text-white">{formatCurrency(report.summary.total_discount_given)}</p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="h-5 w-5 text-[#708238]" />
                <span className="text-sm text-[#A1A1AA]">Promedio/Uso</span>
              </div>
              <p className="text-2xl font-bold text-white">
                {report.summary.total_uses > 0 
                  ? formatCurrency(report.summary.total_discount_given / report.summary.total_uses)
                  : "$0"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[#27272A]">
        <button
          onClick={() => setActiveTab("coupons")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-[1px] transition-colors ${
            activeTab === "coupons"
              ? "border-[#708238] text-white"
              : "border-transparent text-[#A1A1AA] hover:text-white"
          }`}
        >
          <Ticket className="h-4 w-4 inline mr-2" />
          Cupones
        </button>
        <button
          onClick={() => setActiveTab("report")}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-[1px] transition-colors ${
            activeTab === "report"
              ? "border-[#708238] text-white"
              : "border-transparent text-[#A1A1AA] hover:text-white"
          }`}
        >
          <BarChart3 className="h-4 w-4 inline mr-2" />
          Reporte de Uso
        </button>
      </div>

      {/* Tab: Coupons List */}
      {activeTab === "coupons" && (
        <>
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
            <Input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar cupones..."
              className="bg-[#161616] border-[#27272A] text-white pl-10"
            />
          </div>

          {/* Coupons Table */}
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-0">
              {filteredCoupons.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[#27272A]">
                        <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Código</th>
                        <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Descuento</th>
                        <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Válido Para</th>
                        <th className="py-3 px-4 text-center text-[#A1A1AA] text-sm">Usos</th>
                        <th className="py-3 px-4 text-right text-[#A1A1AA] text-sm">Total Descontado</th>
                        <th className="py-3 px-4 text-center text-[#A1A1AA] text-sm">Estado</th>
                        <th className="py-3 px-4 text-center text-[#A1A1AA] text-sm">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCoupons.map((coupon) => (
                        <tr key={coupon.id} className="border-b border-[#27272A]/50 hover:bg-[#1F1F1F]/50">
                          <td className="py-3 px-4">
                            <div>
                              <p className="text-white font-mono font-bold">{coupon.code}</p>
                              {coupon.description && (
                                <p className="text-xs text-[#71717A]">{coupon.description}</p>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <Badge className={coupon.discount_type === "percent" 
                              ? "bg-purple-500/20 text-purple-400" 
                              : "bg-green-500/20 text-green-400"
                            }>
                              {coupon.discount_type === "percent" 
                                ? `${coupon.discount_value}%` 
                                : formatCurrency(coupon.discount_value)}
                            </Badge>
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant="outline" className="border-[#27272A] text-[#A1A1AA]">
                              {coupon.valid_for === "both" ? "Todo" 
                                : coupon.valid_for === "subscription" ? "Suscripción" 
                                : "Inversión"}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className="text-white">{coupon.uses_count}</span>
                            {coupon.max_uses && (
                              <span className="text-[#71717A]">/{coupon.max_uses}</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right text-[#708238] font-medium">
                            {formatCurrency(coupon.total_discount_given)}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <Switch
                              checked={coupon.is_active}
                              onCheckedChange={() => handleToggleCoupon(coupon.id, coupon.is_active)}
                            />
                          </td>
                          <td className="py-3 px-4 text-center">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteCoupon(coupon.id)}
                              className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Ticket className="h-12 w-12 text-[#52525B] mx-auto mb-4" />
                  <p className="text-[#A1A1AA]">No hay cupones creados</p>
                  <Button
                    onClick={() => setShowCreateModal(true)}
                    variant="outline"
                    className="mt-4 border-[#27272A] text-white"
                  >
                    Crear primer cupón
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* Tab: Usage Report */}
      {activeTab === "report" && report && (
        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <FileText className="h-5 w-5 text-[#708238]" />
              Historial de Uso de Cupones
            </CardTitle>
          </CardHeader>
          <CardContent>
            {report.recent_usages && report.recent_usages.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#27272A]">
                      <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Fecha</th>
                      <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Cupón</th>
                      <th className="py-3 px-4 text-left text-[#A1A1AA] text-sm">Tipo</th>
                      <th className="py-3 px-4 text-right text-[#A1A1AA] text-sm">Monto Original</th>
                      <th className="py-3 px-4 text-right text-[#A1A1AA] text-sm">Descuento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.recent_usages.map((usage) => {
                      const coupon = report.coupons.find(c => c.id === usage.coupon_id);
                      return (
                        <tr key={usage.id} className="border-b border-[#27272A]/50">
                          <td className="py-3 px-4 text-[#A1A1AA]">
                            {new Date(usage.used_at).toLocaleDateString("es-MX")}
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-white font-mono">{coupon?.code || "N/A"}</span>
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant="outline" className={
                              usage.used_for === "investment" 
                                ? "border-[#708238] text-[#708238]" 
                                : "border-purple-500 text-purple-400"
                            }>
                              {usage.used_for === "investment" ? "Inversión" : "Suscripción"}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-right text-white">
                            {formatCurrency(usage.original_amount)}
                          </td>
                          <td className="py-3 px-4 text-right text-[#708238] font-medium">
                            -{formatCurrency(usage.discount_amount)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12">
                <BarChart3 className="h-12 w-12 text-[#52525B] mx-auto mb-4" />
                <p className="text-[#A1A1AA]">No hay registros de uso</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Create Coupon Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-[#161616] rounded-xl border border-[#27272A] w-full max-w-md">
            <div className="p-6">
              <h2 className="text-xl font-bold text-white mb-6">Crear Nuevo Cupón</h2>
              
              <form onSubmit={handleCreateCoupon} className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Código del Cupón *</Label>
                  <Input
                    value={newCoupon.code}
                    onChange={(e) => setNewCoupon({...newCoupon, code: e.target.value.toUpperCase()})}
                    placeholder="Ej: DESCUENTO10"
                    className="bg-[#0D0D0D] border-[#27272A] text-white font-mono uppercase"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Tipo de Descuento *</Label>
                    <Select 
                      value={newCoupon.discount_type}
                      onValueChange={(v) => setNewCoupon({...newCoupon, discount_type: v})}
                    >
                      <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A]">
                        <SelectItem value="percent" className="text-white">Porcentaje (%)</SelectItem>
                        <SelectItem value="fixed" className="text-white">Monto Fijo ($)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">
                      {newCoupon.discount_type === "percent" ? "Porcentaje *" : "Monto (MXN) *"}
                    </Label>
                    <div className="relative">
                      {newCoupon.discount_type === "percent" ? (
                        <Percent className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      ) : (
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      )}
                      <Input
                        type="number"
                        value={newCoupon.discount_value}
                        onChange={(e) => setNewCoupon({...newCoupon, discount_value: e.target.value})}
                        placeholder={newCoupon.discount_type === "percent" ? "10" : "500"}
                        min="0"
                        max={newCoupon.discount_type === "percent" ? "100" : undefined}
                        className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Válido Para *</Label>
                  <Select 
                    value={newCoupon.valid_for}
                    onValueChange={(v) => setNewCoupon({...newCoupon, valid_for: v})}
                  >
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      <SelectItem value="both" className="text-white">Todo (Suscripción + Inversión)</SelectItem>
                      <SelectItem value="subscription" className="text-white">Solo Suscripciones</SelectItem>
                      <SelectItem value="investment" className="text-white">Solo Inversiones (Lotes)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Máximo de Usos</Label>
                    <Input
                      type="number"
                      value={newCoupon.max_uses}
                      onChange={(e) => setNewCoupon({...newCoupon, max_uses: e.target.value})}
                      placeholder="Ilimitado"
                      min="1"
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Fecha de Expiración</Label>
                    <Input
                      type="date"
                      value={newCoupon.expires_at}
                      onChange={(e) => setNewCoupon({...newCoupon, expires_at: e.target.value})}
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Descripción (opcional)</Label>
                  <Input
                    value={newCoupon.description}
                    onChange={(e) => setNewCoupon({...newCoupon, description: e.target.value})}
                    placeholder="Ej: Cupón de bienvenida"
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 border-[#27272A] text-white"
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    disabled={creating}
                    className="flex-1 bg-[#708238] hover:bg-[#5a692d]"
                  >
                    {creating ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Creando...
                      </>
                    ) : (
                      <>
                        <Plus className="h-4 w-4 mr-2" />
                        Crear Cupón
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CouponsAdmin;
