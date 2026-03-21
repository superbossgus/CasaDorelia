import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { Coffee, Eye, EyeOff, Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Google icon SVG component
const GoogleIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24">
    <path
      fill="#4285F4"
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <path
      fill="#34A853"
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <path
      fill="#FBBC05"
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <path
      fill="#EA4335"
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </svg>
);

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
      const userData = await login(email, password);
      toast.success("¡Bienvenido!");
      
      // Redirect based on role
      if (userData?.role === "superadmin") {
        navigate("/superadmin");
      } else {
        navigate("/dashboard");
      }
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
          <div className="flex items-center gap-4 mb-4 animate-fade-in">
            <img 
              src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
              alt="Doré" 
              className="h-16 w-auto"
            />
            <h1 className="font-manrope text-5xl font-bold">
              Doré
            </h1>
          </div>
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
            <img 
              src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
              alt="Doré" 
              className="h-12 w-auto mr-3"
            />
            <h1 className="font-manrope text-3xl font-bold text-white">
              Doré
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
                  <div className="flex justify-end">
                    <Link 
                      to="/admin/forgot-password" 
                      className="text-sm text-[#708238] hover:text-[#8a9f4a] transition-colors"
                      data-testid="forgot-password-link"
                    >
                      ¿Olvidaste tu contraseña?
                    </Link>
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

              {/* Google OAuth Section */}
              <div className="mt-6 pt-6 border-t border-[#27272A]">
                <div className="relative flex items-center justify-center mb-4">
                  <span className="absolute inset-x-0 h-px bg-[#27272A]" />
                  <span className="relative bg-[#161616] px-3 text-sm text-[#71717A]">
                    O continúa con
                  </span>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
                    const redirectUrl = window.location.origin + '/dashboard';
                    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
                  }}
                  data-testid="google-login-button"
                  className="w-full bg-white hover:bg-gray-100 text-gray-800 border-gray-300 font-medium transition-all duration-200 flex items-center justify-center gap-3"
                >
                  <GoogleIcon />
                  Continuar con Google
                </Button>
              </div>

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
