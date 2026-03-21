import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * AuthCallback - Handles Google OAuth callback
 * REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
 */
const AuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { setGoogleUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Use ref to prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processGoogleAuth = async () => {
      try {
        // Extract session_id from URL fragment (hash)
        const hash = location.hash;
        const params = new URLSearchParams(hash.replace("#", ""));
        const sessionId = params.get("session_id");

        if (!sessionId) {
          console.error("No session_id found in URL");
          toast.error("Error de autenticación: No se encontró sesión");
          navigate("/admin", { replace: true });
          return;
        }

        // Exchange session_id for user data via backend
        const response = await axios.post(
          `${API}/auth/google/session`,
          { session_id: sessionId },
          { withCredentials: true }
        );

        const { token, user } = response.data;

        // Store token in localStorage
        localStorage.setItem("token", token);
        axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;

        // Update auth context
        setGoogleUser(user, token);

        toast.success(`¡Bienvenido${user.name ? `, ${user.name}` : ""}!`);

        // Redirect based on role
        if (user.role === "superadmin") {
          navigate("/superadmin", { replace: true, state: { user } });
        } else {
          navigate("/dashboard", { replace: true, state: { user } });
        }
      } catch (error) {
        console.error("Google auth error:", error);
        const message =
          error.response?.data?.detail || "Error al autenticar con Google";
        toast.error(message);
        navigate("/admin", { replace: true });
      }
    };

    processGoogleAuth();
  }, [location, navigate, setGoogleUser]);

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex flex-col items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-12 w-12 animate-spin text-[#708238]" />
        <p className="text-white text-lg">Autenticando con Google...</p>
        <p className="text-[#71717A] text-sm">Por favor espera un momento</p>
      </div>
    </div>
  );
};

export default AuthCallback;
