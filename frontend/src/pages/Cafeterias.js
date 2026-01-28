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
import { Store, Plus, Pencil, Trash2, Loader2, MapPin, Phone } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Cafeterias = () => {
  const [cafeterias, setCafeterias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingCafeteria, setEditingCafeteria] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", address: "", phone: "", is_active: true
  });

  useEffect(() => {
    fetchCafeterias();
  }, []);

  const fetchCafeterias = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/cafeterias`);
      setCafeterias(response.data);
    } catch (error) {
      toast.error("Error al cargar cafeterías");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.address) {
      toast.error("Nombre y dirección son requeridos");
      return;
    }
    setIsSubmitting(true);
    try {
      if (editingCafeteria) {
        await axios.put(`${API}/cafeterias/${editingCafeteria.id}`, formData);
        toast.success("Cafetería actualizada");
      } else {
        await axios.post(`${API}/cafeterias`, formData);
        toast.success("Cafetería creada");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchCafeterias();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar cafetería");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar esta cafetería?")) return;
    try {
      await axios.delete(`${API}/cafeterias/${id}`);
      toast.success("Cafetería eliminada");
      fetchCafeterias();
    } catch (error) {
      toast.error("Error al eliminar cafetería");
    }
  };

  const openEditDialog = (cafeteria) => {
    setEditingCafeteria(cafeteria);
    setFormData({
      name: cafeteria.name,
      address: cafeteria.address,
      phone: cafeteria.phone || "",
      is_active: cafeteria.is_active
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingCafeteria(null);
    setFormData({ name: "", address: "", phone: "", is_active: true });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="cafeterias-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Cafeterías</h1>
          <p className="text-[#A1A1AA] mt-1">Administra tus sucursales</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-cafeteria-button">
              <Plus className="h-4 w-4 mr-2" />
              Nueva Cafetería
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope">
                {editingCafeteria ? "Editar Cafetería" : "Nueva Cafetería"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Ej: Café Central"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Dirección *</Label>
                <Input
                  value={formData.address}
                  onChange={(e) => setFormData({...formData, address: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Dirección completa"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Teléfono</Label>
                <Input
                  value={formData.phone}
                  onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="555-1234"
                />
              </div>
              <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {editingCafeteria ? "Actualizar" : "Crear"} Cafetería
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Cafeterias Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cafeterias.map((cafeteria) => (
          <Card key={cafeteria.id} className="bg-[#161616] border-[#27272A] card-hover">
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <Store className="h-6 w-6 text-[#708238]" />
                </div>
                <Badge className={cafeteria.is_active ? 'status-active' : 'status-inactive'}>
                  {cafeteria.is_active ? "Activa" : "Inactiva"}
                </Badge>
              </div>
              
              <h3 className="text-xl font-bold text-white font-manrope mb-2">
                {cafeteria.name}
              </h3>
              
              <div className="space-y-2 mb-4">
                <div className="flex items-start gap-2 text-[#A1A1AA]">
                  <MapPin className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span className="text-sm">{cafeteria.address}</span>
                </div>
                {cafeteria.phone && (
                  <div className="flex items-center gap-2 text-[#A1A1AA]">
                    <Phone className="h-4 w-4" />
                    <span className="text-sm">{cafeteria.phone}</span>
                  </div>
                )}
              </div>
              
              <div className="flex items-center gap-2 pt-4 border-t border-[#27272A]">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => openEditDialog(cafeteria)}
                  className="flex-1 bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white"
                >
                  <Pencil className="h-4 w-4 mr-2" />
                  Editar
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(cafeteria.id)}
                  className="bg-transparent border-[#7F1D1D] text-red-400 hover:bg-[#7F1D1D]/20"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {cafeterias.length === 0 && (
        <Card className="bg-[#161616] border-[#27272A]">
          <CardContent className="text-center py-12 text-[#71717A]">
            <Store className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No hay cafeterías registradas</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Cafeterias;
