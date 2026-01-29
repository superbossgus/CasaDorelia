import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import { Wheat, Plus, Pencil, Trash2, Loader2, AlertTriangle } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const UNITS = [
  { value: "kg", label: "Kilogramo (kg)" },
  { value: "gramo", label: "Gramo (g)" },
  { value: "litro", label: "Litro (L)" },
  { value: "ml", label: "Mililitro (ml)" },
  { value: "pieza", label: "Pieza" },
  { value: "unidad", label: "Unidad" },
];

const Ingredients = () => {
  const [ingredients, setIngredients] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingIngredient, setEditingIngredient] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", unit: "kg", cost_per_unit: 0, supplier_id: "", min_stock: 10, is_active: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [ingredientsRes, suppliersRes] = await Promise.all([
        axios.get(`${API}/ingredients`),
        axios.get(`${API}/suppliers`),
      ]);
      setIngredients(ingredientsRes.data);
      setSuppliers(suppliersRes.data.filter(s => s.is_active));
    } catch (error) {
      toast.error("Error al cargar ingredientes");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || formData.cost_per_unit <= 0) {
      toast.error("Completa nombre y costo");
      return;
    }
    setIsSubmitting(true);
    try {
      const data = { ...formData, supplier_id: formData.supplier_id || null };
      if (editingIngredient) {
        await axios.put(`${API}/ingredients/${editingIngredient.id}`, data);
        toast.success("Ingrediente actualizado");
      } else {
        await axios.post(`${API}/ingredients`, data);
        toast.success("Ingrediente creado");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar este ingrediente?")) return;
    try {
      await axios.delete(`${API}/ingredients/${id}`);
      toast.success("Ingrediente eliminado");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar");
    }
  };

  const openEditDialog = (ingredient) => {
    setEditingIngredient(ingredient);
    setFormData({
      name: ingredient.name,
      unit: ingredient.unit,
      cost_per_unit: ingredient.cost_per_unit,
      supplier_id: ingredient.supplier_id || "",
      min_stock: ingredient.min_stock,
      is_active: ingredient.is_active
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingIngredient(null);
    setFormData({ name: "", unit: "kg", cost_per_unit: 0, supplier_id: "", min_stock: 10, is_active: true });
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="ingredients-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Ingredientes</h1>
          <p className="text-[#A1A1AA] mt-1">Materia prima para tus recetas</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-ingredient-button">
              <Plus className="h-4 w-4 mr-2" />
              Nuevo Ingrediente
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A]">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope">
                {editingIngredient ? "Editar Ingrediente" : "Nuevo Ingrediente"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Nombre *</Label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                  placeholder="Ej: Café en grano"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Unidad *</Label>
                  <Select value={formData.unit} onValueChange={(v) => setFormData({...formData, unit: v})}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {UNITS.map((unit) => (
                        <SelectItem key={unit.value} value={unit.value} className="text-white hover:bg-[#27272A]">
                          {unit.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Costo por Unidad *</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.cost_per_unit}
                    onChange={(e) => setFormData({...formData, cost_per_unit: parseFloat(e.target.value) || 0})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Proveedor</Label>
                <Select value={formData.supplier_id} onValueChange={(v) => setFormData({...formData, supplier_id: v})}>
                  <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                    <SelectValue placeholder="Seleccionar proveedor (opcional)" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#161616] border-[#27272A]">
                    <SelectItem value="" className="text-white hover:bg-[#27272A]">Sin proveedor</SelectItem>
                    {suppliers.map((s) => (
                      <SelectItem key={s.id} value={s.id} className="text-white hover:bg-[#27272A]">{s.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Stock Mínimo</Label>
                <Input
                  type="number"
                  value={formData.min_stock}
                  onChange={(e) => setFormData({...formData, min_stock: parseFloat(e.target.value) || 0})}
                  className="bg-[#0D0D0D] border-[#27272A] text-white"
                />
              </div>
              <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {editingIngredient ? "Actualizar" : "Crear"} Ingrediente
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Ingredients Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Wheat className="h-5 w-5 text-[#708238]" />
            Lista de Ingredientes ({ingredients.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {ingredients.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <Wheat className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay ingredientes registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Ingrediente</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Unidad</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Costo/Unidad</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Proveedor</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-center">Stock Mín.</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ingredients.map((ingredient) => (
                    <TableRow key={ingredient.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="text-white font-medium">{ingredient.name}</TableCell>
                      <TableCell>
                        <Badge className="bg-[#27272A] text-[#A1A1AA]">{ingredient.unit}</Badge>
                      </TableCell>
                      <TableCell className="text-white text-right">{formatCurrency(ingredient.cost_per_unit)}</TableCell>
                      <TableCell className="text-[#A1A1AA]">{ingredient.supplier_name || "—"}</TableCell>
                      <TableCell className="text-[#A1A1AA] text-center">{ingredient.min_stock}</TableCell>
                      <TableCell>
                        <Badge className={ingredient.is_active ? 'status-active' : 'status-inactive'}>
                          {ingredient.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(ingredient)}
                            className="text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(ingredient.id)}
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

export default Ingredients;
