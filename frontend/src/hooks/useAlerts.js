import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const useAlerts = (pollInterval = 300000) => { // 5 minutes default
  const [alerts, setAlerts] = useState([]);
  const [alertCount, setAlertCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastNotified, setLastNotified] = useState(new Set());

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/ingredient-inventory/alerts`);
      const newAlerts = response.data || [];
      
      // Filter critical alerts (less than 3 days)
      const criticalAlerts = newAlerts.filter(a => a.alert_type === "critical");
      
      setAlerts(newAlerts);
      setAlertCount(criticalAlerts.length);
      
      // Check for new critical alerts and send notifications
      const newCriticalIds = new Set(criticalAlerts.map(a => `${a.ingredient_id}_${a.cafeteria_id}`));
      const brandNewAlerts = criticalAlerts.filter(a => 
        !lastNotified.has(`${a.ingredient_id}_${a.cafeteria_id}`)
      );
      
      if (brandNewAlerts.length > 0 && Notification.permission === "granted") {
        sendNotification(brandNewAlerts);
      }
      
      setLastNotified(newCriticalIds);
      
    } catch (error) {
      console.error("Error fetching alerts:", error);
    } finally {
      setLoading(false);
    }
  }, [lastNotified]);

  const sendNotification = (alerts) => {
    if (alerts.length === 1) {
      new Notification("⚠️ Alerta Crítica - Doré", {
        body: `${alerts[0].ingredient_name} en ${alerts[0].cafeteria_name} tiene stock crítico (${alerts[0].days_until_stockout} días restantes)`,
        icon: "/favicon.ico",
        tag: "dore-alert",
        requireInteraction: true
      });
    } else {
      new Notification("🚨 Alertas Críticas - Doré", {
        body: `${alerts.length} ingredientes con stock crítico requieren atención`,
        icon: "/favicon.ico",
        tag: "dore-alert",
        requireInteraction: true
      });
    }
  };

  const requestNotificationPermission = async () => {
    if (!("Notification" in window)) {
      console.log("Este navegador no soporta notificaciones");
      return false;
    }
    
    if (Notification.permission === "granted") {
      return true;
    }
    
    if (Notification.permission !== "denied") {
      const permission = await Notification.requestPermission();
      return permission === "granted";
    }
    
    return false;
  };

  useEffect(() => {
    fetchAlerts();
    
    const interval = setInterval(fetchAlerts, pollInterval);
    
    return () => clearInterval(interval);
  }, [pollInterval]);

  return {
    alerts,
    alertCount,
    loading,
    fetchAlerts,
    requestNotificationPermission,
    notificationPermission: typeof Notification !== "undefined" ? Notification.permission : "denied"
  };
};

export default useAlerts;
