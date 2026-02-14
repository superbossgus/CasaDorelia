import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { CheckCircle2, Loader2, TrendingUp } from "lucide-react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const PartnersPurchaseSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState(false);

  const purchaseId = searchParams.get("purchase_id");
  const partnerToken = localStorage.getItem("partner_token");

  useEffect(() => {
    if (!partnerToken) {
      navigate("/socios/login");
      return;
    }
    
    // Give Stripe webhook time to process
    const timer = setTimeout(() => {
      setLoading(false);
      setSuccess(true);
    }, 2000);

    return () => clearTimeout(timer);
  }, [partnerToken, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-[#708238] mx-auto mb-4" />
          <p className="text-white">Procesando tu compra...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
      <Card className="bg-[#161616] border-[#27272A] max-w-md w-full">
        <CardContent className="pt-8 pb-6 text-center">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle2 className="h-10 w-10 text-green-400" />
          </div>
          
          <h1 className="text-2xl font-bold text-white mb-2">
            ¡Compra Exitosa!
          </h1>
          
          <p className="text-[#A1A1AA] mb-6">
            Tu inversión ha sido procesada correctamente. Ahora eres parte de la familia Doré.
          </p>
          
          <div className="bg-[#0D0D0D] p-4 rounded-lg border border-[#27272A] mb-6">
            <p className="text-[#71717A] text-sm mb-2">Referencia de compra:</p>
            <p className="text-[#708238] font-mono text-sm break-all">{purchaseId}</p>
          </div>
          
          <div className="space-y-3">
            <Button
              onClick={() => navigate("/socios/dashboard")}
              className="w-full bg-[#708238] hover:bg-[#5a692d]"
            >
              <TrendingUp className="h-4 w-4 mr-2" />
              Ver mi Dashboard
            </Button>
            
            <p className="text-xs text-[#71717A]">
              Recibirás un correo de confirmación con los detalles de tu inversión.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PartnersPurchaseSuccess;
