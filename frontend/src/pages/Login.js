import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { Coffee, Eye, EyeOff, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate("/dashboard");
    }
  }, [user, navigate]);

  const handleSeed = async () => {
    setIsSeeding(true);
    try {
      const response = await axios.post(`${API}/seed`);
      if (response.data.admin_credentials) {
        setEmail(response.data.admin_credentials.email);
        setPassword(response.data.admin_credentials.password);
        toast.success("Datos de prueba creados. Credenciales prellenadas.");
      } else {
        toast.info(response.data.message);
      }
    } catch (error) {
      toast.error("Error al crear datos de prueba");
    } finally {
      setIsSeeding(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      await login(email, password);
      toast.success("¡Bienvenido!");
      navigate("/dashboard");
    } catch (error) {
      const message = error.response?.data?.detail || "Error al iniciar sesión";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex">
      {/* Left side - Hero image */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div 
          className="absolute inset-0 bg-cover bg-center"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1735910626330-25ce60e05e84?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjV8MHwxfHNlYXJjaHwyfHxjb2ZmZWUlMjBzaG9wJTIwaW50ZXJpb3IlMjBtb2Rlcm4lMjBkYXJrfGVufDB8fHx8MTc2OTYxNzA3OXww&ixlib=rb-4.1.0&q=85')`
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#0D0D0D] via-[#0D0D0D]/60 to-transparent" />
        <div className="relative z-10 flex flex-col justify-end p-12 text-white">
          <h1 className="font-manrope text-5xl font-bold mb-4 animate-fade-in">
            Café<span className="text-[#708238]">Control</span>
          </h1>
          <p className="text-lg text-[#A1A1AA] max-w-md animate-fade-in stagger-1">
            Sistema integral de gestión para tus cafeterías. Controla ventas, inventario, costos y más.
          </p>
        </div>
      </div>

      {/* Right side - Login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center justify-center mb-8">
            <Coffee className="h-10 w-10 text-[#708238] mr-3" />
            <h1 className="font-manrope text-3xl font-bold text-white">
              Café<span className="text-[#708238]">Control</span>
            </h1>
          </div>

          <Card className="bg-[#161616] border-[#27272A] animate-fade-in">
            <CardHeader className="space-y-1">
              <CardTitle className="text-2xl font-manrope text-white">
                Iniciar Sesión
              </CardTitle>
              <CardDescription className="text-[#A1A1AA]">
                Ingresa tus credenciales para acceder al sistema
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-[#EDEDED]">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="admin@cafecontrol.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    data-testid="login-email-input"
                    className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] focus:border-[#708238]"
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
                      data-testid="login-password-input"
                      className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] focus:border-[#708238] pr-10"
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
                  data-testid="login-submit-button"
                  className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold transition-all duration-200"
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

              <div className="mt-6 pt-6 border-t border-[#27272A]">
                <p className="text-sm text-[#71717A] text-center mb-3">
                  ¿Primera vez? Crea datos de prueba
                </p>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSeed}
                  disabled={isSeeding}
                  data-testid="seed-data-button"
                  className="w-full bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white transition-all duration-200"
                >
                  {isSeeding ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creando datos...
                    </>
                  ) : (
                    "Crear Datos de Prueba"
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Login;
