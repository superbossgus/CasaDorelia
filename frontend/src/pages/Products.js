import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import axios from "axios";
import { Coffee, Plus, Pencil, Trash2, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Products = () => {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isCategoryDialogOpen, setIsCategoryDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", description: "", category_id: "", price: 0, cost: 0, is_active: true
  });
  const [newCategory, setNewCategory] = useState({ name: "", description: "" });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [productsRes, categoriesRes] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/categories`),
      ]);
      setProducts(productsRes.data);
      setCategories(categoriesRes.data);
    } catch (error) {
      toast.error("Error al cargar productos");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.category_id || formData.price <= 0) {
      toast.error("Completa los campos requeridos");
      return;
    }
    setIsSubmitting(true);
    try {
      if (editingProduct) {
        await axios.put(`${API}/products/${editingProduct.id}`, formData);
        toast.success("Producto actualizado");
      } else {
        await axios.post(`${API}/products`, formData);
        toast.success("Producto creado");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar producto");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar este producto?")) return;
    try {
      await axios.delete(`${API}/products/${id}`);
      toast.success("Producto eliminado");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar producto");
    }
  };

  const handleAddCategory = async () => {
    if (!newCategory.name) {
      toast.error("Ingresa un nombre para la categoría");
      return;
    }
    try {
      await axios.post(`${API}/categories`, newCategory);
      toast.success("Categoría creada");
      setIsCategoryDialogOpen(false);
      setNewCategory({ name: "", description: "" });
      fetchData();
    } catch (error) {
      toast.error("Error al crear categoría");
    }
  };

  const openEditDialog = (product) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      description: product.description || "",
      category_id: product.category_id,
      price: product.price,
      cost: product.cost,
      is_active: product.is_active
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingProduct(null);
    setFormData({ name: "", description: "", category_id: "", price: 0, cost: 0, is_active: true });
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  const getCategoryName = (id) => categories.find(c => c.id === id)?.name || "Sin categoría";

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="products-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Productos</h1>
          <p className="text-[#A1A1AA] mt-1">Gestiona el menú de tus cafeterías</p>
        </div>
        
        <div className="flex items-center gap-3">
          <Dialog open={isCategoryDialogOpen} onOpenChange={setIsCategoryDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white">
                <Plus className="h-4 w-4 mr-2" />
                Categoría
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#161616] border-[#27272A]">
              <DialogHeader>
                <DialogTitle className="text-white font-manrope">Nueva Categoría</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Nombre</Label>
                  <Input
                    value={newCategory.name}
                    onChange={(e) => setNewCategory({...newCategory, name: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Ej: Bebidas Calientes"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Descripción</Label>
                  <Input
                    value={newCategory.description}
                    onChange={(e) => setNewCategory({...newCategory, description: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Descripción opcional"
                  />
                </div>
                <Button onClick={handleAddCategory} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                  Crear Categoría
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          
          <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
            <DialogTrigger asChild>
              <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-product-button">
                <Plus className="h-4 w-4 mr-2" />
                Nuevo Producto
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#161616] border-[#27272A]">
              <DialogHeader>
                <DialogTitle className="text-white font-manrope">
                  {editingProduct ? "Editar Producto" : "Nuevo Producto"}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Nombre *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Ej: Café Americano"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Categoría *</Label>
                  <Select value={formData.category_id} onValueChange={(v) => setFormData({...formData, category_id: v})}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue placeholder="Seleccionar categoría" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {categories.map((cat) => (
                        <SelectItem key={cat.id} value={cat.id} className="text-white hover:bg-[#27272A]">{cat.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Precio de Venta *</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.price}
                      onChange={(e) => setFormData({...formData, price: parseFloat(e.target.value) || 0})}
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Costo *</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.cost}
                      onChange={(e) => setFormData({...formData, cost: parseFloat(e.target.value) || 0})}
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Descripción</Label>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Descripción opcional"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-[#EDEDED]">Activo</Label>
                  <Switch
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData({...formData, is_active: checked})}
                  />
                </div>
                {formData.price > 0 && formData.cost > 0 && (
                  <div className="bg-[#0D0D0D] rounded-lg p-3">
                    <p className="text-sm text-[#A1A1AA]">
                      Margen de utilidad: <span className="text-[#708238] font-bold">
                        {(((formData.price - formData.cost) / formData.price) * 100).toFixed(1)}%
                      </span>
                    </p>
                  </div>
                )}
                <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  {editingProduct ? "Actualizar" : "Crear"} Producto
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Products Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Coffee className="h-5 w-5 text-[#708238]" />
            Lista de Productos ({products.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {products.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <Coffee className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay productos registrados</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Producto</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Categoría</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Precio</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Costo</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Margen</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((product) => (
                    <TableRow key={product.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="text-white font-medium">{product.name}</TableCell>
                      <TableCell>
                        <Badge className="bg-[#27272A] text-[#A1A1AA]">
                          {getCategoryName(product.category_id)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-white text-right">{formatCurrency(product.price)}</TableCell>
                      <TableCell className="text-[#A1A1AA] text-right">{formatCurrency(product.cost)}</TableCell>
                      <TableCell className="text-right">
                        <span className="text-[#708238] font-bold">{product.margin}%</span>
                      </TableCell>
                      <TableCell>
                        <Badge className={product.is_active ? 'status-active' : 'status-inactive'}>
                          {product.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(product)}
                            className="text-[#A1A1AA] hover:text-white hover:bg-[#27272A]"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(product.id)}
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

export default Products;
