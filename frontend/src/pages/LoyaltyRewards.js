import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import axios from "axios";
import { 
  Gift, Star, Trophy, Coffee, Ticket, QrCode, 
  ChevronRight, Loader2, Sparkles, Crown, Medal,
  Calendar, Clock, CheckCircle2
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

// Level icons and colors
const LEVEL_CONFIG = {
  bronce: { icon: Coffee, color: "text-amber-600", bg: "bg-amber-600/20", border: "border-amber-600/50" },
  plata: { icon: Star, color: "text-slate-300", bg: "bg-slate-300/20", border: "border-slate-300/50" },
  oro: { icon: Crown, color: "text-yellow-400", bg: "bg-yellow-400/20", border: "border-yellow-400/50" }
};

const LoyaltyRewards = () => {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [redeeming, setRedeeming] = useState(null);
  const [showScanner, setShowScanner] = useState(false);

  // Get loyalty token from localStorage
  const loyaltyToken = localStorage.getItem("loyalty_token");

  useEffect(() => {
    if (loyaltyToken) {
      fetchDashboard();
    } else {
      setLoading(false);
    }
  }, [loyaltyToken]);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/api/loyalty/dashboard`, {
        headers: { Authorization: `Bearer ${loyaltyToken}` }
      });
      setDashboard(response.data);
    } catch (error) {
      console.error("Error fetching dashboard:", error);
      if (error.response?.status === 401) {
        localStorage.removeItem("loyalty_token");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRedeem = async (rewardId) => {
    setRedeeming(rewardId);
    try {
      const response = await axios.post(
        `${API}/api/loyalty/redeem?reward_id=${rewardId}`,
        {},
        { headers: { Authorization: `Bearer ${loyaltyToken}` } }
      );
      toast.success(response.data.message);
      fetchDashboard(); // Refresh data
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al canjear recompensa");
    } finally {
      setRedeeming(null);
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString("es-MX", {
      day: "numeric",
      month: "short",
      year: "numeric"
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  if (!loyaltyToken || !dashboard) {
    return (
      <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center p-4">
        <Card className="bg-[#161616] border-[#27272A] max-w-md w-full">
          <CardContent className="pt-6 text-center">
            <Gift className="h-16 w-16 mx-auto text-[#708238] mb-4" />
            <h2 className="text-2xl font-bold text-white mb-2">Programa de Lealtad</h2>
            <p className="text-[#A1A1AA] mb-6">
              Inicia sesión para ver tus recompensas y acumular puntos
            </p>
            <Button 
              onClick={() => window.location.href = "/loyalty/login"}
              className="w-full bg-[#708238] hover:bg-[#5a692d]"
            >
              Iniciar Sesión
            </Button>
            <p className="mt-4 text-sm text-[#71717A]">
              ¿No tienes cuenta?{" "}
              <a href="/loyalty/register" className="text-[#708238] hover:underline">
                Regístrate
              </a>
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { customer, level_info, next_level, points_to_next_level, all_rewards, active_coupons, recent_transactions } = dashboard;
  const LevelIcon = LEVEL_CONFIG[customer.current_level]?.icon || Coffee;
  const levelConfig = LEVEL_CONFIG[customer.current_level] || LEVEL_CONFIG.bronce;

  // Calculate progress to next level
  const progressPercent = next_level 
    ? ((customer.total_points - (LEVEL_CONFIG[customer.current_level === "bronce" ? "bronce" : customer.current_level === "plata" ? "plata" : "oro"].min_points || 0)) / 
       (next_level.min_points - (level_info.min_points || 0))) * 100
    : 100;

  return (
    <div className="min-h-screen bg-[#0D0D0D] pb-20">
      {/* Header */}
      <div className="bg-gradient-to-b from-[#1a1a1a] to-[#0D0D0D] pt-8 pb-6 px-4">
        <div className="max-w-lg mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div>
              <p className="text-[#A1A1AA] text-sm">¡Hola!</p>
              <h1 className="text-xl font-bold text-white">{customer.name}</h1>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowScanner(true)}
              className="bg-transparent border-[#708238] text-[#708238] hover:bg-[#708238]/20"
            >
              <QrCode className="h-4 w-4 mr-2" />
              Escanear
            </Button>
          </div>

          {/* Points Card */}
          <Card className={`${levelConfig.bg} ${levelConfig.border} border-2`}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`p-3 rounded-full ${levelConfig.bg}`}>
                    <LevelIcon className={`h-6 w-6 ${levelConfig.color}`} />
                  </div>
                  <div>
                    <p className="text-sm text-[#A1A1AA]">Nivel {level_info.icon}</p>
                    <p className={`font-bold text-lg ${levelConfig.color}`}>{level_info.name}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold text-white">{customer.total_points}</p>
                  <p className="text-sm text-[#A1A1AA]">puntos</p>
                </div>
              </div>

              {next_level && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-[#A1A1AA]">Siguiente nivel: {next_level.name}</span>
                    <span className="text-white">{points_to_next_level} pts más</span>
                  </div>
                  <Progress value={Math.min(progressPercent, 100)} className="h-2" />
                </div>
              )}

              {customer.current_level === "oro" && (
                <div className="mt-4 p-3 bg-yellow-400/10 rounded-lg border border-yellow-400/30">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-yellow-400" />
                    <span className="text-yellow-400 font-medium">¡Beneficio Oro!</span>
                  </div>
                  <p className="text-sm text-[#A1A1AA] mt-1">Refill de café americano gratis en cada visita</p>
                </div>
              )}

              <p className="text-xs text-[#71717A] mt-4 text-center">
                Multiplicador actual: {level_info.multiplier}x puntos
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Active Coupons */}
      {active_coupons && active_coupons.length > 0 && (
        <div className="px-4 mt-6 max-w-lg mx-auto">
          <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
            <Ticket className="h-5 w-5 text-[#708238]" />
            Mis Cupones
          </h2>
          <div className="space-y-3">
            {active_coupons.map((coupon) => (
              <Card key={coupon.id} className="bg-[#161616] border-[#27272A]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-bold text-white">{coupon.reward_name}</p>
                      <p className="text-sm text-[#A1A1AA]">
                        Código: <span className="font-mono text-[#708238]">{coupon.code}</span>
                      </p>
                      <p className="text-xs text-[#71717A] flex items-center gap-1 mt-1">
                        <Clock className="h-3 w-3" />
                        Vence: {formatDate(coupon.expires_at)}
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge className="bg-[#708238]/20 text-[#708238] border-[#708238]/50">
                        {coupon.discount_percent}% OFF
                      </Badge>
                      {coupon.max_discount && (
                        <p className="text-xs text-[#71717A] mt-1">Máx ${coupon.max_discount}</p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Rewards Catalog */}
      <div className="px-4 mt-6 max-w-lg mx-auto">
        <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <Gift className="h-5 w-5 text-[#708238]" />
          Canjear Recompensas
        </h2>
        <div className="grid gap-3">
          {all_rewards?.map((reward) => {
            const canRedeem = customer.total_points >= reward.points_required;
            return (
              <Card 
                key={reward.id} 
                className={`bg-[#161616] border-[#27272A] ${canRedeem ? "" : "opacity-60"}`}
              >
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <p className="font-bold text-white">{reward.name}</p>
                      <p className="text-sm text-[#708238]">{reward.points_required} puntos</p>
                      {reward.max_discount && (
                        <p className="text-xs text-[#71717A]">Máximo ${reward.max_discount} MXN</p>
                      )}
                    </div>
                    <Button
                      size="sm"
                      disabled={!canRedeem || redeeming === reward.id}
                      onClick={() => handleRedeem(reward.id)}
                      className={canRedeem 
                        ? "bg-[#708238] hover:bg-[#5a692d]" 
                        : "bg-[#27272A] text-[#71717A]"
                      }
                    >
                      {redeeming === reward.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : canRedeem ? (
                        "Canjear"
                      ) : (
                        `${reward.points_required - customer.total_points} más`
                      )}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="px-4 mt-6 max-w-lg mx-auto">
        <h2 className="text-lg font-bold text-white mb-3 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-[#708238]" />
          Actividad Reciente
        </h2>
        <Card className="bg-[#161616] border-[#27272A]">
          <CardContent className="p-0">
            {recent_transactions?.length > 0 ? (
              <div className="divide-y divide-[#27272A]">
                {recent_transactions.map((tx) => (
                  <div key={tx.id} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-full ${tx.points > 0 ? "bg-green-500/20" : "bg-orange-500/20"}`}>
                        {tx.points > 0 ? (
                          <Star className="h-4 w-4 text-green-400" />
                        ) : (
                          <Gift className="h-4 w-4 text-orange-400" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm text-white">{tx.description}</p>
                        <p className="text-xs text-[#71717A]">{formatDate(tx.created_at)}</p>
                      </div>
                    </div>
                    <span className={`font-bold ${tx.points > 0 ? "text-green-400" : "text-orange-400"}`}>
                      {tx.points > 0 ? "+" : ""}{tx.points}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-[#71717A]">
                <p>No hay actividad reciente</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Info Section */}
      <div className="px-4 mt-6 max-w-lg mx-auto">
        <Card className="bg-[#161616] border-[#27272A]">
          <CardContent className="p-4">
            <h3 className="font-bold text-white mb-3">¿Cómo funciona?</h3>
            <div className="space-y-3 text-sm">
              <div className="flex items-start gap-3">
                <div className="p-1.5 bg-[#708238]/20 rounded-full">
                  <span className="text-[#708238] font-bold text-xs">1</span>
                </div>
                <p className="text-[#A1A1AA]">Cada $10 MXN = 1 punto</p>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-1.5 bg-[#708238]/20 rounded-full">
                  <span className="text-[#708238] font-bold text-xs">2</span>
                </div>
                <p className="text-[#A1A1AA]">Escanea el código QR de tu ticket para acumular puntos</p>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-1.5 bg-[#708238]/20 rounded-full">
                  <span className="text-[#708238] font-bold text-xs">3</span>
                </div>
                <p className="text-[#A1A1AA]">Canjea tus puntos por descuentos y premios</p>
              </div>
              <div className="flex items-start gap-3">
                <div className="p-1.5 bg-[#708238]/20 rounded-full">
                  <span className="text-[#708238] font-bold text-xs">4</span>
                </div>
                <p className="text-[#A1A1AA]">Los puntos expiran a los 6 meses</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bottom spacing */}
      <div className="h-8" />
    </div>
  );
};

export default LoyaltyRewards;
