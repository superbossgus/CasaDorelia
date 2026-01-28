import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { toast } from "sonner";
import axios from "axios";
import { Receipt, Plus, Loader2, Trash2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Purchases = () => {
  const { isAdmin } = useAuth();
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [cafeterias, setCafeterias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedCafeteria, setSelectedCafeteria] = useState("all");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    supplier_id: "", cafeteria_id: "", items: [], notes: ""
  });
  const [currentItem, setCurrentItem] = useState({ product_id: "", quantity: 1, unit_cost: 0 });

  useEffect(() => {
    fetchData();
  }, [selectedCafeteria]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [purchasesRes, suppliersRes, productsRes, cafeteriasRes] = await Promise.all([
        axios.get(`${API}/purchases`, { 
          params: selectedCafeteria !== "all" ? { cafeteria_id: selectedCafeteria } : {} 
        }),
        axios.get(`${API}/suppliers`),
        axios.get(`${API}/products`),
        axios.get(`${API}/cafeterias`),
      ]);
      setPurchases(purchasesRes.data);
      setSuppliers(suppliersRes.data.filter(s => s.is_active));
      setProducts(productsRes.data);
      setCafeterias(cafeteriasRes.data);
    } catch (error) {
      toast.error("Error al cargar datos");
    } finally {
      setLoading(false);
    }
  };

  const addItem = () => {
    if (!currentItem.product_id || currentItem.quantity <= 0 || currentItem.unit_cost <= 0) {
      toast.error("Completa los datos del producto");
      return;
    }
    const product = products.find(p => p.id === currentItem.product_id);
    setFormData({
      ...formData,
      items: [...formData.items, { ...currentItem, product_name: product?.name }]
    });
    setCurrentItem({ product_id: "", quantity: 1, unit_cost: 0 });
  };

  const removeItem = (index) => {
    setFormData({
      ...formData,
      items: formData.items.filter((_, i) => i !== index)
    });
  };

  const handleSubmit = async () => {
    if (!formData.supplier_id || !formData.cafeteria_id || formData.items.length === 0) {
      toast.error("Completa todos los campos y agrega al menos un producto");
      return;
    }
    setIsSubmitting(true);
    try {
      await axios.post(`${API}/purchases`, formData);
      toast.success("Compra registrada exitosamente");
      setIsDialogOpen(false);
      setFormData({ supplier_id: "", cafeteria_id: "", items: [], notes: "" });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al registrar compra");
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  const calculateTotal = () => {
    return formData.items.reduce((sum, item) => sum + (item.quantity * item.unit_cost), 0);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="purchases-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Compras</h1>
          <p className="text-[#A1A1AA] mt-1">Historial de compras a proveedores</p>
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
          
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[#708238] hover:bg-[#5a692d] text-white" data-testid="add-purchase-button">
                <Plus className="h-4 w-4 mr-2" />
                Nueva Compra
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#161616] border-[#27272A] max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="text-white font-manrope">Registrar Compra</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Proveedor</Label>
                    <Select value={formData.supplier_id} onValueChange={(v) => setFormData({...formData, supplier_id: v})}>
                      <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A]">
                        {suppliers.map((s) => (
                          <SelectItem key={s.id} value={s.id} className="text-white hover:bg-[#27272A]">{s.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-[#EDEDED]">Cafetería</Label>
                    <Select value={formData.cafeteria_id} onValueChange={(v) => setFormData({...formData, cafeteria_id: v})}>
                      <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white">
                        <SelectValue placeholder="Seleccionar" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A]">
                        {cafeterias.map((c) => (
                          <SelectItem key={c.id} value={c.id} className="text-white hover:bg-[#27272A]">{c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Add Item */}
                <div className="bg-[#0D0D0D] rounded-lg p-4 space-y-4">
                  <Label className="text-[#EDEDED]">Agregar Producto</Label>
                  <div className="grid grid-cols-4 gap-3">
                    <Select value={currentItem.product_id} onValueChange={(v) => setCurrentItem({...currentItem, product_id: v})}>
                      <SelectTrigger className="col-span-2 bg-[#161616] border-[#27272A] text-white">
                        <SelectValue placeholder="Producto" />
                      </SelectTrigger>
                      <SelectContent className="bg-[#161616] border-[#27272A]">
                        {products.map((p) => (
                          <SelectItem key={p.id} value={p.id} className="text-white hover:bg-[#27272A]">{p.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      placeholder="Cantidad"
                      value={currentItem.quantity}
                      onChange={(e) => setCurrentItem({...currentItem, quantity: parseFloat(e.target.value) || 0})}
                      className="bg-[#161616] border-[#27272A] text-white"
                    />
                    <Input
                      type="number"
                      placeholder="Costo unit."
                      value={currentItem.unit_cost}
                      onChange={(e) => setCurrentItem({...currentItem, unit_cost: parseFloat(e.target.value) || 0})}
                      className="bg-[#161616] border-[#27272A] text-white"
                    />
                  </div>
                  <Button onClick={addItem} variant="outline" className="w-full bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white">
                    <Plus className="h-4 w-4 mr-2" />
                    Agregar
                  </Button>
                </div>

                {/* Items List */}
                {formData.items.length > 0 && (
                  <div className="border border-[#27272A] rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                          <TableHead className="text-[#A1A1AA]">Producto</TableHead>
                          <TableHead className="text-[#A1A1AA] text-center">Cantidad</TableHead>
                          <TableHead className="text-[#A1A1AA] text-right">Costo Unit.</TableHead>
                          <TableHead className="text-[#A1A1AA] text-right">Subtotal</TableHead>
                          <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {formData.items.map((item, index) => (
                          <TableRow key={index} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                            <TableCell className="text-white">{item.product_name}</TableCell>
                            <TableCell className="text-white text-center">{item.quantity}</TableCell>
                            <TableCell className="text-white text-right">{formatCurrency(item.unit_cost)}</TableCell>
                            <TableCell className="text-white text-right font-medium">{formatCurrency(item.quantity * item.unit_cost)}</TableCell>
                            <TableCell>
                              <Button variant="ghost" size="sm" onClick={() => removeItem(index)} className="text-red-400 hover:text-red-300 hover:bg-red-400/10">
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    <div className="bg-[#1F1F1F] p-4 flex justify-between items-center">
                      <span className="text-[#A1A1AA]">Total</span>
                      <span className="text-white text-xl font-bold">{formatCurrency(calculateTotal())}</span>
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Notas</Label>
                  <Input
                    value={formData.notes}
                    onChange={(e) => setFormData({...formData, notes: e.target.value})}
                    className="bg-[#0D0D0D] border-[#27272A] text-white"
                    placeholder="Notas adicionales (opcional)"
                  />
                </div>

                <Button onClick={handleSubmit} disabled={isSubmitting} className="w-full bg-[#708238] hover:bg-[#5a692d] text-white">
                  {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Receipt className="h-4 w-4 mr-2" />}
                  Registrar Compra - {formatCurrency(calculateTotal())}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Purchases Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Receipt className="h-5 w-5 text-[#708238]" />
            Historial de Compras
          </CardTitle>
        </CardHeader>
        <CardContent>
          {purchases.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <Receipt className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay compras registradas</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">ID</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Proveedor</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Cafetería</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-center">Productos</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Total</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Fecha</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {purchases.map((purchase) => (
                    <TableRow key={purchase.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                      <TableCell className="font-mono text-xs text-[#71717A]">{purchase.id.slice(0, 8)}...</TableCell>
                      <TableCell className="text-white">{purchase.supplier_name}</TableCell>
                      <TableCell className="text-[#A1A1AA]">{purchase.cafeteria_name}</TableCell>
                      <TableCell className="text-[#A1A1AA] text-center">{purchase.items.length}</TableCell>
                      <TableCell className="text-white text-right font-medium">{formatCurrency(purchase.total)}</TableCell>
                      <TableCell className="text-[#71717A] text-sm">
                        {new Date(purchase.created_at).toLocaleDateString("es-MX", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric"
                        })}
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

export default Purchases;
