import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
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
import { Coffee, Plus, Pencil, Trash2, Loader2, Image, Download, X, BookOpen } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Products = () => {
  const { isAdmin } = useAuth();
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [cafeterias, setCafeterias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isImageDialogOpen, setIsImageDialogOpen] = useState(false);
  const [isCategoryDialogOpen, setIsCategoryDialogOpen] = useState(false);
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    name: "", description: "", category_id: "", price: 0, cost: 0, is_active: true
  });
  const [newCategory, setNewCategory] = useState({ name: "", description: "" });
  const [imageForm, setImageForm] = useState({ main_image: "", images: ["", "", ""] });
  const [exportCafeteria, setExportCafeteria] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [productsRes, categoriesRes, cafeteriasRes] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/categories`),
        axios.get(`${API}/cafeterias`),
      ]);
      setProducts(productsRes.data);
      setCategories(categoriesRes.data);
      setCafeterias(cafeteriasRes.data);
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

  const openImageDialog = (product) => {
    setSelectedProduct(product);
    setImageForm({
      main_image: product.main_image || "",
      images: [
        product.images?.[0] || "",
        product.images?.[1] || "",
        product.images?.[2] || ""
      ]
    });
    setIsImageDialogOpen(true);
  };

  const handleImageSubmit = async () => {
    if (!selectedProduct) return;
    setIsSubmitting(true);
    try {
      await axios.put(`${API}/products/${selectedProduct.id}/images`, {
        main_image: imageForm.main_image || null,
        images: imageForm.images.filter(img => img.trim() !== "")
      });
      toast.success("Imágenes actualizadas");
      setIsImageDialogOpen(false);
      fetchData();
    } catch (error) {
      toast.error("Error al actualizar imágenes");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleExport = async (format) => {
    if (!exportCafeteria) {
      toast.error("Selecciona una cafetería");
      return;
    }
    try {
      const response = await axios.get(`${API}/catalog/export/${exportCafeteria}`, {
        params: { format },
        responseType: format === 'csv' ? 'blob' : 'json'
      });
      
      if (format === 'csv') {
        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `catalogo_${exportCafeteria}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      } else {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `catalogo_${exportCafeteria}.json`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
      
      toast.success("Catálogo exportado");
      setIsExportDialogOpen(false);
    } catch (error) {
      toast.error("Error al exportar catálogo");
    }
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
        
        <div className="flex items-center gap-3 flex-wrap">
          {/* Export Dialog */}
          <Dialog open={isExportDialogOpen} onOpenChange={setIsExportDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white">
                <Download className="h-4 w-4 mr-2" />
                Exportar
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#161616] border-[#27272A]">
              <DialogHeader>
                <DialogTitle className="text-white font-manrope">Exportar Catálogo</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Cafetería</Label>
                  <Select value={exportCafeteria} onValueChange={setExportCafeteria}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                      <SelectValue placeholder="Seleccionar cafetería" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {cafeterias.map((c) => (
                        <SelectItem key={c.id} value={c.id} className="text-white hover:bg-[#27272A]">{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Button onClick={() => handleExport('json')} className="bg-[#708238] hover:bg-[#5a692d] text-white">
                    Exportar JSON
                  </Button>
                  <Button onClick={() => handleExport('csv')} variant="outline" className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white">
                    Exportar CSV
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

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
                    <Label className="text-[#EDEDED]">Costo (manual)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={formData.cost}
                      onChange={(e) => setFormData({...formData, cost: parseFloat(e.target.value) || 0})}
                      className="bg-[#0D0D0D] border-[#27272A] text-white"
                    />
                    <p className="text-xs text-[#71717A]">Se actualiza automáticamente con la receta</p>
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

      {/* Image Dialog */}
      <Dialog open={isImageDialogOpen} onOpenChange={setIsImageDialogOpen}>
        <DialogContent className="bg-[#161616] border-[#27272A] max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-white font-manrope flex items-center gap-2">
              <Image className="h-5 w-5 text-[#708238]" />
              Imágenes de {selectedProduct?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-6 mt-4">
            {/* Main Image */}
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Imagen Principal (URL)</Label>
              <Input
                value={imageForm.main_image}
                onChange={(e) => setImageForm({...imageForm, main_image: e.target.value})}
                className="bg-[#0D0D0D] border-[#27272A] text-white"
                placeholder="https://ejemplo.com/imagen.jpg"
              />
              {imageForm.main_image && (
                <div className="relative w-32 h-32 rounded-lg overflow-hidden bg-[#0D0D0D]">
                  <img src={imageForm.main_image} alt="Principal" className="w-full h-full object-cover" />
                  <button
                    onClick={() => setImageForm({...imageForm, main_image: ""})}
                    className="absolute top-1 right-1 p-1 bg-red-500/80 rounded-full text-white hover:bg-red-500"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              )}
            </div>

            {/* Additional Images */}
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Imágenes Adicionales (hasta 3)</Label>
              <div className="grid grid-cols-3 gap-4">
                {[0, 1, 2].map((index) => (
                  <div key={index} className="space-y-2">
                    <Input
                      value={imageForm.images[index]}
                      onChange={(e) => {
                        const newImages = [...imageForm.images];
                        newImages[index] = e.target.value;
                        setImageForm({...imageForm, images: newImages});
                      }}
                      className="bg-[#0D0D0D] border-[#27272A] text-white text-xs"
                      placeholder={`Imagen ${index + 1}`}
                    />
                    {imageForm.images[index] && (
                      <div className="relative aspect-square rounded-lg overflow-hidden bg-[#0D0D0D]">
                        <img src={imageForm.images[index]} alt={`Adicional ${index + 1}`} className="w-full h-full object-cover" />
                        <button
                          onClick={() => {
                            const newImages = [...imageForm.images];
                            newImages[index] = "";
                            setImageForm({...imageForm, images: newImages});
                          }}
                          className="absolute top-1 right-1 p-1 bg-red-500/80 rounded-full text-white hover:bg-red-500"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Button onClick={handleImageSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Image className="h-4 w-4 mr-2" />}
              Guardar Imágenes
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Imagen</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Producto</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Categoría</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Precio</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Costo</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Margen</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Receta</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.map((product) => (
                    <TableRow key={product.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell>
                        {product.main_image ? (
                          <img 
                            src={product.main_image} 
                            alt={product.name} 
                            className="w-10 h-10 rounded-lg object-cover"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-lg bg-[#27272A] flex items-center justify-center">
                            <Coffee className="h-5 w-5 text-[#71717A]" />
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-white font-medium">{product.name}</TableCell>
                      <TableCell>
                        <Badge className="bg-[#27272A] text-[#A1A1AA]">
                          {getCategoryName(product.category_id)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-white text-right">{formatCurrency(product.price)}</TableCell>
                      <TableCell className="text-[#A1A1AA] text-right">{formatCurrency(product.cost)}</TableCell>
                      <TableCell className="text-right">
                        <span className={`font-bold ${product.margin >= 50 ? 'text-[#8FBC8F]' : product.margin >= 30 ? 'text-[#D97706]' : 'text-red-400'}`}>
                          {product.margin}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge className={product.has_recipe ? 'bg-[#708238]/20 text-[#708238]' : 'bg-[#27272A] text-[#71717A]'}>
                          {product.has_recipe ? (
                            <><BookOpen className="h-3 w-3 mr-1" /> Sí</>
                          ) : "No"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={product.is_active ? 'status-active' : 'status-inactive'}>
                          {product.is_active ? "Activo" : "Inactivo"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {isAdmin() && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openImageDialog(product)}
                              className="text-[#708238] hover:text-[#8FBC8F] hover:bg-[#708238]/10"
                              title="Imágenes"
                            >
                              <Image className="h-4 w-4" />
                            </Button>
                          )}
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
