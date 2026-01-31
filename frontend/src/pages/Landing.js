import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { Coffee, Check, ArrowRight, Store, Users, BarChart3, Loader2, Sparkles } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const Landing = () => {
  const navigate = useNavigate();
  const { login, user } = useAuth();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [formData, setFormData] = useState({
    business_name: "",
    owner_name: "",
    owner_email: "",
    owner_password: "",
    phone: ""
  });

  useEffect(() => {
    if (user) {
      navigate("/dashboard");
    }
    fetchPlans();
  }, [user, navigate]);

  const fetchPlans = async () => {
    try {
      const response = await axios.get(`${API}/api/plans`);
      setPlans(response.data);
    } catch (error) {
      console.error("Error fetching plans:", error);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/api/tenants/register`, formData);
      toast.success("¡Negocio registrado exitosamente!");
      
      // Auto login
      login(response.data.token, response.data.user);
      navigate("/dashboard");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al registrar");
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: Store, title: "Multi-Sucursal", description: "Gestiona hasta 20 sucursales desde una sola cuenta" },
    { icon: BarChart3, title: "Reportes en Tiempo Real", description: "Dashboard con KPIs, ventas y utilidades" },
    { icon: Users, title: "Gestión de Usuarios", description: "Roles de Admin, Gerente y Cajero" },
  ];

  const formatPrice = (price) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(price);
  };

  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Header */}
      <header className="border-b border-[#27272A] bg-[#0D0D0D]/95 backdrop-blur sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#708238] flex items-center justify-center">
              <Coffee className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white font-manrope">Doré</span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login">
              <Button variant="ghost" className="text-[#A1A1AA] hover:text-white">
                Iniciar Sesión
              </Button>
            </Link>
            <Button 
              onClick={() => setShowRegister(true)}
              className="bg-[#708238] hover:bg-[#5a692d] text-white"
            >
              Comenzar Gratis
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-20 text-center">
        <Badge className="bg-[#708238]/20 text-[#708238] mb-6">
          <Sparkles className="h-3 w-3 mr-1" />
          7 días de prueba gratis
        </Badge>
        <h1 className="text-4xl md:text-6xl font-bold text-white mb-6 font-manrope">
          Gestiona tu Cafetería<br />
          <span className="text-[#708238]">de Forma Inteligente</span>
        </h1>
        <p className="text-xl text-[#A1A1AA] mb-8 max-w-2xl mx-auto">
          Sistema completo para controlar ventas, inventario, costos y utilidades. 
          Ideal para cafeterías con una o múltiples sucursales.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Button 
            size="lg"
            onClick={() => setShowRegister(true)}
            className="bg-[#708238] hover:bg-[#5a692d] text-white text-lg px-8"
          >
            Comenzar Prueba Gratis
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <Card key={index} className="bg-[#161616] border-[#27272A]">
                <CardContent className="p-6">
                  <div className="w-12 h-12 rounded-lg bg-[#708238]/20 flex items-center justify-center mb-4">
                    <Icon className="h-6 w-6 text-[#708238]" />
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                  <p className="text-[#A1A1AA]">{feature.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="container mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-white text-center mb-4 font-manrope">
          Planes y Precios
        </h2>
        <p className="text-[#A1A1AA] text-center mb-12">
          Elige el plan que mejor se adapte a tu negocio
        </p>
        
        <div className="grid md:grid-cols-3 lg:grid-cols-5 gap-4">
          {plans.map((plan, index) => (
            <Card 
              key={plan.plan_id} 
              className={`bg-[#161616] border-[#27272A] ${index === 2 ? 'ring-2 ring-[#708238]' : ''}`}
            >
              <CardHeader className="pb-2">
                {index === 2 && (
                  <Badge className="bg-[#708238] text-white w-fit mb-2">Popular</Badge>
                )}
                <CardTitle className="text-white text-lg">{plan.name}</CardTitle>
                <CardDescription className="text-[#71717A]">
                  Hasta {plan.max_branches} {plan.max_branches === 1 ? 'sucursal' : 'sucursales'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-white">{formatPrice(plan.price)}</span>
                  <span className="text-[#71717A]">/mes</span>
                </div>
                <ul className="space-y-2 text-sm text-[#A1A1AA] mb-4">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-[#708238]" />
                    Usuarios ilimitados
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-[#708238]" />
                    Soporte por WhatsApp
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-[#708238]" />
                    Reportes completos
                  </li>
                </ul>
                <Button 
                  onClick={() => setShowRegister(true)}
                  className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
                  variant={index === 2 ? "default" : "outline"}
                >
                  Comenzar
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Register Modal/Section */}
      {showRegister && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <Card className="bg-[#161616] border-[#27272A] w-full max-w-md">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white font-manrope">Crear Cuenta</CardTitle>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => setShowRegister(false)}
                  className="text-[#71717A] hover:text-white"
                >
                  ✕
                </Button>
              </div>
              <CardDescription className="text-[#A1A1AA]">
                Comienza tu prueba gratis de 7 días
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Nombre del Negocio</Label>
                  <Input
                    value={formData.business_name}
                    onChange={(e) => setFormData({...formData, business_name: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Mi Cafetería"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Tu Nombre</Label>
                  <Input
                    value={formData.owner_name}
                    onChange={(e) => setFormData({...formData, owner_name: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Juan Pérez"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Email</Label>
                  <Input
                    type="email"
                    value={formData.owner_email}
                    onChange={(e) => setFormData({...formData, owner_email: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="correo@ejemplo.com"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Contraseña</Label>
                  <Input
                    type="password"
                    value={formData.owner_password}
                    onChange={(e) => setFormData({...formData, owner_password: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="••••••••"
                    required
                    minLength={6}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Teléfono (opcional)</Label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="+52 55 1234 5678"
                  />
                </div>
                <Button 
                  type="submit" 
                  disabled={loading}
                  className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Registrando...
                    </>
                  ) : (
                    <>
                      Comenzar Prueba Gratis
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
                <p className="text-xs text-[#71717A] text-center">
                  Al registrarte aceptas nuestros términos y condiciones
                </p>
              </form>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-[#27272A] py-8 mt-16">
        <div className="container mx-auto px-4 text-center text-[#71717A]">
          <p>© 2026 Doré. Sistema de Gestión para Cafeterías.</p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
