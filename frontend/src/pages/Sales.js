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
import { Plus, ShoppingCart, Trash2, CreditCard, Banknote, Smartphone, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Sales = () => {
  const { user, isAdmin } = useAuth();
  const [sales, setSales] = useState([]);
  const [products, setProducts] = useState([]);
  const [cafeterias, setCafeterias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedCafeteria, setSelectedCafeteria] = useState("all");
  
  // New sale form
  const [saleItems, setSaleItems] = useState([]);
  const [saleCafeteria, setSaleCafeteria] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("efectivo");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchData();
  }, [selectedCafeteria]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [salesRes, productsRes, cafeteriasRes] = await Promise.all([
        axios.get(`${API}/sales`, { 
          params: selectedCafeteria !== "all" ? { cafeteria_id: selectedCafeteria } : {} 
        }),
        axios.get(`${API}/products`),
        axios.get(`${API}/cafeterias`),
      ]);
      setSales(salesRes.data);
      setProducts(productsRes.data.filter(p => p.is_active));
      setCafeterias(cafeteriasRes.data);
      
      // Set default cafeteria for new sales
      if (cafeteriasRes.data.length > 0 && !saleCafeteria) {
        setSaleCafeteria(user?.cafeteria_id || cafeteriasRes.data[0].id);
      }
    } catch (error) {
      toast.error("Error al cargar datos");
    } finally {
      setLoading(false);
    }
  };

  const addProduct = (productId) => {
    const product = products.find(p => p.id === productId);
    if (!product) return;

    const existingIndex = saleItems.findIndex(item => item.product_id === productId);
    if (existingIndex >= 0) {
      const updated = [...saleItems];
      updated[existingIndex].quantity += 1;
      updated[existingIndex].subtotal = updated[existingIndex].quantity * product.price;
      setSaleItems(updated);
    } else {
      setSaleItems([...saleItems, {
        product_id: product.id,
        product_name: product.name,
        quantity: 1,
        unit_price: product.price,
        subtotal: product.price
      }]);
    }
  };

  const updateQuantity = (index, quantity) => {
    if (quantity < 1) return removeItem(index);
    const updated = [...saleItems];
    updated[index].quantity = quantity;
    updated[index].subtotal = quantity * updated[index].unit_price;
    setSaleItems(updated);
  };

  const removeItem = (index) => {
    setSaleItems(saleItems.filter((_, i) => i !== index));
  };

  const calculateTotal = () => {
    const subtotal = saleItems.reduce((sum, item) => sum + item.subtotal, 0);
    const tax = subtotal * 0.16;
    return { subtotal, tax, total: subtotal + tax };
  };

  const handleSubmit = async () => {
    if (!saleCafeteria || saleItems.length === 0) {
      toast.error("Selecciona una cafetería y agrega productos");
      return;
    }

    setIsSubmitting(true);
    try {
      await axios.post(`${API}/sales`, {
        cafeteria_id: saleCafeteria,
        items: saleItems,
        payment_method: paymentMethod,
      });
      toast.success("Venta registrada exitosamente");
      setIsDialogOpen(false);
      setSaleItems([]);
      setPaymentMethod("efectivo");
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al registrar venta");
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  const paymentIcons = {
    efectivo: Banknote,
    tarjeta: CreditCard,
    clip: Smartphone,
  };

  const paymentLabels = {
    efectivo: "Efectivo",
    tarjeta: "Tarjeta",
    clip: "Clip",
  };

  const { subtotal, tax, total } = calculateTotal();

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="sales-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Ventas</h1>
          <p className="text-[#A1A1AA] mt-1">Gestiona las ventas de tus cafeterías</p>
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
              <Button 
                className="bg-[#708238] hover:bg-[#5a692d] text-white"
                data-testid="new-sale-button"
              >
                <Plus className="h-4 w-4 mr-2" />
                Nueva Venta
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#161616] border-[#27272A] max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="text-white font-manrope flex items-center gap-2">
                  <ShoppingCart className="h-5 w-5 text-[#708238]" />
                  Nueva Venta
                </DialogTitle>
              </DialogHeader>
              
              <div className="space-y-6 mt-4">
                {/* Cafeteria Selection */}
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Cafetería</Label>
                  <Select value={saleCafeteria} onValueChange={setSaleCafeteria}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white" data-testid="sale-cafeteria-select">
                      <SelectValue placeholder="Seleccionar cafetería" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {cafeterias.map((cafe) => (
                        <SelectItem key={cafe.id} value={cafe.id} className="text-white hover:bg-[#27272A]">
                          {cafe.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Product Selection */}
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Agregar Producto</Label>
                  <Select onValueChange={addProduct}>
                    <SelectTrigger className="bg-[#0D0D0D] border-[#27272A] text-white" data-testid="add-product-select">
                      <SelectValue placeholder="Seleccionar producto" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#161616] border-[#27272A]">
                      {products.map((product) => (
                        <SelectItem key={product.id} value={product.id} className="text-white hover:bg-[#27272A]">
                          {product.name} - {formatCurrency(product.price)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Items List */}
                {saleItems.length > 0 && (
                  <div className="border border-[#27272A] rounded-lg overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                          <TableHead className="text-[#A1A1AA]">Producto</TableHead>
                          <TableHead className="text-[#A1A1AA] text-center">Cantidad</TableHead>
                          <TableHead className="text-[#A1A1AA] text-right">Precio</TableHead>
                          <TableHead className="text-[#A1A1AA] text-right">Subtotal</TableHead>
                          <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {saleItems.map((item, index) => (
                          <TableRow key={index} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                            <TableCell className="text-white">{item.product_name}</TableCell>
                            <TableCell>
                              <div className="flex items-center justify-center gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => updateQuantity(index, item.quantity - 1)}
                                  className="h-8 w-8 p-0 bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
                                >
                                  -
                                </Button>
                                <span className="text-white w-8 text-center">{item.quantity}</span>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => updateQuantity(index, item.quantity + 1)}
                                  className="h-8 w-8 p-0 bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
                                >
                                  +
                                </Button>
                              </div>
                            </TableCell>
                            <TableCell className="text-white text-right">{formatCurrency(item.unit_price)}</TableCell>
                            <TableCell className="text-white text-right font-medium">{formatCurrency(item.subtotal)}</TableCell>
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => removeItem(index)}
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

                {/* Totals */}
                {saleItems.length > 0 && (
                  <div className="bg-[#0D0D0D] rounded-lg p-4 space-y-2">
                    <div className="flex justify-between text-[#A1A1AA]">
                      <span>Subtotal</span>
                      <span>{formatCurrency(subtotal)}</span>
                    </div>
                    <div className="flex justify-between text-[#A1A1AA]">
                      <span>IVA (16%)</span>
                      <span>{formatCurrency(tax)}</span>
                    </div>
                    <div className="flex justify-between text-white text-lg font-bold pt-2 border-t border-[#27272A]">
                      <span>Total</span>
                      <span className="text-[#708238]">{formatCurrency(total)}</span>
                    </div>
                  </div>
                )}

                {/* Payment Method */}
                <div className="space-y-2">
                  <Label className="text-[#EDEDED]">Método de Pago</Label>
                  <div className="grid grid-cols-3 gap-3">
                    {Object.entries(paymentLabels).map(([key, label]) => {
                      const Icon = paymentIcons[key];
                      return (
                        <Button
                          key={key}
                          type="button"
                          variant={paymentMethod === key ? "default" : "outline"}
                          onClick={() => setPaymentMethod(key)}
                          data-testid={`payment-${key}`}
                          className={`flex items-center justify-center gap-2 ${
                            paymentMethod === key 
                              ? 'bg-[#708238] hover:bg-[#5a692d] text-white' 
                              : 'bg-transparent border-[#27272A] text-[#A1A1AA] hover:bg-[#27272A] hover:text-white'
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                          {label}
                        </Button>
                      );
                    })}
                  </div>
                </div>

                {/* Submit */}
                <Button
                  onClick={handleSubmit}
                  disabled={isSubmitting || saleItems.length === 0}
                  data-testid="submit-sale-button"
                  className="w-full bg-[#708238] hover:bg-[#5a692d] text-white"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Procesando...
                    </>
                  ) : (
                    <>
                      <ShoppingCart className="mr-2 h-4 w-4" />
                      Registrar Venta - {formatCurrency(total)}
                    </>
                  )}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Sales List */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope">Historial de Ventas</CardTitle>
        </CardHeader>
        <CardContent>
          {sales.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <ShoppingCart className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay ventas registradas</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-[#1F1F1F] border-[#27272A] hover:bg-[#1F1F1F]">
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">ID</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Cafetería</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Productos</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Total</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold text-right">Utilidad</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Pago</TableHead>
                    <TableHead className="text-[#A1A1AA] uppercase text-xs font-bold">Fecha</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sales.slice(0, 50).map((sale) => {
                    const PaymentIcon = paymentIcons[sale.payment_method] || Banknote;
                    return (
                      <TableRow key={sale.id} className="border-[#27272A] hover:bg-[#1F1F1F]/50">
                        <TableCell className="font-mono text-xs text-[#71717A]">
                          {sale.id.slice(0, 8)}...
                        </TableCell>
                        <TableCell className="text-white">{sale.cafeteria_name}</TableCell>
                        <TableCell className="text-[#A1A1AA]">
                          {sale.items.length} {sale.items.length === 1 ? 'producto' : 'productos'}
                        </TableCell>
                        <TableCell className="text-white text-right font-medium">
                          {formatCurrency(sale.total)}
                        </TableCell>
                        <TableCell className={`text-right font-medium ${sale.profit >= 0 ? 'text-[#8FBC8F]' : 'text-red-400'}`}>
                          {formatCurrency(sale.profit)}
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-[#27272A] text-[#A1A1AA] flex items-center gap-1 w-fit">
                            <PaymentIcon className="h-3 w-3" />
                            {paymentLabels[sale.payment_method]}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-[#71717A] text-sm">
                          {new Date(sale.created_at).toLocaleDateString("es-MX", {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit"
                          })}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default Sales;
