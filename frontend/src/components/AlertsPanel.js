import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { AlertTriangle, Bell, BellOff, ChevronRight, Package, Clock } from "lucide-react";
import { toast } from "sonner";

const AlertsPanel = ({ alerts, loading, onRequestPermission, notificationPermission }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const criticalAlerts = alerts.filter(a => a.alert_type === "critical");
  const warningAlerts = alerts.filter(a => a.alert_type === "warning");
  
  const displayAlerts = isExpanded ? alerts : alerts.slice(0, 4);
  
  const handleEnableNotifications = async () => {
    const granted = await onRequestPermission();
    if (granted) {
      toast.success("Notificaciones activadas");
    } else {
      toast.error("Permiso de notificaciones denegado");
    }
  };

  if (loading) {
    return (
      <Card className="bg-[#161616] border-[#27272A]">
        <CardContent className="p-6">
          <div className="animate-pulse flex items-center gap-3">
            <div className="h-10 w-10 bg-[#27272A] rounded-lg"></div>
            <div className="flex-1">
              <div className="h-4 bg-[#27272A] rounded w-1/3 mb-2"></div>
              <div className="h-3 bg-[#27272A] rounded w-1/2"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`border ${criticalAlerts.length > 0 ? 'bg-red-950/20 border-red-500/30' : 'bg-[#161616] border-[#27272A]'}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <div className={`p-2 rounded-lg ${criticalAlerts.length > 0 ? 'bg-red-500/20' : 'bg-[#D97706]/20'}`}>
              <AlertTriangle className={`h-5 w-5 ${criticalAlerts.length > 0 ? 'text-red-400' : 'text-[#D97706]'}`} />
            </div>
            Alertas de Inventario
            {criticalAlerts.length > 0 && (
              <Badge className="bg-red-500 text-white ml-2">{criticalAlerts.length} críticas</Badge>
            )}
          </CardTitle>
          
          {notificationPermission !== "granted" && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleEnableNotifications}
              className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white"
            >
              <Bell className="h-4 w-4 mr-2" />
              Activar notificaciones
            </Button>
          )}
          
          {notificationPermission === "granted" && (
            <Badge className="bg-[#708238]/20 text-[#708238]">
              <Bell className="h-3 w-3 mr-1" />
              Notificaciones activas
            </Badge>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-[#71717A]">
            <Package className="h-10 w-10 mx-auto mb-3 opacity-50" />
            <p>No hay alertas de inventario</p>
            <p className="text-sm mt-1">Todos los ingredientes tienen stock suficiente</p>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {displayAlerts.map((alert, index) => (
                <div
                  key={`${alert.ingredient_id}_${alert.cafeteria_id}`}
                  className={`p-3 rounded-lg border transition-all ${
                    alert.alert_type === "critical" 
                      ? 'bg-red-950/30 border-red-500/30 hover:bg-red-950/50' 
                      : 'bg-[#D97706]/10 border-[#D97706]/30 hover:bg-[#D97706]/20'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-1.5 rounded ${alert.alert_type === "critical" ? 'bg-red-500/20' : 'bg-[#D97706]/20'}`}>
                        <AlertTriangle className={`h-4 w-4 ${alert.alert_type === "critical" ? 'text-red-400' : 'text-[#D97706]'}`} />
                      </div>
                      <div>
                        <p className="text-white font-medium text-sm">{alert.ingredient_name}</p>
                        <p className="text-[#71717A] text-xs">{alert.cafeteria_name}</p>
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className="flex items-center gap-1 text-xs">
                        <Clock className={`h-3 w-3 ${alert.alert_type === "critical" ? 'text-red-400' : 'text-[#D97706]'}`} />
                        <span className={alert.alert_type === "critical" ? 'text-red-400 font-bold' : 'text-[#D97706]'}>
                          {alert.days_until_stockout !== null ? `${alert.days_until_stockout} días` : 'Stock bajo'}
                        </span>
                      </div>
                      <p className="text-[#71717A] text-xs mt-0.5">
                        {alert.current_stock.toFixed(1)} {alert.unit}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {alerts.length > 4 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full mt-3 text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
              >
                {isExpanded ? 'Ver menos' : `Ver ${alerts.length - 4} alertas más`}
                <ChevronRight className={`h-4 w-4 ml-1 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
              </Button>
            )}
            
            <div className="mt-4 pt-3 border-t border-[#27272A] flex items-center justify-between">
              <div className="flex items-center gap-4 text-xs text-[#71717A]">
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500"></span>
                  {criticalAlerts.length} críticas (&lt;3 días)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-[#D97706]"></span>
                  {warningAlerts.length} advertencias (&lt;7 días)
                </span>
              </div>
              
              <Link to="/ingredient-inventory">
                <Button size="sm" className="bg-[#708238] hover:bg-[#5a692d] text-white text-xs">
                  Ver inventario
                  <ChevronRight className="h-3 w-3 ml-1" />
                </Button>
              </Link>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default AlertsPanel;
