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
import { Truck, Plus, Pencil, Trash2, Loader2, Phone, Mail } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Suppliers = () => {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", contact_name: "", email: "", phone: "", address: "", is_active: true
  });

  useEffect(() => {
    fetchSuppliers();
  }, []);

  const fetchSuppliers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/suppliers`);
      setSuppliers(response.data);
    } catch (error) {
      toast.error("Error al cargar proveedores");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name) {
      toast.error("El nombre es requerido");
      return;
    }
    setIsSubmitting(true);
    try {
      if (editingSupplier) {
        await axios.put(`${API}/suppliers/${editingSupplier.id}`, formData);
        toast.success("Proveedor actualizado");
      } else {
        await axios.post(`${API}/suppliers`, formData);
        toast.success("Proveedor creado");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchSuppliers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar proveedor");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar este proveedor?")) return;
    try {
      await axios.delete(`${API}/suppliers/${id}`);
      toast.success("Proveedor eliminado");
      fetchSuppliers();
    } catch (error) {
      toast.error("Error al eliminar proveedor");
    }
  };

  const openEditDialog = (supplier) => {
    setEditingSupplier(supplier);
    setFormData({
      name: supplier.name,
      contact_name: supplier.contact_name || "",
      email: supplier.email || "",
      phone: supplier.phone || "",
      address: supplier.address || "",
      is_active: supplier.is_active
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingSupplier(null);
    setFormData({ name: "", contact_name: "", email: "", phone: "", address: "", is_active: true });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="suppliers-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Proveedores</h1>
          <p className="text-[#A1A1AA] mt-1">Gestiona tus proveedores de insumos</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-supplier-button">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Proveedor
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope">
                {editingSupplier ? "Editar Proveedor" : "Nuevo Proveedor"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre de la Empresa *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Ej: Distribuidora de Café MX"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Persona de Contacto</Label>
                <Input
                  value={formData.contact_name}
                  onChange={(e) => setFormData({...formData, contact_name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Nombre del contacto"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Teléfono</Label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="555-1234"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Email</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="contacto@proveedor.com"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Dirección</Label>
                <Input
                  value={formData.address}
                  onChange={(e) => setFormData({...formData, address: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Dirección completa"
                />
              </div>
              <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {editingSupplier ? "Actualizar" : "Crear"} Proveedor
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Suppliers Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Truck className="h-5 w-5 text-[#708238]" />
            Lista de Proveedores ({suppliers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {suppliers.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <Truck className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay proveedores registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Empresa</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Contacto</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Teléfono</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Email</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {suppliers.map((supplier) => (
                    <TableRow key={supplier.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="text-white font-medium">{supplier.name}</TableCell>
                      <TableCell className="text-[#A1A1AA]">{supplier.contact_name || "-"}</TableCell>
                      <TableCell>
                        {supplier.phone ? (
                          <span className="flex items-center gap-1 text-[#A1A1AA]">
                            <Phone className="h-3 w-3" />
                            {supplier.phone}
                          </span>
                        ) : "-"}
                      </TableCell>
                      <TableCell>
                        {supplier.email ? (
                          <span className="flex items-center gap-1 text-[#A1A1AA]">
                            <Mail className="h-3 w-3" />
                            {supplier.email}
                          </span>
                        ) : "-"}
                      </TableCell>
                      <TableCell>
                        <Badge className={supplier.is_active ? 'status-active' : 'status-inactive'}>
                          {supplier.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(supplier)}
                            className="text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(supplier.id)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-400/10"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Suppliers;
