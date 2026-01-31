import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import axios from "axios";
import { CheckCircle, Loader2, ArrowRight } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const SubscriptionSuccess = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState("checking");
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      pollPaymentStatus(sessionId);
    } else {
      navigate("/subscription");
    }
  }, [searchParams]);

  const pollPaymentStatus = async (sessionId) => {
    if (attempts >= 5) {
      setStatus("timeout");
      return;
    }

    try {
      const response = await axios.get(
        `${API}/api/subscription/checkout/status/${sessionId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.data.payment_status === "paid") {
        setStatus("success");
        toast.success("¡Suscripción activada!");
      } else if (response.data.status === "expired") {
        setStatus("expired");
      } else {
        setAttempts(prev => prev + 1);
        setTimeout(() => pollPaymentStatus(sessionId), 2000);
      }
    } catch (error) {
      console.error("Error:", error);
      setAttempts(prev => prev + 1);
      setTimeout(() => pollPaymentStatus(sessionId), 2000);
    }
  };

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <Card className="bg-[#161616] border-[#27272A] w-full max-w-md">
        <CardContent className="p-8 text-center">
          {status === "checking" && (
            <>
              <Loader2 className="h-16 w-16 animate-spin text-[#708238] mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-white mb-2">Verificando pago...</h2>
              <p className="text-[#A1A1AA]">Por favor espera mientras confirmamos tu suscripción</p>
            </>
          )}

          {status === "success" && (
            <>
              <div className="w-16 h-16 rounded-full bg-[#708238]/20 flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="h-10 w-10 text-[#708238]" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">¡Pago exitoso!</h2>
              <p className="text-[#A1A1AA] mb-6">Tu suscripción ha sido activada correctamente</p>
              <Button 
                onClick={() => navigate("/dashboard")}
                className="bg-[#708238] hover:bg-[#5a692d] text-white"
              >
                Ir al Dashboard
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </>
          )}

          {status === "expired" && (
            <>
              <h2 className="text-xl font-semibold text-white mb-2">Sesión expirada</h2>
              <p className="text-[#A1A1AA] mb-4">La sesión de pago ha expirado</p>
              <Button 
                onClick={() => navigate("/subscription")}
                className="bg-[#708238] hover:bg-[#5a692d] text-white"
              >
                Intentar de nuevo
              </Button>
            </>
          )}

          {status === "timeout" && (
            <>
              <h2 className="text-xl font-semibold text-white mb-2">Verificación pendiente</h2>
              <p className="text-[#A1A1AA] mb-4">
                No pudimos confirmar el pago. Si realizaste el pago, tu suscripción se activará pronto.
              </p>
              <Button 
                onClick={() => navigate("/dashboard")}
                className="bg-[#708238] hover:bg-[#5a692d] text-white"
              >
                Ir al Dashboard
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionSuccess;
