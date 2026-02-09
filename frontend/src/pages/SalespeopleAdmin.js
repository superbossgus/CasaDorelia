import { useState, useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { 
  Users, Plus, QrCode, Share2, DollarSign, TrendingUp,
  Loader2, Search, Download, Check, Copy, Mail, Phone,
  FileText, Calendar, Filter
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const SalespeopleAdmin = () => {
  const { token } = useAuth();
  const [salespeople, setSalespeople] = useState([]);
  const [report, setReport] = useState(null);
  const [commissions, setCommissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showQRDialog, setShowQRDialog] = useState(false);
  const [selectedSalesperson, setSelectedSalesperson] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterMonth, setFilterMonth] = useState("");
  const [filterYear, setFilterYear] = useState(new Date().getFullYear().toString());
  const [formData, setFormData] = useState({ name: "", email: "", phone: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const [paying, setPaying] = useState(null);
  const qrRef = useRef(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [spRes, reportRes, commRes] = await Promise.all([
        axios.get(`${API}/api/salespeople`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/salespeople/commissions/report`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/api/salespeople/commissions/all?status=pending`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setSalespeople(spRes.data);
      setReport(reportRes.data);
      setCommissions(commRes.data);
    } catch (error) {
      toast.error("Error al cargar datos");
    } finally {
      setLoading(false);
    }
  };

  const handleAddSalesperson = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/salespeople`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Vendedor creado exitosamente");
      setSalespeople([...salespeople, response.data]);
      setShowAddDialog(false);
      setFormData({ name: "", email: "", phone: "", notes: "" });
      setSelectedSalesperson(response.data);
      setShowQRDialog(true);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al crear vendedor");
    } finally {
      setSaving(false);
    }
  };

  const handlePayCommissions = async (salespersonId) => {
    setPaying(salespersonId);
    try {
      const response = await axios.post(
        `${API}/api/salespeople/commissions/pay?salesperson_id=${salespersonId}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Pagado: $${response.data.total_paid.toFixed(2)}`);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al pagar");
    } finally {
      setPaying(null);
    }
  };

  const handleShowQR = (salesperson) => {
    setSelectedSalesperson(salesperson);
    setShowQRDialog(true);
  };

  const handleCopyCode = (code) => {
    // Fallback method for copying text
    const fallbackCopy = (text) => {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-9999px";
      textArea.style.top = "-9999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand("copy");
        toast.success("Código copiado");
      } catch (err) {
        toast.error("No se pudo copiar, copia manualmente: " + text);
      }
      document.body.removeChild(textArea);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code)
        .then(() => toast.success("Código copiado"))
        .catch(() => fallbackCopy(code));
    } else {
      fallbackCopy(code);
    }
  };

  const handleDownloadQR = () => {
    if (qrRef.current) {
      const svg = qrRef.current.querySelector("svg");
      const svgData = new XMLSerializer().serializeToString(svg);
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.onload = () => {
        canvas.width = 400;
        canvas.height = 500;
        ctx.fillStyle = "#0D0D0D";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 50, 50, 300, 300);
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "bold 24px Arial";
        ctx.textAlign = "center";
        ctx.fillText(selectedSalesperson?.name || "", 200, 400);
        ctx.fillStyle = "#708238";
        ctx.font = "18px Arial";
        ctx.fillText(`Código: ${selectedSalesperson?.share_code}`, 200, 440);
        ctx.fillText("10% de descuento", 200, 470);
        
        const link = document.createElement("a");
        link.download = `QR-${selectedSalesperson?.name?.replace(/\s/g, "_")}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
      };
      img.src = "data:image/svg+xml;base64," + btoa(svgData);
    }
  };

  const handleShare = async () => {
    const shareData = {
      title: "Descuento Le Pain Doré",
      text: `¡Usa mi código ${selectedSalesperson?.share_code} para obtener 10% de descuento en Le Pain Doré!`,
      url: window.location.origin
    };
    
    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch (err) {
        handleCopyCode(selectedSalesperson?.share_code);
      }
    } else {
      handleCopyCode(selectedSalesperson?.share_code);
    }
  };

  const filteredSalespeople = salespeople.filter(sp =>
    sp.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    sp.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const formatCurrency = (amount) => `$${amount.toFixed(2)}`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="salespeople-admin">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white font-manrope flex items-center gap-2">
            <Users className="h-6 w-6 text-[#708238]" />
            Vendedores y Comisiones
          </h1>
          <p className="text-[#A1A1AA]">Gestiona tus vendedores afiliados y sus comisiones</p>
        </div>
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d]">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Vendedor
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white">Agregar Vendedor</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAddSalesperson} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre completo *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Juan Pérez"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Email *</Label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="vendedor@email.com"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Teléfono</Label>
                <Input
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="+52 55 1234 5678"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Notas</Label>
                <Input
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Notas adicionales..."
                />
              </div>
              <Button
                type="submit"
                disabled={saving}
                className="w-full bg-[#708238] hover:bg-[#5a692d]"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Crear y Generar QR
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      {report && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Vendedores Activos</p>
                  <p className="text-2xl font-bold text-white mt-1">{salespeople.filter(s => s.is_active).length}</p>
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
                  <p className="text-sm text-[#A1A1AA]">Ventas Totales</p>
                  <p className="text-2xl font-bold text-white mt-1">{formatCurrency(report.totals.total_sales)}</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/20">
                  <TrendingUp className="h-5 w-5 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Comisiones Pendientes</p>
                  <p className="text-2xl font-bold text-orange-400 mt-1">{formatCurrency(report.totals.pending_commission)}</p>
                </div>
                <div className="p-3 rounded-lg bg-orange-500/20">
                  <DollarSign className="h-5 w-5 text-orange-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Comisiones Pagadas</p>
                  <p className="text-2xl font-bold text-green-400 mt-1">{formatCurrency(report.totals.paid_commission)}</p>
                </div>
                <div className="p-3 rounded-lg bg-green-500/20">
                  <Check className="h-5 w-5 text-green-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="salespeople" className="space-y-4">
        <TabsList className="bg-[#161616] border border-[#27272A]">
          <TabsTrigger value="salespeople" className="data-[state=active]:bg-[#708238]">
            Vendedores
          </TabsTrigger>
          <TabsTrigger value="commissions" className="data-[state=active]:bg-[#708238]">
            Comisiones Pendientes
          </TabsTrigger>
          <TabsTrigger value="report" className="data-[state=active]:bg-[#708238]">
            Reporte
          </TabsTrigger>
        </TabsList>

        {/* Salespeople Tab */}
        <TabsContent value="salespeople">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white">Lista de Vendedores</CardTitle>
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
                      <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Vendedor</th>
                      <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Código</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Ventas</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Comisión Total</th>
                      <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Pendiente</th>
                      <th className="text-center py-3 px-4 text-[#A1A1AA] text-xs uppercase">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSalespeople.map((sp) => (
                      <tr key={sp.id} className="border-b border-[#27272A] hover:bg-[#1F1F1F]/50">
                        <td className="py-4 px-4">
                          <div>
                            <p className="text-white font-medium">{sp.name}</p>
                            <div className="flex items-center gap-3 text-sm text-[#71717A]">
                              <span className="flex items-center gap-1">
                                <Mail className="h-3 w-3" />
                                {sp.email}
                              </span>
                              {sp.phone && (
                                <span className="flex items-center gap-1">
                                  <Phone className="h-3 w-3" />
                                  {sp.phone}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-4 px-4">
                          <Badge 
                            className="bg-[#708238]/20 text-[#708238] border-[#708238]/50 font-mono cursor-pointer"
                            onClick={() => handleCopyCode(sp.share_code)}
                          >
                            {sp.share_code}
                            <Copy className="h-3 w-3 ml-1" />
                          </Badge>
                        </td>
                        <td className="py-4 px-4 text-right text-white">
                          {formatCurrency(sp.total_sales)}
                        </td>
                        <td className="py-4 px-4 text-right text-[#708238] font-bold">
                          {formatCurrency(sp.total_commission)}
                        </td>
                        <td className="py-4 px-4 text-right">
                          {sp.pending_commission > 0 ? (
                            <span className="text-orange-400 font-bold">
                              {formatCurrency(sp.pending_commission)}
                            </span>
                          ) : (
                            <span className="text-[#71717A]">$0.00</span>
                          )}
                        </td>
                        <td className="py-4 px-4">
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleShowQR(sp)}
                              className="bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
                            >
                              <QrCode className="h-4 w-4" />
                            </Button>
                            {sp.pending_commission > 0 && (
                              <Button
                                size="sm"
                                onClick={() => handlePayCommissions(sp.id)}
                                disabled={paying === sp.id}
                                className="bg-green-600 hover:bg-green-700"
                              >
                                {paying === sp.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <>Pagar</>
                                )}
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {filteredSalespeople.length === 0 && (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-[#71717A]">
                          No hay vendedores registrados
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Commissions Tab */}
        <TabsContent value="commissions">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <CardTitle className="text-white">Comisiones Pendientes de Pago</CardTitle>
            </CardHeader>
            <CardContent>
              {commissions.length > 0 ? (
                <div className="space-y-3">
                  {commissions.map((c) => (
                    <div key={c.id} className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A] flex items-center justify-between">
                      <div>
                        <p className="text-white font-medium">{c.salesperson_name}</p>
                        <p className="text-sm text-[#71717A]">
                          Venta: {formatCurrency(c.sale_total)} • {new Date(c.created_at).toLocaleDateString("es-MX")}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-orange-400 font-bold">{formatCurrency(c.commission_amount)}</p>
                        <p className="text-xs text-[#71717A]">Comisión (10%)</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center text-[#71717A]">
                  No hay comisiones pendientes
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Report Tab */}
        <TabsContent value="report">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <CardTitle className="text-white flex items-center gap-2">
                  <FileText className="h-5 w-5 text-[#708238]" />
                  Reporte de Comisiones
                </CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              {report && (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-[#27272A]">
                        <th className="text-left py-3 px-4 text-[#A1A1AA] text-xs uppercase">Vendedor</th>
                        <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase"># Ventas</th>
                        <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Total Ventas</th>
                        <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Comisión Total</th>
                        <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Pendiente</th>
                        <th className="text-right py-3 px-4 text-[#A1A1AA] text-xs uppercase">Pagado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.report.map((r) => (
                        <tr key={r.salesperson_id} className="border-b border-[#27272A]">
                          <td className="py-4 px-4 text-white">{r.salesperson_name}</td>
                          <td className="py-4 px-4 text-right text-[#A1A1AA]">{r.sales_count}</td>
                          <td className="py-4 px-4 text-right text-white">{formatCurrency(r.total_sales)}</td>
                          <td className="py-4 px-4 text-right text-[#708238] font-bold">{formatCurrency(r.total_commission)}</td>
                          <td className="py-4 px-4 text-right text-orange-400">{formatCurrency(r.pending_commission)}</td>
                          <td className="py-4 px-4 text-right text-green-400">{formatCurrency(r.paid_commission)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t-2 border-[#27272A] bg-[#0D0D0D]">
                        <td className="py-4 px-4 text-white font-bold">TOTAL</td>
                        <td className="py-4 px-4 text-right text-white font-bold">-</td>
                        <td className="py-4 px-4 text-right text-white font-bold">{formatCurrency(report.totals.total_sales)}</td>
                        <td className="py-4 px-4 text-right text-[#708238] font-bold">{formatCurrency(report.totals.total_commission)}</td>
                        <td className="py-4 px-4 text-right text-orange-400 font-bold">{formatCurrency(report.totals.pending_commission)}</td>
                        <td className="py-4 px-4 text-right text-green-400 font-bold">{formatCurrency(report.totals.paid_commission)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* QR Dialog */}
      <Dialog open={showQRDialog} onOpenChange={setShowQRDialog}>
        <DialogContent className="bg-[#161616] border-[#27272A] max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white text-center">
              Código QR de {selectedSalesperson?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="text-center space-y-4">
            <div ref={qrRef} className="bg-white p-6 rounded-lg inline-block">
              <QRCodeSVG
                value={selectedSalesperson?.qr_code || ""}
                size={200}
                level="H"
                includeMargin
              />
            </div>
            
            <div className="space-y-2">
              <p className="text-[#A1A1AA]">Código para compartir:</p>
              <div className="flex items-center justify-center gap-2">
                <Badge className="bg-[#708238]/20 text-[#708238] border-[#708238]/50 font-mono text-2xl py-2 px-4">
                  {selectedSalesperson?.share_code}
                </Badge>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleCopyCode(selectedSalesperson?.share_code)}
                  className="bg-transparent border-[#27272A]"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="bg-[#0D0D0D] p-4 rounded-lg">
              <p className="text-[#708238] font-bold">10% de descuento</p>
              <p className="text-sm text-[#A1A1AA]">para quien presente este código</p>
            </div>

            <div className="flex gap-3 justify-center pt-4">
              <Button onClick={handleDownloadQR} variant="outline" className="bg-transparent border-[#27272A]">
                <Download className="h-4 w-4 mr-2" />
                Descargar
              </Button>
              <Button onClick={handleShare} className="bg-[#708238] hover:bg-[#5a692d]">
                <Share2 className="h-4 w-4 mr-2" />
                Compartir
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SalespeopleAdmin;
