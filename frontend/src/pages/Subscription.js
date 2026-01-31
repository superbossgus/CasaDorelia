import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import axios from "axios";
import { Check, Crown, AlertTriangle, Loader2, CreditCard, Calendar, Store, ArrowRight } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const Subscription = () => {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [searchParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);

  useEffect(() => {
    if (!user) {
      navigate("/login");
      return;
    }
    fetchData();
    
    // Check for successful payment return
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      checkPaymentStatus(sessionId);
    }
  }, [user, navigate, searchParams]);

  const fetchData = async () => {
    try {
      const [plansRes, statusRes] = await Promise.all([
        axios.get(`${API}/api/plans`),
        axios.get(`${API}/api/tenants/subscription-status`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);
      setPlans(plansRes.data);
      setSubscriptionStatus(statusRes.data);
    } catch (error) {
      toast.error("Error al cargar información");
    } finally {
      setLoading(false);
    }
  };

  const checkPaymentStatus = async (sessionId) => {
    try {
      const response = await axios.get(
        `${API}/api/subscription/checkout/status/${sessionId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (response.data.payment_status === "paid") {
        toast.success("¡Pago exitoso! Tu suscripción ha sido activada.");
        fetchData();
      }
    } catch (error) {
      console.error("Error checking payment:", error);
    }
  };

  const handleCheckout = async (planId) => {
    setCheckoutLoading(planId);
    try {
      const response = await axios.post(
        `${API}/api/subscription/checkout`,
        {
          plan_id: planId,
          origin_url: window.location.origin
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url;
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al iniciar pago");
      setCheckoutLoading(null);
    }
  };

  const formatPrice = (price) => {
    return new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(price);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  const isTrial = subscriptionStatus?.is_trial;
  const isExpired = subscriptionStatus?.status === "suspended";
  const trialDaysLeft = subscriptionStatus?.trial_days_left || 0;

  return (
    <div className="min-h-screen bg-[#0D0D0D] py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Button 
            variant="ghost" 
            onClick={() => navigate("/dashboard")}
            className="text-[#A1A1AA] hover:text-white mb-4"
          >
            ← Volver al Dashboard
          </Button>
          <h1 className="text-3xl font-bold text-white font-manrope">Mi Suscripción</h1>
          <p className="text-[#A1A1AA]">Gestiona tu plan y facturación</p>
        </div>

        {/* Current Status Card */}
        <Card className={`mb-8 ${isExpired ? 'bg-red-950/20 border-red-500/30' : 'bg-[#161616] border-[#27272A]'}`}>
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={`p-3 rounded-lg ${isExpired ? 'bg-red-500/20' : isTrial ? 'bg-[#D97706]/20' : 'bg-[#708238]/20'}`}>
                  {isExpired ? (
                    <AlertTriangle className="h-6 w-6 text-red-400" />
                  ) : (
                    <Crown className={`h-6 w-6 ${isTrial ? 'text-[#D97706]' : 'text-[#708238]'}`} />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-semibold text-white">
                      {subscriptionStatus?.plan_name || "Plan Básico"}
                    </h2>
                    <Badge className={
                      isExpired ? 'bg-red-500 text-white' :
                      isTrial ? 'bg-[#D97706] text-white' :
                      'bg-[#708238] text-white'
                    }>
                      {isExpired ? 'Expirado' : isTrial ? 'Prueba' : 'Activo'}
                    </Badge>
                  </div>
                  <p className="text-[#A1A1AA] text-sm">
                    {isExpired ? (
                      "Tu período de prueba ha terminado. Suscríbete para continuar."
                    ) : isTrial ? (
                      `Te quedan ${trialDaysLeft} días de prueba`
                    ) : (
                      `Vence el ${formatDate(subscriptionStatus?.subscription_ends_at)}`
                    )}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-6">
                <div className="text-center">
                  <div className="flex items-center gap-2 text-[#708238]">
                    <Store className="h-4 w-4" />
                    <span className="text-2xl font-bold text-white">
                      {subscriptionStatus?.current_branches || 0}
                    </span>
                    <span className="text-[#71717A]">/ {subscriptionStatus?.max_branches}</span>
                  </div>
                  <p className="text-xs text-[#71717A]">Sucursales</p>
                </div>
              </div>
            </div>

            {isTrial && !isExpired && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="text-[#A1A1AA]">Días restantes de prueba</span>
                  <span className="text-[#D97706] font-medium">{trialDaysLeft} días</span>
                </div>
                <Progress value={(trialDaysLeft / 7) * 100} className="h-2 bg-[#27272A]" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Plans */}
        <h2 className="text-xl font-semibold text-white mb-4">
          {isExpired || isTrial ? "Elige tu plan" : "Cambiar plan"}
        </h2>
        
        <div className="grid md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          {plans.map((plan, index) => {
            const isCurrentPlan = subscriptionStatus?.plan_id === plan.plan_id && !isTrial && !isExpired;
            const isPopular = index === 2;
            
            return (
              <Card 
                key={plan.plan_id} 
                className={`bg-[#161616] border-[#27272A] ${isPopular ? 'ring-2 ring-[#708238]' : ''} ${isCurrentPlan ? 'ring-2 ring-[#708238]/50' : ''}`}
              >
                <CardHeader className="pb-2">
                  {isPopular && (
                    <Badge className="bg-[#708238] text-white w-fit mb-2">Popular</Badge>
                  )}
                  {isCurrentPlan && (
                    <Badge className="bg-[#708238]/20 text-[#708238] w-fit mb-2">Tu plan actual</Badge>
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
                    <li className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-[#708238]" />
                      Alertas de inventario
                    </li>
                  </ul>
                  <Button 
                    onClick={() => handleCheckout(plan.plan_id)}
                    disabled={checkoutLoading === plan.plan_id || isCurrentPlan}
                    className={`w-full ${isCurrentPlan ? 'bg-[#27272A] text-[#71717A]' : 'bg-[#708238] hover:bg-[#5a692d] text-white'}`}
                  >
                    {checkoutLoading === plan.plan_id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Procesando...
                      </>
                    ) : isCurrentPlan ? (
                      "Plan actual"
                    ) : (
                      <>
                        <CreditCard className="h-4 w-4 mr-2" />
                        Suscribirse
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Info */}
        <Card className="bg-[#161616] border-[#27272A]">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Información importante</h3>
            <ul className="space-y-2 text-sm text-[#A1A1AA]">
              <li className="flex items-start gap-2">
                <Check className="h-4 w-4 text-[#708238] mt-0.5" />
                Todos los pagos son procesados de forma segura por Stripe
              </li>
              <li className="flex items-start gap-2">
                <Check className="h-4 w-4 text-[#708238] mt-0.5" />
                Puedes cambiar de plan en cualquier momento
              </li>
              <li className="flex items-start gap-2">
                <Check className="h-4 w-4 text-[#708238] mt-0.5" />
                La suscripción se renueva automáticamente cada mes
              </li>
              <li className="flex items-start gap-2">
                <Check className="h-4 w-4 text-[#708238] mt-0.5" />
                Cancela cuando quieras sin penalización
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Subscription;
