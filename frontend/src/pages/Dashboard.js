import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";
import {
  DollarSign,
  TrendingUp,
  ShoppingCart,
  AlertTriangle,
  Coffee,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Dashboard = () => {
  const { user, isAdmin } = useAuth();
  const [stats, setStats] = useState(null);
  const [cafeterias, setCafeterias] = useState([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCafeterias();
  }, []);

  useEffect(() => {
    fetchStats();
  }, [selectedCafeteria]);

  const fetchCafeterias = async () => {
    try {
      const response = await axios.get(`${API}/cafeterias`);
      setCafeterias(response.data);
    } catch (error) {
      console.error("Error fetching cafeterias:", error);
    }
  };

  const fetchStats = async () => {
    setLoading(true);
    try {
      const params = selectedCafeteria !== "all" ? { cafeteria_id: selectedCafeteria } : {};
      const response = await axios.get(`${API}/dashboard/stats`, { params });
      setStats(response.data);
    } catch (error) {
      toast.error("Error al cargar estadísticas");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", {
      style: "currency",
      currency: "MXN",
    }).format(value);
  };

  const COLORS = ["#708238", "#8FBC8F", "#3E4B28", "#D97706"];

  if (loading || !stats) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  const metricCards = [
    {
      title: "Ventas Hoy",
      value: formatCurrency(stats.total_sales_today),
      icon: DollarSign,
      trend: stats.total_sales_today > 0 ? "up" : "neutral",
      subtitle: `${stats.sales_count_today} transacciones`,
    },
    {
      title: "Ventas del Mes",
      value: formatCurrency(stats.total_sales_month),
      icon: ShoppingCart,
      trend: "up",
      subtitle: "Total acumulado",
    },
    {
      title: "Utilidad Hoy",
      value: formatCurrency(stats.total_profit_today),
      icon: TrendingUp,
      trend: stats.total_profit_today > 0 ? "up" : "neutral",
      subtitle: "Ganancia neta",
    },
    {
      title: "Alertas Stock",
      value: stats.low_stock_alerts,
      icon: AlertTriangle,
      trend: stats.low_stock_alerts > 0 ? "down" : "neutral",
      subtitle: "Productos bajos",
      alert: stats.low_stock_alerts > 0,
    },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-[#A1A1AA] mt-1">
            Bienvenido, {user?.name}
          </p>
        </div>
        
        {isAdmin() && (
          <Select value={selectedCafeteria} onValueChange={setSelectedCafeteria}>
            <SelectTrigger 
              className="w-[200px] bg-[#161616] border-[#27272A] text-white"
              data-testid="cafeteria-filter"
            >
              <SelectValue placeholder="Todas las cafeterías" />
            </SelectTrigger>
            <SelectContent className="bg-[#161616] border-[#27272A]">
              <SelectItem value="all" className="text-white hover:bg-[#27272A]">
                Todas las cafeterías
              </SelectItem>
              {cafeterias.map((cafe) => (
                <SelectItem 
                  key={cafe.id} 
                  value={cafe.id}
                  className="text-white hover:bg-[#27272A]"
                >
                  {cafe.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metricCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Card 
              key={card.title}
              className={`bg-[#161616] border-[#27272A] metric-card card-hover animate-fade-in stagger-${index + 1} ${card.alert ? 'border-l-2 border-l-[#D97706]' : ''}`}
              data-testid={`metric-${card.title.toLowerCase().replace(/\s/g, '-')}`}
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-[#A1A1AA] mb-1">{card.title}</p>
                    <p className="text-2xl font-bold text-white font-manrope">{card.value}</p>
                    <p className="text-xs text-[#71717A] mt-1">{card.subtitle}</p>
                  </div>
                  <div className={`p-3 rounded-lg ${card.alert ? 'bg-[#D97706]/20' : 'bg-[#708238]/20'}`}>
                    <Icon className={`h-5 w-5 ${card.alert ? 'text-[#D97706]' : 'text-[#708238]'}`} />
                  </div>
                </div>
                {card.trend !== "neutral" && (
                  <div className={`flex items-center gap-1 mt-3 text-xs ${card.trend === 'up' ? 'text-[#8FBC8F]' : 'text-[#D97706]'}`}>
                    {card.trend === 'up' ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                    <span>{card.trend === 'up' ? 'En aumento' : 'Requiere atención'}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sales Trend Chart */}
        <Card className="lg:col-span-2 bg-[#161616] border-[#27272A] animate-fade-in stagger-5">
          <CardHeader>
            <CardTitle className="text-white font-manrope">Tendencia de Ventas</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats.sales_trend}>
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#708238" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#708238" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                  <XAxis 
                    dataKey="day" 
                    stroke="#71717A"
                    tick={{ fill: '#A1A1AA', fontSize: 12 }}
                  />
                  <YAxis 
                    stroke="#71717A"
                    tick={{ fill: '#A1A1AA', fontSize: 12 }}
                    tickFormatter={(value) => `$${(value/1000).toFixed(0)}k`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#161616', 
                      border: '1px solid #27272A',
                      borderRadius: '8px',
                      color: '#EDEDED'
                    }}
                    formatter={(value) => [formatCurrency(value), 'Total']}
                    labelFormatter={(label) => `Día: ${label}`}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="total" 
                    stroke="#708238" 
                    strokeWidth={2}
                    fillOpacity={1} 
                    fill="url(#colorTotal)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Sales by Cafeteria */}
        <Card className="bg-[#161616] border-[#27272A] animate-fade-in stagger-5">
          <CardHeader>
            <CardTitle className="text-white font-manrope">Ventas por Cafetería</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats.sales_by_cafeteria}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="total"
                    nameKey="name"
                  >
                    {stats.sales_by_cafeteria.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#161616', 
                      border: '1px solid #27272A',
                      borderRadius: '8px',
                      color: '#EDEDED'
                    }}
                    formatter={(value) => formatCurrency(value)}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 space-y-2">
              {stats.sales_by_cafeteria.map((cafe, index) => (
                <div key={cafe.name} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <span className="text-[#A1A1AA]">{cafe.name}</span>
                  </div>
                  <span className="text-white font-medium">{formatCurrency(cafe.total)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Top Products */}
      <Card className="bg-[#161616] border-[#27272A] animate-fade-in">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Coffee className="h-5 w-5 text-[#708238]" />
            Productos Más Vendidos
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.top_products} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#27272A" horizontal={false} />
                <XAxis 
                  type="number" 
                  stroke="#71717A"
                  tick={{ fill: '#A1A1AA', fontSize: 12 }}
                  tickFormatter={(value) => `$${(value/1000).toFixed(0)}k`}
                />
                <YAxis 
                  dataKey="name" 
                  type="category" 
                  stroke="#71717A"
                  tick={{ fill: '#A1A1AA', fontSize: 12 }}
                  width={100}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#161616', 
                    border: '1px solid #27272A',
                    borderRadius: '8px',
                    color: '#EDEDED'
                  }}
                  formatter={(value, name) => [
                    name === 'revenue' ? formatCurrency(value) : value,
                    name === 'revenue' ? 'Ingresos' : 'Cantidad'
                  ]}
                />
                <Bar dataKey="revenue" fill="#708238" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Dashboard;
