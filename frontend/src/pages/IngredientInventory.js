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
import { toast } from "sonner";
import axios from "axios";
import { Package, Plus, ArrowUp, ArrowDown, AlertTriangle, Loader2, RefreshCw, Clock } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const IngredientInventory = () => {
  const { user, isAdmin, canManage } = useAuth();
  const [inventory, setInventory] = useState([]);
  const [ingredients, setIngredients] = useState([]);
  const [cafeterias, setCafeterias] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isMovementDialogOpen, setIsMovementDialogOpen] = useState(false);
  const [selectedCafeteria, setSelectedCafeteria] = useState("all");
  const [selectedItem, setSelectedItem] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [newItem, setNewItem] = useState({ ingredient_id: "", cafeteria_id: "", quantity: 10, min_stock: 5 });
  const [movement, setMovement] = useState({ quantity: 1, movement_type: "entrada", reason: "" });

  useEffect(() => {
    fetchData();
  }, [selectedCafeteria]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = selectedCafeteria !== "all" ? { cafeteria_id: selectedCafeteria } : {};
      const [inventoryRes, ingredientsRes, cafeteriasRes, alertsRes] = await Promise.all([
        axios.get(`${API}/ingredient-inventory`, { params }),
        axios.get(`${API}/ingredients`),
        axios.get(`${API}/cafeterias`),
        axios.get(`${API}/ingredient-inventory/alerts`, { params }),
      ]);
      setInventory(inventoryRes.data);
      setIngredients(ingredientsRes.data.filter(i => i.is_active));
      setCafeterias(cafeteriasRes.data);
      setAlerts(alertsRes.data);
    } catch (error) {
      toast.error("Error al cargar inventario");
    } finally {
      setLoading(false);
    }
  };

  const handleAddItem = async () => {
    if (!newItem.ingredient_id || !newItem.cafeteria_id) {
      toast.error("Completa todos los campos");
      return;
    }
    setIsSubmitting(true);
    try {
      await axios.post(`${API}/ingredient-inventory`, newItem);
      toast.success("Ingrediente agregado al inventario");
      setIsAddDialogOpen(false);
      setNewItem({ ingredient_id: "", cafeteria_id: "", quantity: 10, min_stock: 5 });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al agregar");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMovement = async () => {
    if (!selectedItem || movement.quantity <= 0) {
      toast.error("Cantidad inválida");
      return;
    }
    setIsSubmitting(true);
    try {
      await axios.post(`${API}/ingredient-inventory/movement`, {
        inventory_id: selectedItem.id,
        ...movement
      });
      toast.success("Movimiento registrado");
      setIsMovementDialogOpen(false);
      setMovement({ quantity: 1, movement_type: "entrada", reason: "" });
      setSelectedItem(null);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al registrar movimiento");
    } finally {
      setIsSubmitting(false);
    }
  };

  const openMovementDialog = (item, type) => {
    setSelectedItem(item);
    setMovement({ quantity: 1, movement_type: type, reason: "" });
    setIsMovementDialogOpen(true);
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  const criticalAlerts = alerts.filter(a => a.alert_type === "critical");
  const warningAlerts = alerts.filter(a => a.alert_type === "warning");

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="ingredient-inventory-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Inventario de Ingredientes</h1>
          <p className="text-[#A1A1AA] mt-1">Stock de materia prima por cafetería</p>
        </div>
        
        <div className="flex items-center gap-3">
          {isAdmin() && (
            <Select value={selectedCafeteria} onValueChange={setSelectedCafeteria}>
              <SelectTrigger className="w-[180px] bg-[#161616] border-[#27272A] text-white">
                <SelectValue placeholder="Filtrar por cafetería" />
              </SelectTrigger>
              <SelectContent className="bg-[#161616] border-[#27272A]">
                <SelectItem value="all" className="text-white hover:bg-[#27272A]">Todas</SelectItem>
                {cafeterias.map((cafe) => (
                  <SelectItem key={cafe.id} value={cafe.id} className="text-white hover:bg-[#27272A]">
                    {cafe.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          
          {canManage() && (
            <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-ingredient-inventory-button">
                  <Plus className="h-4 w-4 mr-2" />
                  Agregar
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-[#161616] border-[#27272A]">
                <DialogHeader>
                  <DialogTitle className="text-white font-manrope">Agregar Ingrediente al Inventario</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Ingrediente</Label>
                    <Select value={newItem.ingredient_id} onValueChange={(v) => setNewItem({...newItem, ingredient_id: v})}>
                      <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                        <SelectValue placeholder="Seleccionar ingrediente" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A]">
                        {ingredients.map((i) => (
                          <SelectItem key={i.id} value={i.id} className="text-white hover:bg-[#27272A]">
                            {i.name} ({i.unit})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Cafetería</Label>
                    <Select value={newItem.cafeteria_id} onValueChange={(v) => setNewItem({...newItem, cafeteria_id: v})}>
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
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Cantidad Inicial</Label>
                      <Input
                        type="number"
                        value={newItem.quantity}
                        onChange={(e) => setNewItem({...newItem, quantity: parseFloat(e.target.value)})}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-[#EDEDED]">Stock Mínimo</Label>
                      <Input
                        type="number"
                        value={newItem.min_stock}
                        onChange={(e) => setNewItem({...newItem, min_stock: parseFloat(e.target.value)})}
                        className="bg-[#0D0D0D] border-[#27272A] text-white"
                      />
                    </div>
                  </div>
                  <Button onClick={handleAddItem} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
                    Agregar
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* Alerts */}
      {criticalAlerts.length > 0 && (
        <Card className="bg-red-900/20 border-red-500/30">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
              <div>
                <p className="text-red-400 font-medium">Alerta Crítica: Stock próximo a agotarse</p>
                <ul className="mt-2 space-y-1">
                  {criticalAlerts.slice(0, 3).map((alert, i) => (
                    <li key={i} className="text-red-300 text-sm flex items-center gap-2">
                      <Clock className="h-3 w-3" />
                      {alert.ingredient_name} en {alert.cafeteria_name}: {alert.days_until_stockout} días restantes
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {warningAlerts.length > 0 && (
        <Card className="bg-[#D97706]/10 border-[#D97706]/30">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-[#D97706] mt-0.5" />
              <div>
                <p className="text-[#D97706] font-medium">{warningAlerts.length} ingredientes con stock bajo</p>
                <p className="text-[#D97706]/80 text-sm mt-1">
                  Considere reabastecer pronto para evitar faltantes
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Movement Dialog */}
      <Dialog open={isMovementDialogOpen} onOpenChange={setIsMovementDialogOpen}>
        <DialogContent className="bg-[#161616] border-[#27272A]">
          <DialogHeader>
            <DialogTitle className="text-white font-manrope">
              {movement.movement_type === "entrada" ? "Entrada de Stock" : 
               movement.movement_type === "salida" ? "Salida de Stock" : 
               movement.movement_type === "merma" ? "Registrar Merma" : "Ajuste de Inventario"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <p className="text-[#A1A1AA]">
              Ingrediente: <span className="text-white">{selectedItem?.ingredient_name}</span>
            </p>
            <p className="text-[#A1A1AA]">
              Stock actual: <span className="text-white">{selectedItem?.quantity} {selectedItem?.unit}</span>
            </p>
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Cantidad ({selectedItem?.unit})</Label>
              <Input
                type="number"
                step="0.01"
                min="0.01"
                value={movement.quantity}
                onChange={(e) => setMovement({...movement, quantity: parseFloat(e.target.value)})}
                className="bg-[#0D0D0D] border-[#27272A] text-white"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#EDEDED]">Razón (opcional)</Label>
              <Input
                value={movement.reason}
                onChange={(e) => setMovement({...movement, reason: e.target.value})}
                placeholder="Motivo del movimiento"
                className="bg-[#0D0D0D] border-[#27272A] text-white placeholder:text-[#52525B]"
              />
            </div>
            <Button onClick={handleMovement} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Confirmar
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Inventory Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Package className="h-5 w-5 text-[#708238]" />
            Stock de Ingredientes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {inventory.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <Package className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay ingredientes en el inventario</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Ingrediente</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Cafetería</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-center">Stock</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-center">Mínimo</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Valor</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-center">Días Rest.</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Estado</TableHead>
                    {canManage() && <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Acciones</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {inventory.map((item) => (
                    <TableRow 
                      key={item.id} 
                      className={`border-[#27272A] hover:bg-[#1F1F1F]/50 ${item.is_low_stock ? 'low-stock' : ''}`}
                    >
                      <TableCell className="text-white font-medium">
                        {item.ingredient_name}
                        <span className="text-[#71717A] text-xs ml-2">({item.unit})</span>
                      </TableCell>
                      <TableCell className="text-[#A1A1AA]">{item.cafeteria_name}</TableCell>
                      <TableCell className="text-center">
                        <span className={`font-bold ${item.is_low_stock ? 'text-[#D97706]' : 'text-white'}`}>
                          {item.quantity.toFixed(2)}
                        </span>
                      </TableCell>
                      <TableCell className="text-[#71717A] text-center">{item.min_stock}</TableCell>
                      <TableCell className="text-white text-right">
                        {formatCurrency(item.quantity * item.cost_per_unit)}
                      </TableCell>
                      <TableCell className="text-center">
                        {item.days_until_stockout ? (
                          <Badge className={
                            item.days_until_stockout < 3 ? 'bg-red-500/20 text-red-400' :
                            item.days_until_stockout < 7 ? 'bg-[#D97706]/20 text-[#D97706]' :
                            'bg-[#27272A] text-[#A1A1AA]'
                          }>
                            {item.days_until_stockout} días
                          </Badge>
                        ) : (
                          <span className="text-[#71717A]">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge className={item.is_low_stock ? 'bg-[#D97706]/20 text-[#D97706]' : 'bg-[#3E4B28]/30 text-[#8FBC8F]'}>
                          {item.is_low_stock ? 'Stock Bajo' : 'Normal'}
                        </Badge>
                      </TableCell>
                      {canManage() && (
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openMovementDialog(item, "entrada")}
                              className="bg-transparent border-[#3E4B28] text-[#8FBC8F] hover:bg-[#3E4B28]/20"
                              title="Entrada"
                            >
                              <ArrowUp className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openMovementDialog(item, "salida")}
                              className="bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A]"
                              title="Salida"
                            >
                              <ArrowDown className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openMovementDialog(item, "merma")}
                              className="bg-transparent border-[#7F1D1D] text-red-400 hover:bg-[#7F1D1D]/20"
                              title="Merma"
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      )}
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

export default IngredientInventory;
