import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { 
  TrendingUp, Loader2, Eye, EyeOff, ArrowLeft, 
  User, Mail, Phone, Building, CreditCard, MapPin
} from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const BANKS = [
  "BBVA México", "Santander", "Banorte", "HSBC", "Scotiabank",
  "Citibanamex", "Banco Azteca", "Inbursa", "BanCoppel", "Afirme",
  "Banregio", "Multiva", "Banbajío", "Mifel", "Otro"
];

const PartnersRegister = () => {
  const navigate = useNavigate();
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState("");
  const [currentPrice, setCurrentPrice] = useState(4000);
  const [lotsToBuy, setLotsToBuy] = useState(1);
  const [paymentMethod, setPaymentMethod] = useState("bank"); // "bank" or "paypal"
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    curp: "",
    address: "",
    bank_name: "",
    clabe: "",
    paypal_email: "",
    password: "",
    confirmPassword: ""
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingBusinesses, setLoadingBusinesses] = useState(true);

  useEffect(() => {
    fetchBusinesses();
  }, []);

  const fetchBusinesses = async () => {
    try {
      const response = await axios.get(`${API}/api/partners/businesses`);
      setBusinesses(response.data);
      if (response.data.length > 0) {
        setSelectedBusiness(response.data[0].id);
        setCurrentPrice(response.data[0].current_lot_price);
      }
    } catch (error) {
      console.error("Error fetching businesses:", error);
    } finally {
      setLoadingBusinesses(false);
    }
  };

  const handleBusinessChange = (businessId) => {
    setSelectedBusiness(businessId);
    const business = businesses.find(b => b.id === businessId);
    if (business) {
      setCurrentPrice(business.current_lot_price);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    // Format CLABE (only numbers, max 18)
    if (name === "clabe") {
      const formatted = value.replace(/\D/g, "").slice(0, 18);
      setFormData({ ...formData, [name]: formatted });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedBusiness) {
      toast.error("Selecciona un negocio");
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      toast.error("Las contraseñas no coinciden");
      return;
    }

    if (formData.password.length < 6) {
      toast.error("La contraseña debe tener al menos 6 caracteres");
      return;
    }

    // Validate payment receiving method
    if (paymentMethod === "bank") {
      if (formData.clabe.length !== 18) {
        toast.error("La CLABE debe tener 18 dígitos");
        return;
      }
      if (!formData.bank_name) {
        toast.error("Selecciona tu banco");
        return;
      }
    } else if (paymentMethod === "paypal") {
      if (!formData.paypal_email || !formData.paypal_email.includes("@")) {
        toast.error("Ingresa un correo de PayPal válido");
        return;
      }
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/api/partners/register?tenant_id=${selectedBusiness}`, {
        name: formData.name,
        email: formData.email,
        phone: formData.phone,
        curp: formData.curp || null,
        address: formData.address || null,
        bank_name: formData.bank_name,
        clabe: formData.clabe,
        password: formData.password,
        lots_to_buy: lotsToBuy
      });

      localStorage.setItem("partner_token", response.data.token);
      toast.success("¡Registro exitoso! Bienvenido como socio.");
      navigate("/socios/dashboard");
    } catch (error) {
      const message = error.response?.data?.detail || "Error al registrarse";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const totalInvestment = lotsToBuy * currentPrice;
  const participation = lotsToBuy * 0.05;
  const monthlyReturn = lotsToBuy * 100;
  const totalReturn = monthlyReturn * 48;

  return (
    <div className="min-h-screen bg-[#0D0D0D] py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-center mb-8">
          <TrendingUp className="h-10 w-10 text-[#708238] mr-3" />
          <h1 className="font-manrope text-2xl font-bold text-white">
            Registro de Socio
          </h1>
        </div>

        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader className="space-y-1">
            <CardTitle className="text-xl font-manrope text-white">
              Únete como Socio Inversionista
            </CardTitle>
            <CardDescription className="text-[#A1A1AA]">
              Completa tus datos para comenzar a invertir
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Business Selection */}
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Negocio a invertir</Label>
                {loadingBusinesses ? (
                  <div className="h-10 bg-[#0D0D0D] rounded-md flex items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-[#708238]" />
                  </div>
                ) : (
                  <Select value={selectedBusiness} onValueChange={handleBusinessChange}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue placeholder="Selecciona el negocio" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {businesses.map((business) => (
                        <SelectItem 
                          key={business.id} 
                          value={business.id}
                          className="text-white hover:bg-[#27272A]"
                        >
                          {business.business_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              {/* Investment Amount */}
              <div className="p-4 bg-[#0D0D0D] rounded-lg border border-[#27272A]">
                <Label className="text-[#EDEDED] mb-3 block">Cantidad de Lotes</Label>
                <div className="flex items-center gap-4">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setLotsToBuy(Math.max(1, lotsToBuy - 1))}
                    className="bg-transparent border-[#27272A]"
                  >
                    -
                  </Button>
                  <span className="text-2xl font-bold text-white w-12 text-center">{lotsToBuy}</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setLotsToBuy(lotsToBuy + 1)}
                    className="bg-transparent border-[#27272A]"
                  >
                    +
                  </Button>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-[#71717A]">Inversión total:</p>
                    <p className="text-white font-bold text-lg">${totalInvestment.toLocaleString()} MXN</p>
                  </div>
                  <div>
                    <p className="text-[#71717A]">Participación:</p>
                    <p className="text-[#708238] font-bold text-lg">{participation.toFixed(2)}%</p>
                  </div>
                  <div>
                    <p className="text-[#71717A]">Rendimiento mensual:</p>
                    <p className="text-white font-bold">${monthlyReturn.toLocaleString()} MXN</p>
                  </div>
                  <div>
                    <p className="text-[#71717A]">Retorno total (4 años):</p>
                    <p className="text-[#708238] font-bold">${totalReturn.toLocaleString()} MXN</p>
                  </div>
                </div>
              </div>

              {/* Personal Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Nombre completo *</Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                    <Input
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      required
                      placeholder="Tu nombre"
                      className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Email *</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                    <Input
                      name="email"
                      type="email"
                      value={formData.email}
                      onChange={handleChange}
                      required
                      placeholder="tu@email.com"
                      className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Teléfono *</Label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                    <Input
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      required
                      placeholder="+52 55 1234 5678"
                      className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">CURP (opcional)</Label>
                  <Input
                    name="curp"
                    value={formData.curp}
                    onChange={handleChange}
                    placeholder="CURP"
                    maxLength={18}
                    className="bg-[#0D0D0D] border-[#27272A] text-white uppercase"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Dirección (opcional)</Label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    name="address"
                    value={formData.address}
                    onChange={handleChange}
                    placeholder="Calle, número, colonia, ciudad"
                    className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                  />
                </div>
              </div>

              {/* Bank Info */}
              <div className="pt-4 border-t border-[#27272A]">
                <h3 className="text-white font-bold mb-4">Datos Bancarios para Depósitos</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Banco *</Label>
                    <Select 
                      value={formData.bank_name} 
                      onValueChange={(v) => setFormData({...formData, bank_name: v})}
                    >
                      <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                        <SelectValue placeholder="Selecciona tu banco" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A] max-h-60">
                        {BANKS.map((bank) => (
                          <SelectItem 
                            key={bank} 
                            value={bank}
                            className="text-white hover:bg-[#27272A]"
                          >
                            {bank}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">CLABE Interbancaria *</Label>
                    <div className="relative">
                      <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      <Input
                        name="clabe"
                        value={formData.clabe}
                        onChange={handleChange}
                        required
                        placeholder="18 dígitos"
                        maxLength={18}
                        className="bg-[#0D0D0D] border-[#27272A] text-white pl-10 font-mono"
                      />
                    </div>
                    <p className="text-xs text-[#71717A]">{formData.clabe.length}/18 dígitos</p>
                  </div>
                </div>
              </div>

              {/* Password */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-[#27272A]">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Contraseña *</Label>
                  <div className="relative">
                    <Input
                      name="password"
                      type={showPassword ? "text" : "password"}
                      value={formData.password}
                      onChange={handleChange}
                      required
                      minLength={6}
                      placeholder="Mínimo 6 caracteres"
                      className="bg-[#0D0D0D] border-[#27272A] text-white pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#A1A1AA] hover:text-white"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Confirmar contraseña *</Label>
                  <Input
                    name="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    required
                    placeholder="Repite tu contraseña"
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold py-6"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Registrando...
                  </>
                ) : (
                  <>
                    Registrarme y Continuar al Pago
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 pt-6 border-t border-[#27272A] text-center">
              <p className="text-sm text-[#71717A]">
                ¿Ya eres socio?{" "}
                <Link to="/socios/login" className="text-[#708238] hover:underline">
                  Inicia sesión
                </Link>
              </p>
            </div>

            <div className="mt-4 text-center">
              <Link 
                to="/socios"
                className="text-sm text-[#71717A] hover:text-white flex items-center justify-center gap-1"
              >
                <ArrowLeft className="h-3 w-3" />
                Volver a información
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PartnersRegister;
