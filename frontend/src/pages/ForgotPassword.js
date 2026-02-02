import { useState, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { toast } from "sonner";
import { ArrowLeft, Mail, Loader2, KeyRound, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ForgotPassword = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(1); // 1: email, 2: code + password, 3: success
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Check if token is in URL (from email link)
  useEffect(() => {
    const tokenFromUrl = searchParams.get('token');
    if (tokenFromUrl) {
      setCode(tokenFromUrl);
      setStep(2);
    }
  }, [searchParams]);

  const handleRequestReset = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await axios.post(`${API}/auth/forgot-password`, { 
        email,
        origin_url: window.location.origin 
      });
      toast.success("Si el correo existe, recibirás un código de recuperación");
      setStep(2);
    } catch (error) {
      toast.error("Error al procesar la solicitud");
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      toast.error("Las contraseñas no coinciden");
      return;
    }

    if (newPassword.length < 6) {
      toast.error("La contraseña debe tener al menos 6 caracteres");
      return;
    }

    setIsLoading(true);

    try {
      const response = await axios.post(`${API}/auth/reset-password`, {
        token: code,
        new_password: newPassword
      });
      
      if (response.data.success) {
        toast.success("Contraseña actualizada correctamente");
        setStep(3);
      }
    } catch (error) {
      const message = error.response?.data?.detail || "Error al restablecer la contraseña";
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

      {/* Right side - Form */}
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
              <div className="flex items-center gap-2 mb-2">
                <Link 
                  to="/login" 
                  className="text-[#A1A1AA] hover:text-white transition-colors"
                  data-testid="back-to-login-link"
                >
                  <ArrowLeft className="h-5 w-5" />
                </Link>
                <CardTitle className="text-2xl font-manrope text-white">
                  {step === 1 && "Recuperar Contraseña"}
                  {step === 2 && "Ingresa el Código"}
                  {step === 3 && "¡Listo!"}
                </CardTitle>
              </div>
              <CardDescription className="text-[#A1A1AA]">
                {step === 1 && "Ingresa tu correo electrónico para recibir un código de recuperación"}
                {step === 2 && "Revisa tu correo e ingresa el código junto con tu nueva contraseña"}
                {step === 3 && "Tu contraseña ha sido actualizada correctamente"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Step 1: Request Email */}
              {step === 1 && (
                <form onSubmit={handleRequestReset} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-[#EDEDED]">Correo Electrónico</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="tu@email.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        data-testid="forgot-email-input"
                        className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] focus:border-[#708238] pl-10"
                      />
                    </div>
                  </div>
                  <Button
                    type="submit"
                    disabled={isLoading}
                    data-testid="request-reset-button"
                    className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold transition-all duration-200"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Enviando...
                      </>
                    ) : (
                      "Enviar Código de Recuperación"
                    )}
                  </Button>
                </form>
              )}

              {/* Step 2: Enter Code and New Password */}
              {step === 2 && (
                <form onSubmit={handleResetPassword} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="code" className="text-[#EDEDED]">Código de Recuperación</Label>
                    <div className="relative">
                      <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
                      <Input
                        id="code"
                        type="text"
                        placeholder="Pega el código aquí"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        required
                        data-testid="reset-code-input"
                        className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] focus:border-[#708238] pl-10 font-mono"
                      />
                    </div>
                    <p className="text-xs text-[#71717A]">
                      Revisa tu correo ({email}) y pega el código que recibiste
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="newPassword" className="text-[#EDEDED]">Nueva Contraseña</Label>
                    <div className="relative">
                      <Input
                        id="newPassword"
                        type={showPassword ? "text" : "password"}
                        placeholder="Mínimo 6 caracteres"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        required
                        minLength={6}
                        data-testid="new-password-input"
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

                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword" className="text-[#EDEDED]">Confirmar Contraseña</Label>
                    <Input
                      id="confirmPassword"
                      type={showPassword ? "text" : "password"}
                      placeholder="Repite tu contraseña"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      minLength={6}
                      data-testid="confirm-password-input"
                      className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B] focus:border-[#708238]"
                    />
                  </div>

                  <Button
                    type="submit"
                    disabled={isLoading}
                    data-testid="reset-password-button"
                    className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold transition-all duration-200"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Actualizando...
                      </>
                    ) : (
                      "Restablecer Contraseña"
                    )}
                  </Button>

                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => setStep(1)}
                    className="w-full text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
                  >
                    Solicitar nuevo código
                  </Button>
                </form>
              )}

              {/* Step 3: Success */}
              {step === 3 && (
                <div className="text-center space-y-6">
                  <div className="flex justify-center">
                    <div className="bg-[#708238]/20 rounded-full p-4">
                      <CheckCircle2 className="h-12 w-12 text-[#708238]" />
                    </div>
                  </div>
                  <p className="text-[#A1A1AA]">
                    Tu contraseña ha sido actualizada. Ya puedes iniciar sesión con tu nueva contraseña.
                  </p>
                  <Button
                    onClick={() => navigate("/login")}
                    data-testid="go-to-login-button"
                    className="w-full bg-[#708238] hover:bg-[#5a692d] text-white font-semibold transition-all duration-200"
                  >
                    Ir a Iniciar Sesión
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
