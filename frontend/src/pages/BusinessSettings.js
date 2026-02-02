import { useState, useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { Building2, Upload, Trash2, Loader2, Image, Save, Phone, Mail } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

const BusinessSettings = () => {
  const { token } = useAuth();
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({ business_name: "", phone: "" });
  const [logoTimestamp, setLogoTimestamp] = useState(Date.now()); // Cache buster
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchTenant();
  }, []);

  const fetchTenant = async () => {
    try {
      const response = await axios.get(`${API}/api/tenants/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTenant(response.data);
      setFormData({
        business_name: response.data.business_name || "",
        phone: response.data.phone || ""
      });
    } catch (error) {
      toast.error("Error al cargar información del negocio");
    } finally {
      setLoading(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file size
    if (file.size > 2 * 1024 * 1024) {
      toast.error("El archivo es demasiado grande. Máximo 2MB");
      return;
    }

    // Validate file type
    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/svg+xml"];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Tipo de archivo no permitido. Use JPEG, PNG, WebP o SVG");
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API}/api/tenants/logo`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      toast.success("Logo subido correctamente");
      setTenant({ ...tenant, logo_url: response.data.logo_url });
      setLogoTimestamp(Date.now()); // Update timestamp to bust cache
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al subir logo");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDeleteLogo = async () => {
    try {
      await axios.delete(`${API}/api/tenants/logo`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success("Logo eliminado");
      setTenant({ ...tenant, logo_url: null });
      // Reset file input to allow re-selecting the same file
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      toast.error("Error al eliminar logo");
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      const form = new FormData();
      form.append("business_name", formData.business_name);
      form.append("phone", formData.phone || "");

      await axios.put(`${API}/api/tenants/settings`, form, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "multipart/form-data"
        }
      });
      toast.success("Configuración guardada");
      fetchTenant();
    } catch (error) {
      toast.error("Error al guardar configuración");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  const logoUrl = tenant?.logo_url 
    ? `${API}${tenant.logo_url}` 
    : null;

  return (
    <div className="space-y-6" data-testid="business-settings">
      <div>
        <h1 className="text-2xl font-bold text-white font-manrope">Configuración del Negocio</h1>
        <p className="text-[#A1A1AA]">Personaliza tu marca y configuración</p>
      </div>

      {/* Logo Section */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Image className="h-5 w-5 text-[#708238]" />
            Logo de tu Negocio
          </CardTitle>
          <CardDescription className="text-[#A1A1AA]">
            Este logo se mostrará en toda la aplicación, reportes y exportaciones
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-6">
            {/* Logo Preview */}
            <div className="flex-shrink-0">
              {logoUrl ? (
                <div className="relative group">
                  <div className="w-32 h-32 rounded-xl bg-[#0D0D0D] border-2 border-[#27272A] flex items-center justify-center overflow-hidden">
                    <img 
                      src={logoUrl} 
                      alt="Logo del negocio" 
                      className="max-w-full max-h-full object-contain p-2"
                    />
                  </div>
                  <button
                    onClick={handleDeleteLogo}
                    className="absolute -top-2 -right-2 p-1.5 bg-red-500 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                    title="Eliminar logo"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ) : (
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className="w-32 h-32 rounded-xl bg-[#0D0D0D] border-2 border-dashed border-[#27272A] hover:border-[#708238] cursor-pointer flex flex-col items-center justify-center gap-2 text-[#71717A] hover:text-[#708238] transition-all"
                >
                  {uploading ? (
                    <Loader2 className="h-8 w-8 animate-spin" />
                  ) : (
                    <>
                      <Upload className="h-8 w-8" />
                      <span className="text-xs">Subir logo</span>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Upload Info */}
            <div className="flex-1">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleLogoUpload}
                accept="image/jpeg,image/png,image/webp,image/svg+xml"
                className="hidden"
              />
              
              {logoUrl && (
                <Button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  variant="outline"
                  className="mb-4 bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
                >
                  {uploading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Upload className="h-4 w-4 mr-2" />
                  )}
                  Cambiar logo
                </Button>
              )}

              <div className="space-y-2 text-sm text-[#71717A]">
                <p>• Formatos: JPEG, PNG, WebP, SVG</p>
                <p>• Tamaño máximo: 2MB</p>
                <p>• Recomendado: Fondo transparente (PNG/SVG)</p>
                <p>• Tamaño ideal: 512x512 px o mayor</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Business Info Section */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Building2 className="h-5 w-5 text-[#708238]" />
            Información del Negocio
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Nombre del Negocio</Label>
              <Input
                value={formData.business_name}
                onChange={(e) => setFormData({ ...formData, business_name: e.target.value })}
                className="bg-[#0D0D0D] border-[#27272A] text-white"
                placeholder="Mi Cafetería"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Teléfono</Label>
              <Input
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="bg-[#0D0D0D] border-[#27272A] text-white"
                placeholder="+52 55 1234 5678"
              />
            </div>
          </div>

          <div className="flex items-center gap-4 pt-2">
            <div className="flex items-center gap-2 text-sm text-[#71717A]">
              <Mail className="h-4 w-4" />
              <span>{tenant?.owner_email}</span>
            </div>
            <Badge className={tenant?.status === "active" ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"}>
              {tenant?.status === "active" ? "Activo" : "Prueba"}
            </Badge>
          </div>

          <Button
            onClick={handleSaveSettings}
            disabled={saving}
            className="bg-[#708238] hover:bg-[#5a692d] text-white"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Save className="h-4 w-4 mr-2" />
            )}
            Guardar Cambios
          </Button>
        </CardContent>
      </Card>

      {/* Preview Section */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope">Vista Previa</CardTitle>
          <CardDescription className="text-[#A1A1AA]">
            Así se verá tu marca en la aplicación
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-[#0D0D0D] rounded-lg p-4 border border-[#27272A]">
            <div className="flex items-center gap-3">
              {logoUrl ? (
                <img src={logoUrl} alt="Logo" className="h-10 w-10 object-contain" />
              ) : (
                <div className="h-10 w-10 rounded-lg bg-[#708238] flex items-center justify-center">
                  <Building2 className="h-6 w-6 text-white" />
                </div>
              )}
              <div>
                <h3 className="text-white font-bold">{formData.business_name || "Tu Negocio"}</h3>
                <p className="text-xs text-[#71717A]">Sistema de Gestión</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default BusinessSettings;
