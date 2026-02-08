import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Gift, Loader2, Eye, EyeOff, ArrowLeft, Cake, Phone, Mail, User } from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const LoyaltyRegister = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState("");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
    birthday: ""
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingBusinesses, setLoadingBusinesses] = useState(true);

  useEffect(() => {
    fetchBusinesses();
    const businessId = searchParams.get("business");
    if (businessId) {
      setSelectedBusiness(businessId);
    }
  }, [searchParams]);

  const fetchBusinesses = async () => {
    try {
      const response = await axios.get(`${API}/api/loyalty/businesses`);
      setBusinesses(response.data);
    } catch (error) {
      console.error("Error fetching businesses:", error);
    } finally {
      setLoadingBusinesses(false);
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
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

    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/api/loyalty/register?tenant_id=${selectedBusiness}`, {
        name: formData.name,
        email: formData.email,
        phone: formData.phone || null,
        password: formData.password,
        birthday: formData.birthday || null
      });

      localStorage.setItem("loyalty_token", response.data.token);
      toast.success(`¡Bienvenido! Recibiste ${response.data.welcome_bonus} puntos de bienvenida`);
      navigate("/loyalty/rewards");
    } catch (error) {
      const message = error.response?.data?.detail || "Error al registrarse";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedBusinessData = businesses.find(b => b.id === selectedBusiness);

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4 py-8">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-8">
          <Gift className="h-10 w-10 text-[#708238] mr-3" />
          <h1 className="font-manrope text-2xl font-bold text-white">
            Programa de Lealtad
          </h1>
        </div>

        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader className="space-y-1">
            <CardTitle className="text-xl font-manrope text-white">
              Crear Cuenta
            </CardTitle>
            <CardDescription className="text-[#A1A1AA]">
              Únete al programa de lealtad y comienza a acumular puntos
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Negocio</Label>
                {loadingBusinesses ? (
                  <div className="h-10 bg-[#0D0D0D] rounded-md flex items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-[#708238]" />
                  </div>
                ) : (
                  <Select value={selectedBusiness} onValueChange={setSelectedBusiness}>
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
                          <div className="flex items-center gap-2">
                            {business.logo_url && (
                              <img 
                                src={`${API}${business.logo_url}`} 
                                alt="" 
                                className="h-5 w-5 object-contain"
                              />
                            )}
                            {business.business_name}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="name" className="text-[#EDEDED]">Nombre completo</Label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    placeholder="Tu nombre"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] pl-10"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email" className="text-[#EDEDED]">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="tu@email.com"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] pl-10"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="phone" className="text-[#EDEDED]">
                  Teléfono <span className="text-[#71717A]">(opcional)</span>
                </Label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    id="phone"
                    name="phone"
                    type="tel"
                    placeholder="+52 55 1234 5678"
                    value={formData.phone}
                    onChange={handleChange}
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] pl-10"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="birthday" className="text-[#EDEDED]">
                  Fecha de nacimiento <span className="text-[#71717A]">(para regalo de cumpleaños)</span>
                </Label>
                <div className="relative">
                  <Cake className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    id="birthday"
                    name="birthday"
                    type="date"
                    value={formData.birthday}
                    onChange={handleChange}
                    className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-[#EDEDED]">Contraseña</Label>
                <div className="relative">
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Mínimo 6 caracteres"
                    value={formData.password}
                    onChange={handleChange}
                    required
                    minLength={6}
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] pr-10"
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
                <Label htmlFor="confirmPassword" className="text-[#EDEDED]">Confirmar contraseña</Label>
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showPassword ? "text" : "password"}
                  placeholder="Repite tu contraseña"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B]"
                />
              </div>

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Registrando...
                  </>
                ) : (
                  "Crear Cuenta"
                )}
              </Button>

              <p className="text-xs text-[#71717A] text-center">
                Al registrarte, recibirás 10 puntos de bienvenida
              </p>
            </form>

            <div className="mt-6 pt-6 border-t border-[#27272A] text-center">
              <p className="text-sm text-[#71717A]">
                ¿Ya tienes cuenta?{" "}
                <Link 
                  to={`/loyalty/login${selectedBusiness ? `?business=${selectedBusiness}` : ""}`}
                  className="text-[#708238] hover:underline"
                >
                  Inicia sesión
                </Link>
              </p>
            </div>

            <div className="mt-4 text-center">
              <Link 
                to="/admin"
                className="text-sm text-[#71717A] hover:text-white flex items-center justify-center gap-1"
              >
                <ArrowLeft className="h-3 w-3" />
                Acceso para empleados
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LoyaltyRegister;
