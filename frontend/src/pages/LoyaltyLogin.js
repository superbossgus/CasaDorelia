import { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Gift, Loader2, Eye, EyeOff, ArrowLeft } from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const LoyaltyLogin = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingBusinesses, setLoadingBusinesses] = useState(true);

  useEffect(() => {
    fetchBusinesses();
    // Check if business is pre-selected from URL
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!selectedBusiness) {
      toast.error("Selecciona un negocio");
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/api/loyalty/login`, {
        email,
        password,
        tenant_id: selectedBusiness
      });

      localStorage.setItem("loyalty_token", response.data.token);
      toast.success("¡Bienvenido de vuelta!");
      navigate("/loyalty/rewards");
    } catch (error) {
      const message = error.response?.data?.detail || "Error al iniciar sesión";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedBusinessData = businesses.find(b => b.id === selectedBusiness);

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
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
              Iniciar Sesión
            </CardTitle>
            <CardDescription className="text-[#A1A1AA]">
              Accede a tu cuenta para ver tus puntos y recompensas
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
                <Label htmlFor="email" className="text-[#EDEDED]">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="tu@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B]"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-[#EDEDED]">Contraseña</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
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

              <Button
                type="submit"
                disabled={isLoading}
                className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Iniciando...
                  </>
                ) : (
                  "Iniciar Sesión"
                )}
              </Button>
            </form>

            <div className="mt-6 pt-6 border-t border-[#27272A] text-center">
              <p className="text-sm text-[#71717A]">
                ¿No tienes cuenta?{" "}
                <Link 
                  to={`/loyalty/register${selectedBusiness ? `?business=${selectedBusiness}` : ""}`}
                  className="text-[#708238] hover:underline"
                >
                  Regístrate aquí
                </Link>
              </p>
            </div>

            <div className="mt-4 text-center">
              <Link 
                to="/login"
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

export default LoyaltyLogin;
