import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import axios from "axios";
import { QRCodeSVG } from "qrcode.react";
import { 
  TrendingUp, DollarSign, Percent, Calendar, 
  Loader2, Download, Share2, LogOut, QrCode,
  CheckCircle2, Clock, CreditCard, FileText,
  Upload, Building, Copy, X
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

// PayPal link
const PAYPAL_LINK = "https://paypal.me/grupoviter";

const PartnersDashboard = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [buying, setBuying] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [selectedLots, setSelectedLots] = useState(1);
  const [paymentStep, setPaymentStep] = useState("select"); // "select", "spei", "paypal", "upload"
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [receiptFile, setReceiptFile] = useState(null);
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

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/api/partners/dashboard`, {
        headers: { Authorization: `Bearer ${partnerToken}` }
      });
      setDashboard(response.data);
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

  const handleBuyLots = async (lots, method = "stripe") => {
    setBuying(true);
    try {
      const response = await axios.post(
        `${API}/api/partners/buy-lots?lots=${lots}&method=${method}`,
        {},
        { headers: { Authorization: `Bearer ${partnerToken}` } }
      );
      if (method === "stripe") {
        window.location.href = response.data.checkout_url;
      } else {
        // For SPEI/PayPal, show instructions and purchase was created
        toast.success("Compra registrada. Realiza el pago y sube tu comprobante.");
        setShowPaymentModal(false);
        fetchDashboard();
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al procesar compra");
      setBuying(false);
    }
  };

  const openPaymentModal = (lots) => {
    setSelectedLots(lots);
    setPaymentStep("select");
    setShowPaymentModal(true);
    setReceiptFile(null);
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
      // Fallback
      const textArea = document.createElement("textarea");
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      toast.success("Copiado al portapapeles");
    });
  };

  const handleLogout = () => {
    localStorage.removeItem("partner_token");
    navigate("/socios");
  };

  const handleDownloadQR = () => {
    if (qrRef.current && dashboard) {
      const svg = qrRef.current.querySelector("svg");
      const svgData = new XMLSerializer().serializeToString(svg);
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      const img = new Image();
      img.onload = () => {
        canvas.width = 400;
        canvas.height = 550;
        ctx.fillStyle = "#0D0D0D";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 50, 50, 300, 300);
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "bold 20px Arial";
        ctx.textAlign = "center";
        ctx.fillText(dashboard.partner.name, 200, 400);
        ctx.fillStyle = "#708238";
        ctx.font = "16px Arial";
        ctx.fillText(`Socio Inversionista`, 200, 430);
        ctx.fillText(`${dashboard.partner.participation_percent.toFixed(1)}% participación`, 200, 460);
        ctx.fillText(`Código: ${dashboard.partner.partner_code}`, 200, 490);
        ctx.fillStyle = "#A1A1AA";
        ctx.font = "12px Arial";
        ctx.fillText("10% descuento en compras", 200, 520);
        
        const link = document.createElement("a");
        link.download = `Certificado-Socio-${dashboard.partner.name.replace(/\s/g, "_")}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
      };
      img.src = "data:image/svg+xml;base64," + btoa(svgData);
    }
  };

  const formatCurrency = (amount) => `$${amount?.toLocaleString() || 0}`;
  const formatDate = (dateStr) => new Date(dateStr).toLocaleDateString("es-MX", {
    day: "numeric", month: "short", year: "numeric"
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  if (!dashboard) {
    return null;
  }

  const { partner, purchases, recent_returns, current_lot_price, monthly_return_per_lot, total_payment_months } = dashboard;

  return (
    <div className="min-h-screen bg-[#0D0D0D] pb-20">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1a1a1a] to-[#0D0D0D] pt-6 pb-8 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-6">
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

          {/* Main Stats */}
          <Card className="bg-gradient-to-r from-[#708238]/20 to-[#708238]/5 border-[#708238]/30">
            <CardContent className="p-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                  <p className="text-[#A1A1AA] text-sm">Lotes</p>
                  <p className="text-3xl font-bold text-white">{partner.total_lots}</p>
                </div>
                <div>
                  <p className="text-[#A1A1AA] text-sm">Participación</p>
                  <p className="text-3xl font-bold text-[#708238]">{partner.participation_percent.toFixed(2)}%</p>
                </div>
                <div>
                  <p className="text-[#A1A1AA] text-sm">Inversión Total</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(partner.total_investment)}</p>
                </div>
                <div>
                  <p className="text-[#A1A1AA] text-sm">Valor Actual</p>
                  <p className="text-2xl font-bold text-[#708238]">{formatCurrency(partner.current_value)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 space-y-6">
        {/* Returns Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-green-500/20 rounded-lg">
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <p className="text-sm text-[#A1A1AA]">Rendimientos Pagados</p>
                  <p className="text-xl font-bold text-green-400">{formatCurrency(partner.total_returns_paid)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-blue-500/20 rounded-lg">
                  <Calendar className="h-5 w-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm text-[#A1A1AA]">Pagos Recibidos</p>
                  <p className="text-xl font-bold text-white">
                    {partner.payments_made} <span className="text-sm text-[#71717A]">/ {total_payment_months}</span>
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-[#708238]/20 rounded-lg">
                  <DollarSign className="h-5 w-5 text-[#708238]" />
                </div>
                <div>
                  <p className="text-sm text-[#A1A1AA]">Próximo Pago</p>
                  <p className="text-xl font-bold text-white">{formatCurrency(partner.total_lots * monthly_return_per_lot)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* QR and Certificate */}
        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <QrCode className="h-5 w-5 text-[#708238]" />
              Tu Certificado de Socio
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col md:flex-row items-center gap-6">
              <div ref={qrRef} className="bg-white p-4 rounded-lg">
                <QRCodeSVG
                  value={partner.qr_code}
                  size={150}
                  level="H"
                  includeMargin
                />
              </div>
              <div className="flex-1 text-center md:text-left">
                <p className="text-[#A1A1AA] mb-2">Código de Socio:</p>
                <Badge className="bg-[#708238]/20 text-[#708238] border-[#708238]/50 font-mono text-lg px-4 py-2">
                  {partner.partner_code}
                </Badge>
                <p className="text-sm text-[#71717A] mt-4">
                  Presenta este código en cualquier sucursal para obtener <strong className="text-[#708238]">10% de descuento</strong> y generar comisiones adicionales.
                </p>
                <div className="flex gap-3 mt-4 justify-center md:justify-start">
                  <Button onClick={handleDownloadQR} variant="outline" className="bg-transparent border-[#27272A]">
                    <Download className="h-4 w-4 mr-2" />
                    Descargar
                  </Button>
                </div>
              </div>
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
            <p className="text-[#A1A1AA] mb-4">
              Precio actual por lote: <strong className="text-white">{formatCurrency(current_lot_price)}</strong>
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[1, 3, 5, 10].map((lots) => (
                <Button
                  key={lots}
                  onClick={() => handleBuyLots(lots)}
                  disabled={buying}
                  variant="outline"
                  className="bg-transparent border-[#27272A] hover:border-[#708238] hover:bg-[#708238]/10 flex-col h-auto py-4"
                >
                  <span className="text-2xl font-bold text-white">{lots}</span>
                  <span className="text-sm text-[#A1A1AA]">lote{lots > 1 ? 's' : ''}</span>
                  <span className="text-[#708238] font-bold">{formatCurrency(lots * current_lot_price)}</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Purchase History */}
        {purchases && purchases.length > 0 && (
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <FileText className="h-5 w-5 text-[#708238]" />
                Historial de Compras
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {purchases.map((purchase) => (
                  <div 
                    key={purchase.id} 
                    className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A] flex items-center justify-between"
                  >
                    <div>
                      <p className="text-white font-bold">{purchase.lots} lote{purchase.lots > 1 ? 's' : ''}</p>
                      <p className="text-sm text-[#71717A]">
                        {formatDate(purchase.created_at)} • {purchase.participation_percent.toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[#708238] font-bold">{formatCurrency(purchase.total_amount)}</p>
                      <Badge 
                        className={purchase.status === "completed" 
                          ? "bg-green-500/20 text-green-400 border-green-500/30" 
                          : "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
                        }
                      >
                        {purchase.status === "completed" ? "Completada" : "Pendiente"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recent Returns */}
        {recent_returns && recent_returns.length > 0 && (
          <Card className="bg-[#161616] border-[#27272A]">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <DollarSign className="h-5 w-5 text-[#708238]" />
                Últimos Rendimientos
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {recent_returns.map((ret) => (
                  <div 
                    key={ret.id} 
                    className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A] flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      {ret.status === "paid" ? (
                        <CheckCircle2 className="h-5 w-5 text-green-400" />
                      ) : (
                        <Clock className="h-5 w-5 text-yellow-400" />
                      )}
                      <div>
                        <p className="text-white">Pago #{ret.payment_number} - {ret.month_year}</p>
                        <p className="text-sm text-[#71717A]">{ret.lots} lotes</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={ret.status === "paid" ? "text-green-400 font-bold" : "text-yellow-400 font-bold"}>
                        {formatCurrency(ret.amount)}
                      </p>
                      <p className="text-xs text-[#71717A]">
                        {ret.status === "paid" ? `Pagado ${formatDate(ret.paid_at)}` : "Pendiente"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Footer Links */}
        <div className="text-center pt-6">
          <Link to="/socios" className="text-sm text-[#71717A] hover:text-white">
            Más información sobre el programa de socios
          </Link>
        </div>
      </div>
    </div>
  );
};

export default PartnersDashboard;
