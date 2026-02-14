import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { toast } from "sonner";
import { TrendingUp, Loader2, Eye, EyeOff, ArrowLeft, Mail } from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const PartnersLogin = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/api/partners/login`, {
        email,
        password
      });

      localStorage.setItem("partner_token", response.data.token);
      toast.success("¡Bienvenido de vuelta!");
      navigate("/socios/dashboard");
    } catch (error) {
      const message = error.response?.data?.detail || "Credenciales inválidas";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex items-center justify-center mb-8">
          <TrendingUp className="h-10 w-10 text-[#708238] mr-3" />
          <h1 className="font-manrope text-2xl font-bold text-white">
            Portal de Socios
          </h1>
        </div>

        <Card className="bg-[#161616] border-[#27272A]">
          <CardHeader className="space-y-1">
            <CardTitle className="text-xl font-manrope text-white">
              Iniciar Sesión
            </CardTitle>
            <CardDescription className="text-[#A1A1AA]">
              Accede a tu cuenta de socio inversionista
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-[#EDEDED]">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="tu@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] pl-10"
                  />
                </div>
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
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#A1A1AA] hover:text-white transition-colors"
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
                ¿Aún no eres socio?{" "}
                <Link to="/socios/registro" className="text-[#708238] hover:underline">
                  Regístrate aquí
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

export default PartnersLogin;
