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
import { BookOpen, Plus, Pencil, Trash2, Loader2, ChefHat, DollarSign } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Recipes = () => {
  const [recipes, setRecipes] = useState([]);
  const [products, setProducts] = useState([]);
  const [ingredients, setIngredients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingRecipe, setEditingRecipe] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    product_id: "",
    ingredients: [],
    portions: 1,
    auto_deduct: true
  });
  
  const [currentIngredient, setCurrentIngredient] = useState({ ingredient_id: "", quantity: 0 });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [recipesRes, productsRes, ingredientsRes] = await Promise.all([
        axios.get(`${API}/recipes`),
        axios.get(`${API}/products`),
        axios.get(`${API}/ingredients`),
      ]);
      setRecipes(recipesRes.data);
      setProducts(productsRes.data);
      setIngredients(ingredientsRes.data.filter(i => i.is_active));
    } catch (error) {
      toast.error("Error al cargar recetas");
    } finally {
      setLoading(false);
    }
  };

  const addIngredient = () => {
    if (!currentIngredient.ingredient_id || currentIngredient.quantity <= 0) {
      toast.error("Selecciona ingrediente y cantidad");
      return;
    }
    
    // Check if already exists
    if (formData.ingredients.some(i => i.ingredient_id === currentIngredient.ingredient_id)) {
      toast.error("Este ingrediente ya está en la receta");
      return;
    }
    
    const ing = ingredients.find(i => i.id === currentIngredient.ingredient_id);
    setFormData({
      ...formData,
      ingredients: [...formData.ingredients, {
        ...currentIngredient,
        ingredient_name: ing?.name,
        unit: ing?.unit,
        cost_per_unit: ing?.cost_per_unit
      }]
    });
    setCurrentIngredient({ ingredient_id: "", quantity: 0 });
  };

  const removeIngredient = (index) => {
    setFormData({
      ...formData,
      ingredients: formData.ingredients.filter((_, i) => i !== index)
    });
  };

  const calculateCost = () => {
    const total = formData.ingredients.reduce((sum, ing) => {
      return sum + (ing.cost_per_unit || 0) * ing.quantity;
    }, 0);
    return total / formData.portions;
  };

  const handleSubmit = async () => {
    if (!formData.product_id || formData.ingredients.length === 0) {
      toast.error("Selecciona producto y agrega ingredientes");
      return;
    }
    setIsSubmitting(true);
    try {
      const data = {
        product_id: formData.product_id,
        ingredients: formData.ingredients.map(i => ({
          ingredient_id: i.ingredient_id,
          quantity: i.quantity
        })),
        portions: formData.portions,
        auto_deduct: formData.auto_deduct
      };
      
      if (editingRecipe) {
        await axios.put(`${API}/recipes/${editingRecipe.id}`, data);
        toast.success("Receta actualizada");
      } else {
        await axios.post(`${API}/recipes`, data);
        toast.success("Receta creada");
      }
      setIsDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al guardar receta");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar esta receta?")) return;
    try {
      await axios.delete(`${API}/recipes/${id}`);
      toast.success("Receta eliminada");
      fetchData();
    } catch (error) {
      toast.error("Error al eliminar");
    }
  };

  const openEditDialog = (recipe) => {
    setEditingRecipe(recipe);
    setFormData({
      product_id: recipe.product_id,
      ingredients: recipe.ingredients.map(i => ({
        ingredient_id: i.ingredient_id,
        quantity: i.quantity,
        ingredient_name: i.ingredient_name,
        unit: i.unit,
        cost_per_unit: i.cost_per_unit
      })),
      portions: recipe.portions,
      auto_deduct: recipe.auto_deduct
    });
    setIsDialogOpen(true);
  };

  const resetForm = () => {
    setEditingRecipe(null);
    setFormData({ product_id: "", ingredients: [], portions: 1, auto_deduct: true });
    setCurrentIngredient({ ingredient_id: "", quantity: 0 });
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  // Products without recipes (for creating new)
  const productsWithoutRecipe = products.filter(p => !recipes.some(r => r.product_id === p.id));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="recipes-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Recetas</h1>
          <p className="text-[#A1A1AA] mt-1">Define los ingredientes de cada producto para costeo automático</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={(open) => { setIsDialogOpen(open); if (!open) resetForm(); }}>
          <DialogTrigger asChild>
            <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-recipe-button">
              <Plus className="h-4 w-4 mr-2" />
              Nueva Receta
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#161616] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="text-white font-manrope flex items-center gap-2">
                <ChefHat className="h-5 w-5 text-[#708238]" />
                {editingRecipe ? "Editar Receta" : "Nueva Receta"}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-6 mt-4">
              {/* Product Selection */}
              <div className="space-y-2">
                <Label className="text-[#EDEDED]">Producto *</Label>
                <Select 
                  value={formData.product_id} 
                  onValueChange={(v) => setFormData({...formData, product_id: v})}
                  disabled={!!editingRecipe}
                >
                  <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                    <SelectValue placeholder="Seleccionar producto" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#161616] border-[#27272A]">
                    {(editingRecipe ? products : productsWithoutRecipe).map((p) => (
                      <SelectItem key={p.id} value={p.id} className="text-white hover:bg-[#27272A]">
                        {p.name} - {formatCurrency(p.price)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Add Ingredient */}
              <div className="bg-[#0D0D0D] rounded-lg p-4 space-y-4">
                <Label className="text-[#EDEDED]">Agregar Ingrediente</Label>
                <div className="grid grid-cols-3 gap-3">
                  <Select 
                    value={currentIngredient.ingredient_id} 
                    onValueChange={(v) => setCurrentIngredient({...currentIngredient, ingredient_id: v})}
                  >
                    <SelectTrigger className="col-span-2 bg-[#161616] border-[#27272A] text-white">
                      <SelectValue placeholder="Ingrediente" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {ingredients.map((i) => (
                        <SelectItem key={i.id} value={i.id} className="text-white hover:bg-[#27272A]">
                          {i.name} ({i.unit}) - {formatCurrency(i.cost_per_unit)}/{i.unit}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    step="0.001"
                    placeholder="Cantidad"
                    value={currentIngredient.quantity || ""}
                    onChange={(e) => setCurrentIngredient({...currentIngredient, quantity: parseFloat(e.target.value) || 0})}
                    className="bg-[#161616] border-[#27272A] text-white"
                  />
                </div>
                <Button 
                  onClick={addIngredient} 
                  variant="outline" 
                  className="w-full bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Agregar a la receta
                </Button>
              </div>

              {/* Ingredients List */}
              {formData.ingredients.length > 0 && (
                <div className="border border-[#27272A] rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                        <TableHead className="text-[#A1A1AA]">Ingrediente</TableHead>
                        <TableHead className="text-[#A1A1AA] text-center">Cantidad</TableHead>
                        <TableHead className="text-[#A1A1AA] text-right">Costo</TableHead>
                        <TableHead className="w-[50px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {formData.ingredients.map((ing, index) => (
                        <TableRow key={index} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                          <TableCell className="text-white">{ing.ingredient_name}</TableCell>
                          <TableCell className="text-white text-center">{ing.quantity} {ing.unit}</TableCell>
                          <TableCell className="text-white text-right">
                            {formatCurrency((ing.cost_per_unit || 0) * ing.quantity)}
                          </TableCell>
                          <TableCell>
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              onClick={() => removeIngredient(index)}
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

              {/* Portions & Auto Deduct */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Porciones por receta</Label>
                  <Input
                    type="number"
                    min="1"
                    value={formData.portions}
                    onChange={(e) => setFormData({...formData, portions: parseInt(e.target.value) || 1})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Descuento automático</Label>
                  <div className="flex items-center gap-3 h-10">
                    <Switch
                      checked={formData.auto_deduct}
                      onCheckedChange={(checked) => setFormData({...formData, auto_deduct: checked})}
                    />
                    <span className="text-sm text-[#A1A1AA]">
                      {formData.auto_deduct ? "Descontar al vender" : "Manual"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Cost Summary */}
              {formData.ingredients.length > 0 && (
                <div className="bg-[#0D0D0D] rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-5 w-5 text-[#708238]" />
                      <span className="text-[#A1A1AA]">Costo por porción:</span>
                    </div>
                    <span className="text-2xl font-bold text-[#708238]">
                      {formatCurrency(calculateCost())}
                    </span>
                  </div>
                  {formData.product_id && (
                    <div className="mt-2 pt-2 border-t border-[#27272A]">
                      <div className="flex justify-between text-sm">
                        <span className="text-[#71717A]">Precio de venta:</span>
                        <span className="text-white">
                          {formatCurrency(products.find(p => p.id === formData.product_id)?.price || 0)}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm mt-1">
                        <span className="text-[#71717A]">Margen:</span>
                        <span className="text-[#8FBC8F]">
                          {(() => {
                            const price = products.find(p => p.id === formData.product_id)?.price || 0;
                            const cost = calculateCost();
                            return price > 0 ? `${(((price - cost) / price) * 100).toFixed(1)}%` : '0%';
                          })()}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Submit */}
              <Button 
                onClick={handleSubmit} 
                disabled={isSubmitting} 
                className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
              >
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {editingRecipe ? "Actualizar" : "Crear"} Receta
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Recipes List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {recipes.map((recipe) => {
          const product = products.find(p => p.id === recipe.product_id);
          const margin = product && product.price > 0 
            ? ((product.price - recipe.calculated_cost) / product.price * 100).toFixed(1) 
            : 0;
          
          return (
            <Card key={recipe.id} className="bg-[#161616] border-[#27272A] card-hover">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-white font-manrope text-lg">{recipe.product_name}</CardTitle>
                    <p className="text-[#71717A] text-sm mt-1">{recipe.ingredients.length} ingredientes</p>
                  </div>
                  <Badge className={recipe.auto_deduct ? 'bg-[#708238]/20 text-[#708238]' : 'bg-[#27272A] text-[#A1A1AA]'}>
                    {recipe.auto_deduct ? "Auto" : "Manual"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {/* Ingredients preview */}
                  <div className="space-y-1">
                    {recipe.ingredients.slice(0, 3).map((ing, i) => (
                      <div key={i} className="flex justify-between text-sm">
                        <span className="text-[#A1A1AA]">{ing.ingredient_name}</span>
                        <span className="text-white">{ing.quantity} {ing.unit}</span>
                      </div>
                    ))}
                    {recipe.ingredients.length > 3 && (
                      <p className="text-xs text-[#71717A]">+{recipe.ingredients.length - 3} más...</p>
                    )}
                  </div>
                  
                  {/* Cost info */}
                  <div className="pt-3 border-t border-[#27272A] space-y-2">
                    <div className="flex justify-between">
                      <span className="text-[#71717A]">Costo:</span>
                      <span className="text-white font-medium">{formatCurrency(recipe.calculated_cost)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#71717A]">Precio:</span>
                      <span className="text-white">{formatCurrency(product?.price || 0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#71717A]">Margen:</span>
                      <span className={`font-bold ${parseFloat(margin) >= 50 ? 'text-[#8FBC8F]' : parseFloat(margin) >= 30 ? 'text-[#D97706]' : 'text-red-400'}`}>
                        {margin}%
                      </span>
                    </div>
                  </div>
                  
                  {/* Actions */}
                  <div className="flex gap-2 pt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEditDialog(recipe)}
                      className="flex-1 bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white"
                    >
                      <Pencil className="h-4 w-4 mr-2" />
                      Editar
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(recipe.id)}
                      className="bg-transparent border-[#7F1D1D] text-red-400 hover:bg-[#7F1D1D]/20"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {recipes.length === 0 && (
        <Card className="bg-[#161616] border-[#27272A]">
          <CardContent className="text-center py-12 text-[#71717A]">
            <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No hay recetas registradas</p>
            <p className="text-sm mt-2">Crea recetas para calcular automáticamente los costos de tus productos</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Recipes;
