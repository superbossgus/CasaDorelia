import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import axios from "axios";
import { FileText, TrendingUp, DollarSign, ShoppingCart, Store, Download, FileSpreadsheet, Loader2 } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from "recharts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Reports = () => {
  const { isAdmin, token } = useAuth();
  const [comparison, setComparison] = useState([]);
  const [profitAnalysis, setProfitAnalysis] = useState(null);
  const [cafeterias, setCafeterias] = useState([]);
  const [selectedCafeteria, setSelectedCafeteria] = useState("all");
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    fetchCafeterias();
    fetchReports();
  }, []);

  useEffect(() => {
    fetchProfitAnalysis();
  }, [selectedCafeteria]);

  const fetchCafeterias = async () => {
    try {
      const response = await axios.get(`${API}/cafeterias`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCafeterias(response.data);
    } catch (error) {
      console.error("Error fetching cafeterias:", error);
    }
  };

  const fetchReports = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/reports/sales-comparison`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setComparison(response.data);
    } catch (error) {
      toast.error("Error al cargar reportes");
    } finally {
      setLoading(false);
    }
  };

  const fetchProfitAnalysis = async () => {
    try {
      const params = selectedCafeteria !== "all" ? { cafeteria_id: selectedCafeteria } : {};
      const response = await axios.get(`${API}/reports/profit-analysis`, { 
        params,
        headers: { Authorization: `Bearer ${token}` }
      });
      setProfitAnalysis(response.data);
    } catch (error) {
      console.error("Error fetching profit analysis:", error);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(value);
  };

  const downloadReport = async (type, format) => {
    setDownloading(`${type}_${format}`);
    try {
      const params = new URLSearchParams();
      if (selectedCafeteria !== "all") {
        params.append("cafeteria_id", selectedCafeteria);
      }
      
      const response = await axios.get(`${API}/reports/${type}/${format}?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      
      // Get filename from header or generate one
      const contentDisposition = response.headers['content-disposition'];
      let filename = `reporte_${type}.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) filename = match[1];
      }
      
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success(`Reporte ${format.toUpperCase()} descargado`);
    } catch (error) {
      toast.error("Error al descargar reporte");
      console.error(error);
    } finally {
      setDownloading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#708238]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="reports-container">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="font-manrope text-3xl font-bold text-white">Reportes</h1>
          <p className="text-[#A1A1AA] mt-1">Análisis de rendimiento del mes actual</p>
        </div>
        
        <div className="flex items-center gap-3">
          {isAdmin() && (
            <Select value={selectedCafeteria} onValueChange={setSelectedCafeteria}>
              <SelectTrigger className="w-[180px] bg-[#161616] border-[#27272A] text-white">
                <SelectValue placeholder="Filtrar análisis" />
              </SelectTrigger>
              <SelectContent className="bg-[#161616] border-[#27272A]">
                <SelectItem value="all" className="text-white hover:bg-[#27272A]">Todas las cafeterías</SelectItem>
                {cafeterias.map((cafe) => (
                  <SelectItem key={cafe.id} value={cafe.id} className="text-white hover:bg-[#27272A]">{cafe.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          
          {/* Download Buttons */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadReport('sales', 'pdf')}
              disabled={downloading === 'sales_pdf'}
              className="bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
            >
              {downloading === 'sales_pdf' ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <FileText className="h-4 w-4 mr-2 text-red-400" />
              )}
              PDF
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadReport('sales', 'excel')}
              disabled={downloading === 'sales_excel'}
              className="bg-transparent border-[#27272A] text-white hover:bg-[#27272A]"
            >
              {downloading === 'sales_excel' ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <FileSpreadsheet className="h-4 w-4 mr-2 text-green-400" />
              )}
              Excel
            </Button>
          </div>
        </div>
      </div>

      {/* Profit Analysis Cards */}
      {profitAnalysis && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Ingresos Totales</p>
                  <p className="text-2xl font-bold text-white font-manrope mt-1">
                    {formatCurrency(profitAnalysis.total_revenue)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <DollarSign className="h-5 w-5 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Costo de Ventas</p>
                  <p className="text-2xl font-bold text-white font-manrope mt-1">
                    {formatCurrency(profitAnalysis.total_cost_of_goods)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[#D97706]/20">
                  <ShoppingCart className="h-5 w-5 text-[#D97706]" />
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Utilidad Bruta</p>
                  <p className="text-2xl font-bold text-[#8FBC8F] font-manrope mt-1">
                    {formatCurrency(profitAnalysis.gross_profit)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[#3E4B28]/30">
                  <TrendingUp className="h-5 w-5 text-[#8FBC8F]" />
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="bg-[#161616] border-[#27272A]">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-sm text-[#A1A1AA]">Margen Bruto</p>
                  <p className="text-2xl font-bold text-[#708238] font-manrope mt-1">
                    {profitAnalysis.gross_margin_percent}%
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[#708238]/20">
                  <FileText className="h-5 w-5 text-[#708238]" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Comparison Chart */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope flex items-center gap-2">
            <Store className="h-5 w-5 text-[#708238]" />
            Comparativa entre Cafeterías (Mes Actual)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {comparison.length === 0 ? (
            <div className="text-center py-12 text-[#71717A]">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay datos para mostrar</p>
            </div>
          ) : (
            <div className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={comparison} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272A" horizontal={false} />
                  <XAxis 
                    type="number" 
                    stroke="#71717A"
                    tick={{ fill: '#A1A1AA', fontSize: 12 }}
                    tickFormatter={(value) => `$${(value/1000).toFixed(0)}k`}
                  />
                  <YAxis 
                    dataKey="cafeteria_name" 
                    type="category" 
                    stroke="#71717A"
                    tick={{ fill: '#A1A1AA', fontSize: 12 }}
                    width={120}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#161616', 
                      border: '1px solid #27272A',
                      borderRadius: '8px',
                      color: '#EDEDED'
                    }}
                    formatter={(value, name) => [
                      formatCurrency(value),
                      name === 'total_sales' ? 'Ventas' : 'Utilidad'
                    ]}
                  />
                  <Legend 
                    formatter={(value) => value === 'total_sales' ? 'Ventas' : 'Utilidad'}
                    wrapperStyle={{ color: '#A1A1AA' }}
                  />
                  <Bar dataKey="total_sales" fill="#708238" radius={[0, 4, 4, 0]} name="total_sales" />
                  <Bar dataKey="total_profit" fill="#8FBC8F" radius={[0, 4, 4, 0]} name="total_profit" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metrics Table */}
      <Card className="bg-[#161616] border-[#27272A]">
        <CardHeader>
          <CardTitle className="text-white font-manrope">Métricas Detalladas por Cafetería</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#27272A]">
                  <th className="text-left py-3 px-4 text-[#A1A1AA] uppercase text-xs font-bold">Cafetería</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] uppercase text-xs font-bold">Ventas</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] uppercase text-xs font-bold">Utilidad</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] uppercase text-xs font-bold">Transacciones</th>
                  <th className="text-right py-3 px-4 text-[#A1A1AA] uppercase text-xs font-bold">Ticket Promedio</th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((cafe) => (
                  <tr key={cafe.cafeteria_id} className="border-b border-[#27272A] hover:bg-[#1F1F1F]/50">
                    <td className="py-4 px-4 text-white font-medium">{cafe.cafeteria_name}</td>
                    <td className="py-4 px-4 text-white text-right">{formatCurrency(cafe.total_sales)}</td>
                    <td className="py-4 px-4 text-[#8FBC8F] text-right">{formatCurrency(cafe.total_profit)}</td>
                    <td className="py-4 px-4 text-[#A1A1AA] text-right">{cafe.transaction_count}</td>
                    <td className="py-4 px-4 text-white text-right">{formatCurrency(cafe.average_ticket)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Reports;
