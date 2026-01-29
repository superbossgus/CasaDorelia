import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { MessageCircle, Plus, Trash2, Loader2, Send, Bell, CheckCircle, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const WhatsAppAlerts = () => {
  const [numbers, setNumbers] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isSendingAlerts, setIsSendingAlerts] = useState(false);
  
  const [formData, setFormData] = useState({ phone_number: "", name: "" });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [numbersRes, statusRes] = await Promise.all([
        axios.get(`${API}/whatsapp/numbers`),
        axios.get(`${API}/whatsapp/status`),
      ]);
      setNumbers(numbersRes.data);
      setStatus(statusRes.data);
    } catch (error) {
      toast.error("Error al cargar configuración de WhatsApp");
    } finally {
      setLoading(false);
    }
  };

  const handleAddNumber = async () => {
    if (!formData.phone_number || !formData.name) {
      toast.error("Completa todos los campos");
      return;
    }
    
    // Validate phone format
    if (!formData.phone_number.startsWith("+")) {
      toast.error("El número debe empezar con + y código de país (ej: +525591985187)");
      return;
    }
    
    try {
      await axios.post(`${API}/whatsapp/numbers`, formData);
      toast.success("Número agregado correctamente");
      setIsDialogOpen(false);
      setFormData({ phone_number: "", name: "" });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al agregar número");
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar este número?")) return;
    try {
      await axios.delete(`${API}/whatsapp/numbers/${id}`);
      toast.success("Número eliminado");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar número");
    }
  };

  const handleSendTest = async () => {
    setIsSending(true);
    try {
      const response = await axios.post(`${API}/whatsapp/send-test`);
      const results = response.data.results;
      const successful = results.filter(r => r.status === "sent").length;
      
      if (successful === results.length) {
        toast.success(`Mensaje de prueba enviado a ${successful} números`);
      } else {
        toast.warning(`Enviado a ${successful}/${results.length} números`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al enviar mensaje de prueba");
    } finally {
      setIsSending(false);
    }
  };

  const handleSendAlerts = async () => {
    setIsSendingAlerts(true);
    try {
      const response = await axios.post(`${API}/whatsapp/send-alerts`);
      
      if (response.data.alerts_count === 0) {
        toast.info("No hay alertas críticas de ingredientes");
      } else {
        toast.success(`${response.data.alerts_count} alertas enviadas a ${numbers.length} números`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al enviar alertas");
    } finally {
      setIsSendingAlerts(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="whatsapp-alerts-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Alertas WhatsApp</h1>
          <p className="text-[#A1A1AA] mt-1">Configura números para recibir alertas de stock crítico</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-whatsapp-number-button">
              <Plus className="h-4 w-4 mr-2" />
              Agregar Número
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope flex items-center gap-2">
                <MessageCircle className="h-5 w-5 text-[#25D366]" />
                Agregar Número de WhatsApp
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="bg-[#0D0D0D] rounded-lg p-4 border border-[#27272A]">
                <p className="text-sm text-[#D97706] flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>
                    <strong>Importante:</strong> Antes de agregar un número, el usuario debe enviar un mensaje 
                    al número <strong>+1 (415) 523-8886</strong> con el código <strong>"join &lt;sandbox-code&gt;"</strong> 
                    desde su WhatsApp para activar el sandbox de Twilio.
                  </span>
                </p>
              </div>
              
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre del contacto</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Ej: Juan Pérez"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Número de WhatsApp</Label>
                <Input
                  value={formData.phone_number}
                  onChange={(e) => setFormData({...formData, phone_number: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="+525591985187"
                />
                <p className="text-xs text-[#71717A]">Formato: +[código país][número] sin espacios</p>
              </div>
              <Button onClick={handleAddNumber} className="w-full bg-[#25D366] hover:bg-[#128C7E] text-white">
                <MessageCircle className="h-4 w-4 mr-2" />
                Agregar Número
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Status Card */}
      <Card className={`border ${status?.configured ? 'bg-[#25D366]/10 border-[#25D366]/30' : 'bg-red-900/10 border-red-500/30'}`}>
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status?.configured ? (
              <CheckCircle className="h-6 w-6 text-[#25D366]" />
            ) : (
              <AlertTriangle className="h-6 w-6 text-red-400" />
            )}
            <div>
              <p className={status?.configured ? 'text-[#25D366] font-medium' : 'text-red-400 font-medium'}>
                {status?.message}
              </p>
              {status?.twilio_number && (
                <p className="text-[#71717A] text-sm">Número Twilio: {status.twilio_number}</p>
              )}
            </div>
          </div>
          {status?.configured && numbers.length > 0 && (
            <div className="flex gap-2">
              <Button
                onClick={handleSendTest}
                disabled={isSending}
                variant="outline"
                className="bg-transparent border-[#25D366] text-[#25D366] hover:bg-[#25D366]/20"
              >
                {isSending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Send className="h-4 w-4 mr-2" />}
                Enviar Prueba
              </Button>
              <Button
                onClick={handleSendAlerts}
                disabled={isSendingAlerts}
                className="bg-[#D97706] hover:bg-[#B45309] text-white"
              >
                {isSendingAlerts ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Bell className="h-4 w-4 mr-2" />}
                Enviar Alertas Ahora
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Numbers Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-[#25D366]" />
            Números Configurados ({numbers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {numbers.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <MessageCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay números configurados</p>
              <p className="text-sm mt-2">Agrega números de WhatsApp para recibir alertas de stock crítico</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Nombre</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Número</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Agregado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {numbers.map((num) => (
                    <TableRow key={num.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="text-white font-medium">{num.name}</TableCell>
                      <TableCell className="font-mono text-[#25D366]">{num.phone_number}</TableCell>
                      <TableCell>
                        <Badge className={num.is_active ? 'bg-[#25D366]/20 text-[#25D366]' : 'bg-[#27272A] text-[#71717A]'}>
                          {num.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-[#71717A] text-sm">
                        {new Date(num.created_at).toLocaleDateString("es-MX")}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(num.id)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-400/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardContent className="p-6">
          <h3 className="text-white font-manrope font-bold mb-4">¿Cuándo se envían las alertas?</h3>
          <div className="space-y-3 text-[#A1A1AA]">
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 rounded-full bg-red-500 mt-2"></div>
              <p><strong className="text-white">Alertas Críticas:</strong> Ingredientes con menos de 3 días de stock según consumo promedio</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 rounded-full bg-[#D97706] mt-2"></div>
              <p><strong className="text-white">Información incluida:</strong> Nombre del ingrediente, cafetería, stock actual, días restantes y cantidad sugerida a pedir</p>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-2 h-2 rounded-full bg-[#25D366] mt-2"></div>
              <p><strong className="text-white">Envío manual:</strong> Usa el botón "Enviar Alertas Ahora" para revisar alertas críticas en cualquier momento</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default WhatsAppAlerts;
