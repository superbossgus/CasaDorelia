import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { 
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";
import { 
  TrendingUp, DollarSign, Percent, Calendar, 
  Loader2, Download, Share2, LogOut, QrCode,
  CheckCircle2, Clock, CreditCard, FileText,
  Upload, Building, Copy, X, ChevronDown, ChevronUp,
  PiggyBank, Target, ArrowUpRight, RefreshCw, Info,
  Ticket, AlertTriangle
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

// Logo de Doré en blanco para fondos oscuros
const DORE_LOGO_WHITE = "https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png";

// Datos de cuenta SPEI
const SPEI_DATA = {
  beneficiary: "Grupo Viter, S.A. de C.V.",
  rfc: "GVI160429NL9",
  bank: "BBVA Bancomer",
  account: "0106483542",
  clabe: "012180001064835429"
};

const PAYPAL_LINK = "https://paypal.me/grupoviter";

const PartnersDashboard = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [projection, setProjection] = useState(null);
  const [fundStatus, setFundStatus] = useState(null);
  const [loadingProjection, setLoadingProjection] = useState(false);
  const [buying, setBuying] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedLots, setSelectedLots] = useState(1);
  const [paymentStep, setPaymentStep] = useState("select");
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [receiptFile, setReceiptFile] = useState(null);
  const [activeTab, setActiveTab] = useState("resumen");
  const [reinvestEnabled, setReinvestEnabled] = useState(true);
  const [reinvestUntilMonth, setReinvestUntilMonth] = useState(36);
  const [showProjectionTable, setShowProjectionTable] = useState(false);
  const [couponCode, setCouponCode] = useState("");
  const [couponValidation, setCouponValidation] = useState(null);
  const [validatingCoupon, setValidatingCoupon] = useState(false);
  const qrRef = useRef(null);
  const fileInputRef = useRef(null);

  const partnerToken = localStorage.getItem("partner_token");

  useEffect(() => {
    if (!partnerToken) {
      navigate("/socios/login");
      return;
    }
    fetchDashboard();
  }, [partnerToken, navigate]);

  useEffect(() => {
    if (dashboard && dashboard.partner.total_lots > 0) {
      fetchProjection();
    }
  }, [reinvestEnabled, reinvestUntilMonth, dashboard?.partner?.total_lots]);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/api/partners/dashboard`, {
        headers: { Authorization: `Bearer ${partnerToken}` }
      });
      setDashboard(response.data);
      // Set reinvest settings from partner data if available
      if (response.data.partner.reinvest_enabled !== undefined) {
        setReinvestEnabled(response.data.partner.reinvest_enabled);
      }
      if (response.data.partner.reinvest_until_month !== undefined) {
        setReinvestUntilMonth(response.data.partner.reinvest_until_month);
      }
      // Fetch fund status
      fetchFundStatus();
    } catch (error) {
      if (error.response?.status === 401) {
        localStorage.removeItem("partner_token");
        navigate("/socios/login");
      }
      toast.error("Error al cargar dashboard");
    } finally {
      setLoading(false);
    }
  };

  const fetchFundStatus = async () => {
    try {
      const response = await axios.get(`${API}/api/partners/fund-status`);
      setFundStatus(response.data);
    } catch (error) {
      console.error("Error fetching fund status:", error);
    }
  };

  const fetchProjection = async () => {
    setLoadingProjection(true);
    try {
      const response = await axios.get(
        `${API}/api/partners/projection?reinvest=${reinvestEnabled}&reinvest_until_month=${reinvestUntilMonth}`,
        { headers: { Authorization: `Bearer ${partnerToken}` } }
      );
      setProjection(response.data);
    } catch (error) {
      console.error("Error fetching projection:", error);
    } finally {
      setLoadingProjection(false);
    }
  };

  const updateReinvestSettings = async (enabled, untilMonth) => {
    try {
      await axios.put(
        `${API}/api/partners/reinvestment-settings?reinvest_enabled=${enabled}&reinvest_until_month=${untilMonth}`,
        {},
        { headers: { Authorization: `Bearer ${partnerToken}` } }
      );
      toast.success("Configuración actualizada");
    } catch (error) {
      toast.error("Error al actualizar configuración");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("partner_token");
    navigate("/socios/login");
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
  };

  const formatPercent = (value) => {
    return `${value.toFixed(1)}%`;
  };

  const downloadQR = () => {
    const svg = qrRef.current?.querySelector("svg");
    if (!svg) return;
    
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    const svgData = new XMLSerializer().serializeToString(svg);
    const img = new Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      
      const link = document.createElement("a");
      link.download = `qr_socio_${dashboard.partner.partner_code.replace(/\s/g, "_")}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    };
    
    img.src = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(svgData)))}`;
  };

  const handleBuyLots = async (lots, method = "stripe") => {
    // Check fund availability
    if (fundStatus && fundStatus.is_sold_out) {
      toast.error("Se ha llegado al máximo de lotes del fondo. No hay lotes disponibles.");
      return;
    }
    if (fundStatus && lots > fundStatus.available_lots) {
      toast.error(`Solo quedan ${fundStatus.available_lots} lotes disponibles en el fondo.`);
      return;
    }

    setBuying(true);
    try {
      const couponParam = couponValidation ? `&coupon_code=${couponCode}` : "";
      const response = await axios.post(
        `${API}/api/partners/buy-lots?lots=${lots}&method=${method}${couponParam}`,
        {},
        { headers: { Authorization: `Bearer ${partnerToken}` } }
      );
      if (method === "stripe") {
        window.location.href = response.data.checkout_url;
      } else {
        toast.success("Compra registrada. Realiza el pago y sube tu comprobante.");
        setShowPaymentModal(false);
        setCouponCode("");
        setCouponValidation(null);
        fetchDashboard();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al procesar compra");
      setBuying(false);
    }
  };

  const validateCoupon = async () => {
    if (!couponCode.trim()) {
      toast.error("Ingresa un código de cupón");
      return;
    }

    setValidatingCoupon(true);
    try {
      const amount = selectedLots * current_lot_price;
      const response = await axios.post(
        `${API}/api/coupons/validate?code=${couponCode}&valid_for=investment&amount=${amount}&tenant_id=${dashboard.partner.tenant_id}`
      );
      setCouponValidation(response.data);
      toast.success(`¡Cupón válido! Descuento de ${formatCurrency(response.data.discount_amount)}`);
    } catch (error) {
      setCouponValidation(null);
      toast.error(error.response?.data?.detail || "Cupón no válido");
    } finally {
      setValidatingCoupon(false);
    }
  };

  const removeCoupon = () => {
    setCouponCode("");
    setCouponValidation(null);
  };

  const openPaymentModal = (lots) => {
    setSelectedLots(lots);
    setPaymentStep("select");
    setShowPaymentModal(true);
    setReceiptFile(null);
    setCouponCode("");
    setCouponValidation(null);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        toast.error("El archivo es demasiado grande (máx 10MB)");
        return;
      }
      setReceiptFile(file);
    }
  };

  const handleUploadReceipt = async () => {
    if (!receiptFile) {
      toast.error("Selecciona un archivo");
      return;
    }

    setUploadingReceipt(true);
    try {
      const formData = new FormData();
      formData.append("file", receiptFile);
      formData.append("lots", selectedLots);
      formData.append("payment_method", paymentStep === "spei" ? "spei" : "paypal");

      await axios.post(`${API}/api/partners/upload-receipt`, formData, {
        headers: {
          Authorization: `Bearer ${partnerToken}`,
          "Content-Type": "multipart/form-data"
        }
      });

      toast.success("¡Comprobante subido! Tu compra será verificada pronto.");
      setShowPaymentModal(false);
      setReceiptFile(null);
      fetchDashboard();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al subir comprobante");
    } finally {
      setUploadingReceipt(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success("Copiado al portapapeles");
    }).catch(() => {
      const textArea = document.createElement("textarea");
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      toast.success("Copiado al portapapeles");
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <p className="text-[#A1A1AA]">Error al cargar datos</p>
      </div>
    );
  }

  const { partner, purchases, recent_returns, current_lot_price, monthly_return_per_lot } = dashboard;
  const kpis = projection?.kpis || {};

  // Prepare chart data
  const chartData = projection?.projection?.filter((_, i) => i % 3 === 0 || i === 47).map(p => ({
    mes: `M${p.month}`,
    valor: p.portfolio_value,
    lotes: p.lots_end,
    dividendo: p.monthly_dividend
  })) || [];

  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#708238]/20 to-transparent border-b border-[#27272A]">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <img 
                src={DORE_LOGO_WHITE}
                alt="Doré" 
                className="h-10 w-auto brightness-0 invert"
              />
              <div>
                <p className="text-[#A1A1AA] text-sm">Portal de Socios</p>
                <h1 className="text-lg font-bold text-white">{partner.name}</h1>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline" className="border-[#708238] text-[#708238]">
                {partner.partner_code}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="text-[#A1A1AA] hover:text-white"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Salir
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-[#27272A]">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex gap-1">
            {[
              { id: "resumen", label: "Resumen Ejecutivo", icon: TrendingUp },
              { id: "proyeccion", label: "Proyección de Inversión", icon: Target },
              { id: "historial", label: "Historial y Pagos", icon: FileText }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-[1px] ${
                  activeTab === tab.id
                    ? "border-[#708238] text-white"
                    : "border-transparent text-[#A1A1AA] hover:text-white"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Tab: Resumen Ejecutivo */}
        {activeTab === "resumen" && (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="bg-gradient-to-br from-[#708238]/20 to-[#708238]/5 border-[#708238]/30">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <PiggyBank className="h-5 w-5 text-[#708238]" />
                    <span className="text-sm text-[#A1A1AA]">Inversión Total</span>
                  </div>
                  <p className="text-2xl font-bold text-white">{formatCurrency(partner.total_investment)}</p>
                  <p className="text-xs text-[#708238]">{partner.total_lots} lotes</p>
                </CardContent>
              </Card>

              <Card className="bg-[#161616] border-[#27272A]">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Percent className="h-5 w-5 text-[#708238]" />
                    <span className="text-sm text-[#A1A1AA]">Participación</span>
                  </div>
                  <p className="text-2xl font-bold text-[#708238]">{formatPercent(partner.participation_percent)}</p>
                  <p className="text-xs text-[#A1A1AA]">del Fondo Doré</p>
                </CardContent>
              </Card>

              <Card className="bg-[#161616] border-[#27272A]">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="h-5 w-5 text-[#708238]" />
                    <span className="text-sm text-[#A1A1AA]">Dividendo Mensual</span>
                  </div>
                  <p className="text-2xl font-bold text-white">{formatCurrency(partner.total_lots * monthly_return_per_lot)}</p>
                  <p className="text-xs text-[#A1A1AA]">${monthly_return_per_lot} × {partner.total_lots} lotes</p>
                </CardContent>
              </Card>

              <Card className="bg-[#161616] border-[#27272A]">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <TrendingUp className="h-5 w-5 text-[#708238]" />
                    <span className="text-sm text-[#A1A1AA]">Valor Portafolio</span>
                  </div>
                  <p className="text-2xl font-bold text-white">{formatCurrency(partner.current_value)}</p>
                  <p className="text-xs text-green-500">+{formatPercent(((partner.current_value / partner.total_investment) - 1) * 100 || 0)}</p>
                </CardContent>
              </Card>
            </div>

            {/* Projection Summary Card */}
            {projection && kpis.initial_lots > 0 && (
              <Card className="bg-gradient-to-r from-[#161616] to-[#1F1F1F] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <Target className="h-5 w-5 text-[#708238]" />
                    Proyección a 48 Meses
                    {reinvestEnabled && (
                      <Badge className="bg-[#708238]/20 text-[#708238] text-xs">
                        Con reinversión hasta mes {reinvestUntilMonth}
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                    <div className="text-center p-3 bg-[#0D0D0D] rounded-lg">
                      <p className="text-xs text-[#A1A1AA] mb-1">Lotes Finales</p>
                      <p className="text-xl font-bold text-white">{kpis.final_lots}</p>
                      <p className="text-xs text-green-500">+{kpis.lots_growth} nuevos</p>
                    </div>
                    <div className="text-center p-3 bg-[#0D0D0D] rounded-lg">
                      <p className="text-xs text-[#A1A1AA] mb-1">Dividendo Final/Mes</p>
                      <p className="text-xl font-bold text-[#708238]">{formatCurrency(kpis.final_monthly_dividend)}</p>
                    </div>
                    <div className="text-center p-3 bg-[#0D0D0D] rounded-lg">
                      <p className="text-xs text-[#A1A1AA] mb-1">Total Dividendos</p>
                      <p className="text-xl font-bold text-white">{formatCurrency(kpis.total_dividends_received)}</p>
                    </div>
                    <div className="text-center p-3 bg-[#0D0D0D] rounded-lg">
                      <p className="text-xs text-[#A1A1AA] mb-1">Valor Final</p>
                      <p className="text-xl font-bold text-[#708238]">{formatCurrency(kpis.final_portfolio_value)}</p>
                    </div>
                    <div className="text-center p-3 bg-[#0D0D0D] rounded-lg">
                      <p className="text-xs text-[#A1A1AA] mb-1">ROI Total</p>
                      <p className="text-xl font-bold text-green-500">+{formatPercent(kpis.roi_percentage)}</p>
                      <p className="text-xs text-[#A1A1AA]">Mes recuperación: {kpis.recovery_month}</p>
                    </div>
                  </div>

                  {/* Portfolio Growth Chart */}
                  {chartData.length > 0 && (
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="colorValor" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#708238" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#708238" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="mes" stroke="#71717A" fontSize={12} />
                          <YAxis stroke="#71717A" fontSize={12} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#161616', border: '1px solid #27272A', borderRadius: '8px' }}
                            labelStyle={{ color: '#A1A1AA' }}
                            formatter={(value, name) => [formatCurrency(value), name === 'valor' ? 'Valor Portafolio' : name]}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="valor" 
                            stroke="#708238" 
                            fillOpacity={1} 
                            fill="url(#colorValor)" 
                            name="Valor Portafolio"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* QR Code & Referral Section */}
            <div className="grid md:grid-cols-2 gap-4">
              <Card className="bg-[#161616] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <QrCode className="h-5 w-5 text-[#708238]" />
                    Tu Código QR de Descuento
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-[#A1A1AA] text-sm mb-4">
                    Comparte este código para dar 10% de descuento y ganar comisiones
                  </p>
                  <div className="flex justify-center" ref={qrRef}>
                    <div className="p-4 bg-white rounded-lg">
                      <QRCodeSVG value={partner.qr_code} size={150} />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button 
                      onClick={downloadQR}
                      variant="outline" 
                      className="flex-1 border-[#27272A] text-white hover:bg-[#27272A]"
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Descargar
                    </Button>
                    <Button
                      onClick={() => setShowQR(!showQR)}
                      variant="outline"
                      className="flex-1 border-[#708238] text-[#708238] hover:bg-[#708238]/10"
                    >
                      <Share2 className="h-4 w-4 mr-2" />
                      Compartir
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Buy More Lots */}
              <Card className="bg-[#161616] border-[#27272A]">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-[#708238]" />
                    Comprar Más Lotes
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Fund Status */}
                  {fundStatus && (
                    <div className="mb-4 p-3 bg-[#0D0D0D] rounded-lg border border-[#27272A]">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-[#A1A1AA]">Fondo Doré</span>
                        <span className="text-sm text-[#708238]">
                          {fundStatus.available_lots.toLocaleString()} / {fundStatus.max_total_lots.toLocaleString()} lotes disponibles
                        </span>
                      </div>
                      <div className="w-full bg-[#27272A] rounded-full h-2">
                        <div 
                          className="bg-[#708238] h-2 rounded-full transition-all"
                          style={{ width: `${fundStatus.fund_percentage_sold}%` }}
                        />
                      </div>
                      <p className="text-xs text-[#71717A] mt-1">
                        {fundStatus.fund_percentage_sold}% vendido • {formatCurrency(fundStatus.fund_total_value)} valor total del fondo
                      </p>
                    </div>
                  )}

                  {fundStatus?.is_sold_out ? (
                    <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-center">
                      <AlertTriangle className="h-8 w-8 text-red-400 mx-auto mb-2" />
                      <p className="text-red-400 font-medium">Se ha llegado al máximo de lotes del fondo</p>
                      <p className="text-sm text-[#A1A1AA] mt-1">No hay lotes disponibles para comprar</p>
                    </div>
                  ) : (
                    <>
                      <p className="text-[#A1A1AA] text-sm mb-4">
                        Precio actual: <strong className="text-white">{formatCurrency(current_lot_price)}</strong> / lote
                      </p>
                      <div className="grid grid-cols-2 gap-3">
                        {[1, 3, 5, 10].map((lots) => (
                          <Button
                            key={lots}
                            onClick={() => openPaymentModal(lots)}
                            disabled={buying || (fundStatus && lots > fundStatus.available_lots)}
                            variant="outline"
                            className="bg-transparent border-[#27272A] hover:border-[#708238] hover:bg-[#708238]/10 flex-col h-auto py-3"
                          >
                            <span className="text-xl font-bold text-white">{lots}</span>
                            <span className="text-xs text-[#A1A1AA]">lote{lots > 1 ? 's' : ''}</span>
                            <span className="text-sm text-[#708238] font-bold">{formatCurrency(lots * current_lot_price)}</span>
                          </Button>
                        ))}
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}

        {/* Tab: Proyección de Inversión */}
        {activeTab === "proyeccion" && (
          <>
            {/* Reinvestment Settings */}
            <Card className="bg-[#161616] border-[#27272A]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <RefreshCw className="h-5 w-5 text-[#708238]" />
                  Configuración de Reinversión
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col md:flex-row md:items-center gap-6">
                  <div className="flex items-center gap-4">
                    <Switch
                      checked={reinvestEnabled}
                      onCheckedChange={(checked) => {
                        setReinvestEnabled(checked);
                        updateReinvestSettings(checked, reinvestUntilMonth);
                      }}
                    />
                    <div>
                      <p className="text-white font-medium">Reinversión Automática</p>
                      <p className="text-sm text-[#A1A1AA]">Los dividendos se usan para comprar más lotes</p>
                    </div>
                  </div>
                  
                  {reinvestEnabled && (
                    <div className="flex items-center gap-3">
                      <Label className="text-[#A1A1AA]">Reinvertir hasta el mes:</Label>
                      <Input
                        type="number"
                        value={reinvestUntilMonth}
                        onChange={(e) => {
                          const v = Math.min(48, Math.max(1, parseInt(e.target.value) || 36));
                          setReinvestUntilMonth(v);
                          updateReinvestSettings(reinvestEnabled, v);
                        }}
                        min={1}
                        max={48}
                        className="w-20 bg-[#0D0D0D] border-[#27272A] text-white"
                      />
                    </div>
                  )}
                </div>

                <div className="mt-4 p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A]">
                  <div className="flex items-start gap-2">
                    <Info className="h-5 w-5 text-[#708238] mt-0.5" />
                    <div className="text-sm text-[#A1A1AA]">
                      <p><strong className="text-white">¿Cómo funciona?</strong></p>
                      <p>Con reinversión activa, tus dividendos mensuales + un 10% de interés anual se acumulan para comprar nuevos lotes automáticamente. Esto aumenta tu participación y dividendos futuros.</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Projection KPIs */}
            {projection && kpis.initial_lots > 0 && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card className="bg-gradient-to-br from-[#708238]/20 to-transparent border-[#708238]/30">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Inversión Inicial</p>
                      <p className="text-2xl font-bold text-white">{formatCurrency(kpis.initial_investment)}</p>
                      <p className="text-xs text-[#708238]">{kpis.initial_lots} lotes</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#161616] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Lotes al Final (Mes 48)</p>
                      <p className="text-2xl font-bold text-white">{kpis.final_lots}</p>
                      <p className="text-xs text-green-500">+{kpis.lots_growth} nuevos</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#161616] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Participación Final</p>
                      <p className="text-2xl font-bold text-[#708238]">{formatPercent(kpis.participation_final)}</p>
                      <p className="text-xs text-[#A1A1AA]">desde {formatPercent(kpis.participation_initial)}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#161616] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Mes de Recuperación</p>
                      <p className="text-2xl font-bold text-white">Mes {kpis.recovery_month}</p>
                      <p className="text-xs text-[#A1A1AA]">~{Math.ceil(kpis.recovery_month / 12)} años</p>
                    </CardContent>
                  </Card>
                </div>

                <div className="grid md:grid-cols-2 gap-4">
                  <Card className="bg-[#161616] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Total Dividendos Recibidos</p>
                      <p className="text-3xl font-bold text-white">{formatCurrency(kpis.total_dividends_received)}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-[#161616] border-[#27272A]">
                    <CardContent className="p-4 text-center">
                      <p className="text-sm text-[#A1A1AA]">Total Interés Ganado</p>
                      <p className="text-3xl font-bold text-[#708238]">{formatCurrency(kpis.total_interest_earned)}</p>
                    </CardContent>
                  </Card>
                </div>

                {/* Charts */}
                <Card className="bg-[#161616] border-[#27272A]">
                  <CardHeader>
                    <CardTitle className="text-white">Crecimiento del Portafolio</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-80">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={projection.projection}>
                          <defs>
                            <linearGradient id="colorValor2" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#708238" stopOpacity={0.4}/>
                              <stop offset="95%" stopColor="#708238" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="month" stroke="#71717A" fontSize={12} />
                          <YAxis stroke="#71717A" fontSize={12} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#161616', border: '1px solid #27272A', borderRadius: '8px' }}
                            labelStyle={{ color: '#A1A1AA' }}
                            formatter={(value, name) => {
                              const labels = {
                                portfolio_value: 'Valor Portafolio',
                                cumulative_return: 'Retorno Acumulado'
                              };
                              return [formatCurrency(value), labels[name] || name];
                            }}
                          />
                          <Legend />
                          <Area type="monotone" dataKey="portfolio_value" stroke="#708238" fillOpacity={1} fill="url(#colorValor2)" name="Valor Portafolio" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Lots Growth Chart */}
                <Card className="bg-[#161616] border-[#27272A]">
                  <CardHeader>
                    <CardTitle className="text-white">Crecimiento de Lotes</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={projection.projection}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                          <XAxis dataKey="month" stroke="#71717A" fontSize={12} />
                          <YAxis stroke="#71717A" fontSize={12} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: '#161616', border: '1px solid #27272A', borderRadius: '8px' }}
                            labelStyle={{ color: '#A1A1AA' }}
                          />
                          <Legend />
                          <Line type="stepAfter" dataKey="lots_end" stroke="#708238" strokeWidth={2} dot={false} name="Total Lotes" />
                          <Line type="monotone" dataKey="next_month_dividend" stroke="#F59E0B" strokeWidth={2} dot={false} name="Dividendo Mensual" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* Detailed Table Toggle */}
                <Card className="bg-[#161616] border-[#27272A]">
                  <CardHeader>
                    <button
                      onClick={() => setShowProjectionTable(!showProjectionTable)}
                      className="w-full flex items-center justify-between"
                    >
                      <CardTitle className="text-white flex items-center gap-2">
                        <FileText className="h-5 w-5 text-[#708238]" />
                        Tabla Detallada de Corrida Mensual
                      </CardTitle>
                      {showProjectionTable ? (
                        <ChevronUp className="h-5 w-5 text-[#A1A1AA]" />
                      ) : (
                        <ChevronDown className="h-5 w-5 text-[#A1A1AA]" />
                      )}
                    </button>
                  </CardHeader>
                  {showProjectionTable && (
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-[#27272A]">
                              <th className="py-2 px-3 text-left text-[#A1A1AA]">Mes</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">Lotes</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">Dividendo</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">Interés</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">Lotes +</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">Valor Port.</th>
                              <th className="py-2 px-3 text-right text-[#A1A1AA]">ROI</th>
                            </tr>
                          </thead>
                          <tbody>
                            {projection.projection.map((row) => (
                              <tr key={row.month} className={`border-b border-[#27272A]/50 ${row.recovered ? 'bg-green-500/5' : ''}`}>
                                <td className="py-2 px-3 text-white">{row.month}</td>
                                <td className="py-2 px-3 text-right text-white">{row.lots_end}</td>
                                <td className="py-2 px-3 text-right text-white">{formatCurrency(row.monthly_dividend)}</td>
                                <td className="py-2 px-3 text-right text-[#708238]">{formatCurrency(row.interest_earned)}</td>
                                <td className="py-2 px-3 text-right text-green-500">{row.lots_purchased > 0 ? `+${row.lots_purchased}` : '-'}</td>
                                <td className="py-2 px-3 text-right text-white font-medium">{formatCurrency(row.portfolio_value)}</td>
                                <td className="py-2 px-3 text-right text-[#708238]">{formatPercent(row.roi_percentage)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  )}
                </Card>
              </>
            )}

            {(!projection || kpis.initial_lots === 0) && (
              <Card className="bg-[#161616] border-[#27272A]">
                <CardContent className="py-12 text-center">
                  <Target className="h-12 w-12 text-[#52525B] mx-auto mb-4" />
                  <p className="text-[#A1A1AA]">Compra tu primer lote para ver la proyección de tu inversión</p>
                  <Button
                    onClick={() => setActiveTab("resumen")}
                    className="mt-4 bg-[#708238] hover:bg-[#5a692d]"
                  >
                    Comprar Lotes
                  </Button>
                </CardContent>
              </Card>
            )}
          </>
        )}

        {/* Tab: Historial y Pagos */}
        {activeTab === "historial" && (
          <>
            {/* Purchases History */}
            <Card className="bg-[#161616] border-[#27272A]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-[#708238]" />
                  Historial de Compras
                </CardTitle>
              </CardHeader>
              <CardContent>
                {purchases && purchases.length > 0 ? (
                  <div className="space-y-3">
                    {purchases.map((purchase) => (
                      <div
                        key={purchase.id}
                        className="flex items-center justify-between p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A]"
                      >
                        <div>
                          <p className="text-white font-medium">{purchase.lots} lote{purchase.lots > 1 ? 's' : ''}</p>
                          <p className="text-sm text-[#A1A1AA]">
                            {new Date(purchase.created_at).toLocaleDateString('es-MX')}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-white font-bold">{formatCurrency(purchase.total_amount)}</p>
                          <Badge 
                            className={
                              purchase.status === "completed" 
                                ? "bg-green-500/20 text-green-400"
                                : purchase.status === "pending_verification"
                                ? "bg-yellow-500/20 text-yellow-400"
                                : "bg-[#27272A] text-[#A1A1AA]"
                            }
                          >
                            {purchase.status === "completed" ? "Completado" : 
                             purchase.status === "pending_verification" ? "En verificación" : "Pendiente"}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[#A1A1AA] text-center py-8">No hay compras registradas</p>
                )}
              </CardContent>
            </Card>

            {/* Returns History */}
            <Card className="bg-[#161616] border-[#27272A]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-[#708238]" />
                  Historial de Rendimientos
                </CardTitle>
              </CardHeader>
              <CardContent>
                {recent_returns && recent_returns.length > 0 ? (
                  <div className="space-y-3">
                    {recent_returns.map((ret) => (
                      <div
                        key={ret.id}
                        className="flex items-center justify-between p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A]"
                      >
                        <div>
                          <p className="text-white font-medium">
                            {new Date(ret.payment_date).toLocaleDateString('es-MX', { month: 'long', year: 'numeric' })}
                          </p>
                          <p className="text-sm text-[#A1A1AA]">{ret.lots} lotes × ${ret.amount_per_lot}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-[#708238] font-bold">{formatCurrency(ret.amount)}</p>
                          <Badge 
                            className={
                              ret.status === "paid" 
                                ? "bg-green-500/20 text-green-400"
                                : "bg-yellow-500/20 text-yellow-400"
                            }
                          >
                            {ret.status === "paid" ? "Pagado" : "Pendiente"}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[#A1A1AA] text-center py-8">No hay rendimientos registrados</p>
                )}
              </CardContent>
            </Card>

            {/* Payment Info */}
            <Card className="bg-[#161616] border-[#27272A]">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Building className="h-5 w-5 text-[#708238]" />
                  Datos de Pago Registrados
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="p-4 bg-[#0D0D0D] rounded-lg">
                  {partner.payment_info?.method === "paypal" ? (
                    <div className="flex items-center gap-3">
                      <svg viewBox="0 0 24 24" className="h-8 w-8 text-[#0070ba]" fill="currentColor">
                        <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106zm14.146-14.42a3.35 3.35 0 0 0-.607-.541c-.013.076-.026.175-.041.254-.93 4.778-4.005 7.201-9.138 7.201h-2.19a.563.563 0 0 0-.556.479l-1.187 7.527-.336 2.131a.32.32 0 0 0 .317.37h4.103a.505.505 0 0 0 .499-.426l.02-.106.396-2.513.026-.14a.505.505 0 0 1 .499-.426h.315c4.036 0 7.19-1.64 8.116-6.378.387-1.976.186-3.632-.836-4.432z"/>
                      </svg>
                      <div>
                        <p className="text-white font-medium">PayPal</p>
                        <p className="text-[#A1A1AA]">{partner.payment_info.paypal_masked}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3">
                      <Building className="h-8 w-8 text-[#708238]" />
                      <div>
                        <p className="text-white font-medium">{partner.payment_info?.bank_name || "Cuenta Bancaria"}</p>
                        <p className="text-[#A1A1AA] font-mono">****{partner.payment_info?.clabe_last4 || partner.clabe_last4}</p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {/* Footer Link */}
        <div className="text-center py-4">
          <Link to="/socios" className="text-[#708238] hover:text-white transition-colors text-sm">
            Más información sobre el programa de socios
          </Link>
        </div>
      </div>

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-[#161616] rounded-xl border border-[#27272A] w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white">
                  Comprar {selectedLots} Lote{selectedLots > 1 ? 's' : ''}
                </h2>
                <button 
                  onClick={() => setShowPaymentModal(false)}
                  className="text-[#A1A1AA] hover:text-white"
                >
                  <X className="h-6 w-6" />
                </button>
              </div>

              <div className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A] mb-4">
                <div className="flex justify-between items-center">
                  <span className="text-[#A1A1AA]">Subtotal:</span>
                  <span className={`text-xl font-bold ${couponValidation ? "text-[#71717A] line-through" : "text-[#708238]"}`}>
                    {formatCurrency(selectedLots * current_lot_price)} MXN
                  </span>
                </div>
                {couponValidation && (
                  <>
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-green-400 text-sm">Descuento ({couponValidation.code}):</span>
                      <span className="text-green-400">-{formatCurrency(couponValidation.discount_amount)}</span>
                    </div>
                    <div className="flex justify-between items-center mt-2 pt-2 border-t border-[#27272A]">
                      <span className="text-white font-medium">Total a pagar:</span>
                      <span className="text-2xl font-bold text-[#708238]">
                        {formatCurrency(couponValidation.final_amount)} MXN
                      </span>
                    </div>
                  </>
                )}
                {!couponValidation && (
                  <p className="text-sm text-[#71717A] mt-2">
                    {(selectedLots * 0.1).toFixed(1)}% de participación • ${selectedLots * monthly_return_per_lot}/mes
                  </p>
                )}
              </div>

              {/* Coupon Code Field */}
              <div className="mb-6">
                <Label className="text-[#A1A1AA] text-sm mb-2 block">¿Tienes un cupón de descuento?</Label>
                {!couponValidation ? (
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Ticket className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      <Input
                        value={couponCode}
                        onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                        placeholder="Código de cupón"
                        className="bg-[#0D0D0D] border-[#27272A] text-white pl-10 font-mono uppercase"
                      />
                    </div>
                    <Button
                      onClick={validateCoupon}
                      disabled={validatingCoupon || !couponCode}
                      variant="outline"
                      className="border-[#708238] text-[#708238] hover:bg-[#708238]/10"
                    >
                      {validatingCoupon ? <Loader2 className="h-4 w-4 animate-spin" /> : "Aplicar"}
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center justify-between p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-green-400" />
                      <span className="text-green-400 font-mono">{couponValidation.code}</span>
                      <Badge className="bg-green-500/20 text-green-400">
                        {couponValidation.discount_type === "percent" 
                          ? `${couponValidation.discount_value}%` 
                          : formatCurrency(couponValidation.discount_value)}
                      </Badge>
                    </div>
                    <Button
                      onClick={removeCoupon}
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:text-red-300"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>

              {paymentStep === "select" && (
                <div className="space-y-3">
                  <p className="text-[#A1A1AA] mb-4">Selecciona tu método de pago:</p>
                  
                  <button
                    onClick={() => handleBuyLots(selectedLots, "stripe")}
                    disabled={buying}
                    className="w-full p-4 rounded-lg border-2 border-[#27272A] bg-[#0D0D0D] hover:border-[#708238] transition-all flex items-center gap-4"
                  >
                    <div className="p-3 bg-[#635bff]/20 rounded-lg">
                      <CreditCard className="h-6 w-6 text-[#635bff]" />
                    </div>
                    <div className="text-left flex-1">
                      <p className="text-white font-medium">Tarjeta Bancaria</p>
                      <p className="text-sm text-[#71717A]">Pago seguro con Stripe</p>
                    </div>
                    {buying && <Loader2 className="h-5 w-5 animate-spin text-[#708238]" />}
                  </button>

                  <button
                    onClick={() => setPaymentStep("paypal")}
                    className="w-full p-4 rounded-lg border-2 border-[#27272A] bg-[#0D0D0D] hover:border-[#0070ba] transition-all flex items-center gap-4"
                  >
                    <div className="p-3 bg-[#0070ba]/20 rounded-lg">
                      <svg viewBox="0 0 24 24" className="h-6 w-6 text-[#0070ba]" fill="currentColor">
                        <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106zm14.146-14.42a3.35 3.35 0 0 0-.607-.541c-.013.076-.026.175-.041.254-.93 4.778-4.005 7.201-9.138 7.201h-2.19a.563.563 0 0 0-.556.479l-1.187 7.527-.336 2.131a.32.32 0 0 0 .317.37h4.103a.505.505 0 0 0 .499-.426l.02-.106.396-2.513.026-.14a.505.505 0 0 1 .499-.426h.315c4.036 0 7.19-1.64 8.116-6.378.387-1.976.186-3.632-.836-4.432z"/>
                      </svg>
                    </div>
                    <div className="text-left flex-1">
                      <p className="text-white font-medium">PayPal</p>
                      <p className="text-sm text-[#71717A]">paypal.me/grupoviter</p>
                    </div>
                  </button>

                  <button
                    onClick={() => setPaymentStep("spei")}
                    className="w-full p-4 rounded-lg border-2 border-[#27272A] bg-[#0D0D0D] hover:border-[#004481] transition-all flex items-center gap-4"
                  >
                    <div className="p-3 bg-[#004481]/20 rounded-lg">
                      <Building className="h-6 w-6 text-[#004481]" />
                    </div>
                    <div className="text-left flex-1">
                      <p className="text-white font-medium">Depósito SPEI</p>
                      <p className="text-sm text-[#71717A]">Transferencia bancaria</p>
                    </div>
                  </button>
                </div>
              )}

              {paymentStep === "paypal" && (
                <div className="space-y-4">
                  <button 
                    onClick={() => setPaymentStep("select")}
                    className="text-[#708238] text-sm hover:underline"
                  >
                    ← Volver a opciones de pago
                  </button>

                  <div className="p-4 bg-[#0070ba]/10 rounded-lg border border-[#0070ba]/30">
                    <div className="flex items-center gap-3 mb-4">
                      <svg viewBox="0 0 24 24" className="h-8 w-8 text-[#0070ba]" fill="currentColor">
                        <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106zm14.146-14.42a3.35 3.35 0 0 0-.607-.541c-.013.076-.026.175-.041.254-.93 4.778-4.005 7.201-9.138 7.201h-2.19a.563.563 0 0 0-.556.479l-1.187 7.527-.336 2.131a.32.32 0 0 0 .317.37h4.103a.505.505 0 0 0 .499-.426l.02-.106.396-2.513.026-.14a.505.505 0 0 1 .499-.426h.315c4.036 0 7.19-1.64 8.116-6.378.387-1.976.186-3.632-.836-4.432z"/>
                      </svg>
                      <h3 className="text-white font-bold">Pago por PayPal</h3>
                    </div>
                    
                    <p className="text-[#A1A1AA] mb-4">1. Haz clic en el botón para ir a PayPal</p>
                    
                    <a
                      href={`${PAYPAL_LINK}/${selectedLots * current_lot_price}MXN`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full"
                    >
                      <Button className="w-full bg-[#0070ba] hover:bg-[#005ea6] text-white">
                        Pagar {formatCurrency(selectedLots * current_lot_price)} en PayPal
                      </Button>
                    </a>

                    <p className="text-[#A1A1AA] mt-4 mb-2">2. Después de pagar, sube tu comprobante:</p>
                  </div>

                  <div className="space-y-3">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      accept="image/*,.pdf"
                      className="hidden"
                    />
                    
                    <div 
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-[#27272A] rounded-lg p-6 text-center cursor-pointer hover:border-[#708238] transition-colors"
                    >
                      {receiptFile ? (
                        <div className="flex items-center justify-center gap-3">
                          <FileText className="h-8 w-8 text-[#708238]" />
                          <div className="text-left">
                            <p className="text-white font-medium">{receiptFile.name}</p>
                            <p className="text-sm text-[#71717A]">{(receiptFile.size / 1024).toFixed(1)} KB</p>
                          </div>
                        </div>
                      ) : (
                        <>
                          <Upload className="h-10 w-10 text-[#52525B] mx-auto mb-2" />
                          <p className="text-[#A1A1AA]">Subir comprobante</p>
                          <p className="text-xs text-[#71717A]">Imagen o PDF (máx 10MB)</p>
                        </>
                      )}
                    </div>

                    <Button
                      onClick={handleUploadReceipt}
                      disabled={!receiptFile || uploadingReceipt}
                      className="w-full bg-[#708238] hover:bg-[#5a692d]"
                    >
                      {uploadingReceipt ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Subiendo...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4 mr-2" />
                          Enviar Comprobante
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {paymentStep === "spei" && (
                <div className="space-y-4">
                  <button 
                    onClick={() => setPaymentStep("select")}
                    className="text-[#708238] text-sm hover:underline"
                  >
                    ← Volver a opciones de pago
                  </button>

                  <div className="p-4 bg-[#004481]/10 rounded-lg border border-[#004481]/30">
                    <div className="flex items-center gap-3 mb-4">
                      <Building className="h-8 w-8 text-[#004481]" />
                      <h3 className="text-white font-bold">Datos para Transferencia SPEI</h3>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex justify-between items-center p-3 bg-[#0D0D0D] rounded-lg">
                        <div>
                          <p className="text-xs text-[#71717A]">Beneficiario</p>
                          <p className="text-white font-medium">{SPEI_DATA.beneficiary}</p>
                        </div>
                        <button onClick={() => copyToClipboard(SPEI_DATA.beneficiary)} className="text-[#708238]">
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="flex justify-between items-center p-3 bg-[#0D0D0D] rounded-lg">
                        <div>
                          <p className="text-xs text-[#71717A]">RFC</p>
                          <p className="text-white font-mono">{SPEI_DATA.rfc}</p>
                        </div>
                        <button onClick={() => copyToClipboard(SPEI_DATA.rfc)} className="text-[#708238]">
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="flex justify-between items-center p-3 bg-[#0D0D0D] rounded-lg">
                        <div>
                          <p className="text-xs text-[#71717A]">Banco</p>
                          <p className="text-white">{SPEI_DATA.bank}</p>
                        </div>
                        <button onClick={() => copyToClipboard(SPEI_DATA.bank)} className="text-[#708238]">
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="flex justify-between items-center p-3 bg-[#0D0D0D] rounded-lg">
                        <div>
                          <p className="text-xs text-[#71717A]">No. Cuenta</p>
                          <p className="text-white font-mono">{SPEI_DATA.account}</p>
                        </div>
                        <button onClick={() => copyToClipboard(SPEI_DATA.account)} className="text-[#708238]">
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>

                      <div className="flex justify-between items-center p-3 bg-[#708238]/20 rounded-lg border border-[#708238]/30">
                        <div>
                          <p className="text-xs text-[#A1A1AA]">CLABE Interbancaria</p>
                          <p className="text-[#708238] font-mono font-bold text-lg">{SPEI_DATA.clabe}</p>
                        </div>
                        <button onClick={() => copyToClipboard(SPEI_DATA.clabe)} className="text-[#708238]">
                          <Copy className="h-5 w-5" />
                        </button>
                      </div>

                      <div className="p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/30">
                        <p className="text-yellow-400 text-sm">
                          <strong>Importante:</strong> En el concepto incluye tu código: <span className="font-mono">{partner.partner_code}</span>
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="text-[#A1A1AA]">Después de la transferencia, sube tu comprobante:</p>
                    
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileSelect}
                      accept="image/*,.pdf"
                      className="hidden"
                    />
                    
                    <div 
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-[#27272A] rounded-lg p-6 text-center cursor-pointer hover:border-[#708238] transition-colors"
                    >
                      {receiptFile ? (
                        <div className="flex items-center justify-center gap-3">
                          <FileText className="h-8 w-8 text-[#708238]" />
                          <div className="text-left">
                            <p className="text-white font-medium">{receiptFile.name}</p>
                            <p className="text-sm text-[#71717A]">{(receiptFile.size / 1024).toFixed(1)} KB</p>
                          </div>
                        </div>
                      ) : (
                        <>
                          <Upload className="h-10 w-10 text-[#52525B] mx-auto mb-2" />
                          <p className="text-[#A1A1AA]">Subir comprobante</p>
                          <p className="text-xs text-[#71717A]">Imagen o PDF (máx 10MB)</p>
                        </>
                      )}
                    </div>

                    <Button
                      onClick={handleUploadReceipt}
                      disabled={!receiptFile || uploadingReceipt}
                      className="w-full bg-[#708238] hover:bg-[#5a692d]"
                    >
                      {uploadingReceipt ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Subiendo...
                        </>
                      ) : (
                        <>
                          <Upload className="h-4 w-4 mr-2" />
                          Enviar Comprobante
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PartnersDashboard;
