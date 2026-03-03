import { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import axios from "axios";
import {
  ShoppingCart, Trash2, Plus, Minus, CreditCard,
  Banknote, Send, Search, X, ChefHat, User,
  Coffee, UtensilsCrossed, Cake, Package, Loader2,
  Receipt, Clock, CheckCircle2
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

// Category icons
const categoryIcons = {
  "Café": Coffee,
  "Bebidas": Coffee,
  "Panadería": Cake,
  "Comida": UtensilsCrossed,
  "Postres": Cake,
  "Otros": Package
};

const PointOfSale = () => {
  const [loading, setLoading] = useState(true);
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [customerName, setCustomerName] = useState("");
  const [orderType, setOrderType] = useState("mostrador");
  const [paymentMethod, setPaymentMethod] = useState("efectivo");
  const [showCheckout, setShowCheckout] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemNote, setItemNote] = useState("");
  const [cafeteriaId, setCafeteriaId] = useState(null);
  const [recentOrders, setRecentOrders] = useState([]);
  
  const token = localStorage.getItem("token");
  const searchRef = useRef(null);

  useEffect(() => {
    fetchCafeteria();
  }, []);

  useEffect(() => {
    if (cafeteriaId) {
      fetchProducts();
      fetchRecentOrders();
    }
  }, [cafeteriaId]);

  const fetchCafeteria = async () => {
    try {
      const response = await axios.get(`${API}/api/cafeterias`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.length > 0) {
        setCafeteriaId(response.data[0].id);
      }
    } catch (error) {
      toast.error("Error al cargar cafetería");
    }
  };

  const fetchProducts = async () => {
    try {
      const response = await axios.get(`${API}/api/pos/products?cafeteria_id=${cafeteriaId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setProducts(response.data);
    } catch (error) {
      toast.error("Error al cargar productos");
    } finally {
      setLoading(false);
    }
  };

  const fetchRecentOrders = async () => {
    try {
      const response = await axios.get(`${API}/api/pos/orders?cafeteria_id=${cafeteriaId}&today_only=true`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRecentOrders(response.data.slice(0, 5));
    } catch (error) {
      console.error("Error fetching recent orders:", error);
    }
  };

  const addToCart = (product) => {
    const existingIndex = cart.findIndex(item => item.product_id === product.id && !item.notes);
    
    if (existingIndex >= 0) {
      const newCart = [...cart];
      newCart[existingIndex].quantity += 1;
      newCart[existingIndex].total_price = newCart[existingIndex].quantity * newCart[existingIndex].unit_price;
      setCart(newCart);
    } else {
      setCart([...cart, {
        product_id: product.id,
        product_name: product.name,
        quantity: 1,
        unit_price: product.price,
        total_price: product.price,
        notes: null,
        category: product.category,
        color: product.color
      }]);
    }
    
    toast.success(`${product.name} agregado`);
  };

  const updateQuantity = (index, delta) => {
    const newCart = [...cart];
    newCart[index].quantity += delta;
    
    if (newCart[index].quantity <= 0) {
      newCart.splice(index, 1);
    } else {
      newCart[index].total_price = newCart[index].quantity * newCart[index].unit_price;
    }
    
    setCart(newCart);
  };

  const removeFromCart = (index) => {
    const newCart = [...cart];
    newCart.splice(index, 1);
    setCart(newCart);
  };

  const openNoteModal = (index) => {
    setSelectedItem(index);
    setItemNote(cart[index].notes || "");
    setShowNoteModal(true);
  };

  const saveItemNote = () => {
    if (selectedItem !== null) {
      const newCart = [...cart];
      newCart[selectedItem].notes = itemNote || null;
      setCart(newCart);
      setShowNoteModal(false);
      setSelectedItem(null);
      setItemNote("");
    }
  };

  const clearCart = () => {
    setCart([]);
    setCustomerName("");
  };

  const subtotal = cart.reduce((sum, item) => sum + item.total_price, 0);
  const tax = subtotal * 0.16;
  const total = subtotal + tax;

  const processOrder = async () => {
    if (cart.length === 0) {
      toast.error("El carrito está vacío");
      return;
    }

    setProcessing(true);
    try {
      const orderData = {
        items: cart,
        customer_name: customerName || null,
        order_type: orderType,
        payment_method: paymentMethod,
        notes: null
      };

      const response = await axios.post(`${API}/api/pos/orders`, orderData, {
        headers: { Authorization: `Bearer ${token}` }
      });

      toast.success(`¡Orden #${response.data.order_number} creada!`);
      clearCart();
      setShowCheckout(false);
      fetchRecentOrders();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Error al procesar orden");
    } finally {
      setProcessing(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
      minimumFractionDigits: 0
    }).format(amount);
  };

  // Get unique categories
  const categories = ["all", ...new Set(products.map(p => p.category).filter(Boolean))];

  // Filter products
  const filteredProducts = products.filter(p => {
    const matchesSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === "all" || p.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-200px)]">
        <Loader2 className="h-8 w-8 animate-spin text-[#708238]" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-120px)] flex gap-4">
      {/* Products Panel */}
      <div className="flex-1 flex flex-col">
        {/* Search and Categories */}
        <div className="mb-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-[#52525B]" />
            <Input
              ref={searchRef}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar producto..."
              className="bg-[#161616] border-[#27272A] text-white pl-11 h-12 text-lg"
            />
            {searchTerm && (
              <button 
                onClick={() => setSearchTerm("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>
          
          <div className="flex gap-2 overflow-x-auto pb-2">
            {categories.map(cat => (
              <Button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                variant={selectedCategory === cat ? "default" : "outline"}
                className={`whitespace-nowrap ${
                  selectedCategory === cat 
                    ? "bg-[#708238] hover:bg-[#5a692d]" 
                    : "border-[#27272A] text-[#A1A1AA] hover:text-white"
                }`}
              >
                {cat === "all" ? "Todos" : cat}
              </Button>
            ))}
          </div>
        </div>

        {/* Products Grid */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {filteredProducts.map(product => {
              const Icon = categoryIcons[product.category] || Package;
              return (
                <button
                  key={product.id}
                  onClick={() => addToCart(product)}
                  disabled={!product.in_stock}
                  className={`relative p-4 rounded-xl border-2 transition-all text-left ${
                    product.in_stock
                      ? "border-transparent hover:border-white hover:scale-105 active:scale-95"
                      : "opacity-50 cursor-not-allowed"
                  }`}
                  style={{ backgroundColor: product.color + "20", borderColor: product.color + "40" }}
                >
                  <div 
                    className="w-12 h-12 rounded-lg flex items-center justify-center mb-3"
                    style={{ backgroundColor: product.color }}
                  >
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="font-bold text-white text-sm mb-1 line-clamp-2">{product.name}</h3>
                  <p className="text-lg font-bold" style={{ color: product.color }}>
                    {formatCurrency(product.price)}
                  </p>
                  {!product.in_stock && (
                    <Badge className="absolute top-2 right-2 bg-red-500/20 text-red-400">
                      Agotado
                    </Badge>
                  )}
                  {product.in_stock && product.stock <= 5 && (
                    <Badge className="absolute top-2 right-2 bg-yellow-500/20 text-yellow-400">
                      Poco stock
                    </Badge>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Cart Panel */}
      <div className="w-96 flex flex-col bg-[#161616] rounded-xl border border-[#27272A]">
        {/* Cart Header */}
        <div className="p-4 border-b border-[#27272A]">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-[#708238]" />
              Pedido Actual
            </h2>
            {cart.length > 0 && (
              <Button
                onClick={clearCart}
                variant="ghost"
                size="sm"
                className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
          
          {/* Customer Name */}
          <div className="mt-3 relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#52525B]" />
            <Input
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="Nombre del cliente (opcional)"
              className="bg-[#0D0D0D] border-[#27272A] text-white pl-10"
            />
          </div>
        </div>

        {/* Cart Items */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {cart.length === 0 ? (
            <div className="text-center py-12">
              <ShoppingCart className="h-12 w-12 text-[#52525B] mx-auto mb-3" />
              <p className="text-[#A1A1AA]">Carrito vacío</p>
              <p className="text-sm text-[#52525B]">Selecciona productos para agregar</p>
            </div>
          ) : (
            cart.map((item, index) => (
              <div 
                key={`${item.product_id}-${index}`}
                className="p-3 rounded-lg border border-[#27272A] bg-[#0D0D0D]"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h4 className="font-medium text-white text-sm">{item.product_name}</h4>
                    <p className="text-xs text-[#708238]">{formatCurrency(item.unit_price)} c/u</p>
                    {item.notes && (
                      <p className="text-xs text-yellow-400 mt-1 italic">📝 {item.notes}</p>
                    )}
                  </div>
                  <p className="font-bold text-white">{formatCurrency(item.total_price)}</p>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => updateQuantity(index, -1)}
                      size="sm"
                      variant="outline"
                      className="h-8 w-8 p-0 border-[#27272A]"
                    >
                      <Minus className="h-4 w-4" />
                    </Button>
                    <span className="text-white font-bold w-8 text-center">{item.quantity}</span>
                    <Button
                      onClick={() => updateQuantity(index, 1)}
                      size="sm"
                      variant="outline"
                      className="h-8 w-8 p-0 border-[#27272A]"
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  </div>
                  
                  <div className="flex gap-1">
                    <Button
                      onClick={() => openNoteModal(index)}
                      size="sm"
                      variant="ghost"
                      className="text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/10"
                    >
                      📝
                    </Button>
                    <Button
                      onClick={() => removeFromCart(index)}
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Cart Footer */}
        {cart.length > 0 && (
          <div className="p-4 border-t border-[#27272A] space-y-3">
            {/* Totals */}
            <div className="space-y-1 text-sm">
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

            {/* Order Type */}
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "mostrador", label: "Mostrador" },
                { value: "mesa", label: "Mesa" },
                { value: "para llevar", label: "Para llevar" }
              ].map(type => (
                <Button
                  key={type.value}
                  onClick={() => setOrderType(type.value)}
                  variant={orderType === type.value ? "default" : "outline"}
                  size="sm"
                  className={orderType === type.value 
                    ? "bg-[#708238] hover:bg-[#5a692d]" 
                    : "border-[#27272A] text-[#A1A1AA]"
                  }
                >
                  {type.label}
                </Button>
              ))}
            </div>

            {/* Payment Method */}
            <div className="grid grid-cols-2 gap-2">
              <Button
                onClick={() => setPaymentMethod("efectivo")}
                variant={paymentMethod === "efectivo" ? "default" : "outline"}
                className={paymentMethod === "efectivo" 
                  ? "bg-green-600 hover:bg-green-700" 
                  : "border-[#27272A] text-[#A1A1AA]"
                }
              >
                <Banknote className="h-4 w-4 mr-2" />
                Efectivo
              </Button>
              <Button
                onClick={() => setPaymentMethod("tarjeta")}
                variant={paymentMethod === "tarjeta" ? "default" : "outline"}
                className={paymentMethod === "tarjeta" 
                  ? "bg-blue-600 hover:bg-blue-700" 
                  : "border-[#27272A] text-[#A1A1AA]"
                }
              >
                <CreditCard className="h-4 w-4 mr-2" />
                Tarjeta
              </Button>
            </div>

            {/* Submit Button */}
            <Button
              onClick={processOrder}
              disabled={processing}
              className="w-full h-14 text-lg bg-[#708238] hover:bg-[#5a692d]"
            >
              {processing ? (
                <>
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                  Procesando...
                </>
              ) : (
                <>
                  <Send className="h-5 w-5 mr-2" />
                  Enviar a Cocina
                </>
              )}
            </Button>
          </div>
        )}

        {/* Recent Orders */}
        {recentOrders.length > 0 && cart.length === 0 && (
          <div className="p-4 border-t border-[#27272A]">
            <h3 className="text-sm font-medium text-[#A1A1AA] mb-2">Últimas órdenes</h3>
            <div className="space-y-2">
              {recentOrders.map(order => (
                <div 
                  key={order.id}
                  className="flex items-center justify-between p-2 rounded bg-[#0D0D0D] text-sm"
                >
                  <div className="flex items-center gap-2">
                    <Receipt className="h-4 w-4 text-[#708238]" />
                    <span className="text-white">#{order.order_number}</span>
                    {order.customer_name && (
                      <span className="text-[#71717A]">- {order.customer_name}</span>
                    )}
                  </div>
                  <Badge className={
                    order.status === "delivered" ? "bg-green-500/20 text-green-400" :
                    order.status === "ready" ? "bg-blue-500/20 text-blue-400" :
                    order.status === "preparing" ? "bg-yellow-500/20 text-yellow-400" :
                    "bg-[#27272A] text-[#A1A1AA]"
                  }>
                    {order.status === "delivered" ? "Entregado" :
                     order.status === "ready" ? "Listo" :
                     order.status === "preparing" ? "Preparando" : "Pendiente"}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Note Modal */}
      {showNoteModal && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="bg-[#161616] rounded-xl border border-[#27272A] w-full max-w-md p-6">
            <h2 className="text-lg font-bold text-white mb-4">
              Nota especial para: {cart[selectedItem]?.product_name}
            </h2>
            <Input
              value={itemNote}
              onChange={(e) => setItemNote(e.target.value)}
              placeholder="Ej: sin cebolla, sin azúcar, extra caliente..."
              className="bg-[#0D0D0D] border-[#27272A] text-white mb-4"
              autoFocus
            />
            <div className="flex gap-3">
              <Button
                onClick={() => setShowNoteModal(false)}
                variant="outline"
                className="flex-1 border-[#27272A] text-white"
              >
                Cancelar
              </Button>
              <Button
                onClick={saveItemNote}
                className="flex-1 bg-[#708238] hover:bg-[#5a692d]"
              >
                Guardar Nota
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PointOfSale;
