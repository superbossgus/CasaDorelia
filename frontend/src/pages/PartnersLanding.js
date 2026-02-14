import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { 
  TrendingUp, Shield, DollarSign, Users, 
  ChevronRight, CheckCircle2, Clock, Percent 
} from "lucide-react";

const PartnersLanding = () => {
  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Hero */}
      <div className="relative overflow-hidden">
        <div 
          className="absolute inset-0 bg-cover bg-center opacity-20"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=1920&q=80')`
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#0D0D0D] via-transparent to-[#0D0D0D]" />
        
        <div className="relative z-10 max-w-5xl mx-auto px-4 pt-16 pb-24 text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <img 
              src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
              alt="Doré" 
              className="h-14 w-auto"
            />
            <h1 className="font-manrope text-4xl md:text-5xl font-bold text-white">
              Socios Doré
            </h1>
          </div>
          
          <p className="text-xl md:text-2xl text-[#A1A1AA] mb-4">
            Invierte en el crecimiento de nuestras cafeterías
          </p>
          
          <p className="text-[#708238] text-lg mb-10 max-w-2xl mx-auto">
            Conviértete en socio inversionista y recibe rendimientos mensuales garantizados
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/socios/registro">
              <Button 
                size="lg" 
                className="bg-[#708238] hover:bg-[#5a692d] text-white font-semibold px-8 py-6 text-lg w-full sm:w-auto"
              >
                <TrendingUp className="mr-2 h-5 w-5" />
                Quiero ser Socio
              </Button>
            </Link>
            <Link to="/socios/login">
              <Button 
                size="lg" 
                variant="outline"
                className="border-[#708238] text-[#708238] hover:bg-[#708238]/10 font-semibold px-8 py-6 text-lg w-full sm:w-auto"
              >
                Ya soy Socio
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Investment Highlight */}
      <div className="bg-gradient-to-r from-[#708238]/20 to-transparent py-12">
        <div className="max-w-5xl mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-6 text-center">
            <div>
              <p className="text-4xl font-bold text-white">$5,000</p>
              <p className="text-[#A1A1AA]">Inversión mínima</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-[#708238]">0.1%</p>
              <p className="text-[#A1A1AA]">Participación por lote</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-white">$150</p>
              <p className="text-[#A1A1AA]">Rendimiento mensual/lote</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-[#708238]">48</p>
              <p className="text-[#A1A1AA]">Meses de pagos</p>
            </div>
          </div>
        </div>
      </div>

      {/* How it works */}
      <div className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-12">
          ¿Cómo funciona?
        </h2>
        
        <div className="grid md:grid-cols-3 gap-8">
          <Card className="bg-[#161616] border-[#27272A] text-center relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 bg-[#708238] rounded-full flex items-center justify-center text-white font-bold">
              1
            </div>
            <CardContent className="pt-10 pb-6">
              <Users className="h-12 w-12 text-[#708238] mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">Regístrate</h3>
              <p className="text-[#A1A1AA]">
                Crea tu cuenta de socio con tus datos básicos y cuenta bancaria para depósitos
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A] text-center relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 bg-[#708238] rounded-full flex items-center justify-center text-white font-bold">
              2
            </div>
            <CardContent className="pt-10 pb-6">
              <DollarSign className="h-12 w-12 text-[#708238] mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">Invierte</h3>
              <p className="text-[#A1A1AA]">
                Compra lotes de participación de forma segura con tarjeta de crédito o débito
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A] text-center relative">
            <div className="absolute -top-4 left-1/2 -translate-x-1/2 w-8 h-8 bg-[#708238] rounded-full flex items-center justify-center text-white font-bold">
              3
            </div>
            <CardContent className="pt-10 pb-6">
              <TrendingUp className="h-12 w-12 text-[#708238] mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">Recibe Rendimientos</h3>
              <p className="text-[#A1A1AA]">
                Recibe $150 MXN mensuales por cada lote durante 4 años
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Investment Calculator */}
      <div className="bg-[#161616] py-16">
        <div className="max-w-4xl mx-auto px-4">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-4">
            Calcula tu Inversión
          </h2>
          <p className="text-[#A1A1AA] text-center mb-12">
            Mira cuánto puedes ganar con diferentes niveles de inversión
          </p>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#27272A]">
                  <th className="py-4 px-4 text-left text-[#A1A1AA]">Lotes</th>
                  <th className="py-4 px-4 text-right text-[#A1A1AA]">Inversión</th>
                  <th className="py-4 px-4 text-right text-[#A1A1AA]">Participación</th>
                  <th className="py-4 px-4 text-right text-[#A1A1AA]">Rendimiento/Mes</th>
                  <th className="py-4 px-4 text-right text-[#A1A1AA]">Retorno Total (4 años)</th>
                </tr>
              </thead>
              <tbody>
                {[1, 3, 5, 10, 20].map((lots) => (
                  <tr key={lots} className="border-b border-[#27272A] hover:bg-[#1F1F1F]/50">
                    <td className="py-4 px-4 text-white font-bold">{lots} lote{lots > 1 ? 's' : ''}</td>
                    <td className="py-4 px-4 text-right text-white">${(lots * 5000).toLocaleString()}</td>
                    <td className="py-4 px-4 text-right text-[#708238]">{(lots * 0.1).toFixed(1)}%</td>
                    <td className="py-4 px-4 text-right text-white">${(lots * 150).toLocaleString()}</td>
                    <td className="py-4 px-4 text-right text-[#708238] font-bold">${(lots * 150 * 48).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <p className="text-center text-[#71717A] text-sm mt-6">
            * El precio del lote puede aumentar con el tiempo, incrementando el valor de tu inversión
          </p>
        </div>
      </div>

      {/* Benefits */}
      <div className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-12">
          Beneficios de ser Socio
        </h2>
        
        <div className="grid md:grid-cols-2 gap-6">
          {[
            { icon: DollarSign, title: "Rendimientos Garantizados", desc: "$150 MXN mensuales por lote durante 48 meses" },
            { icon: TrendingUp, title: "Plusvalía", desc: "El valor de tu participación puede aumentar con el tiempo" },
            { icon: Shield, title: "Inversión Segura", desc: "Respaldada por el crecimiento real de las cafeterías" },
            { icon: Percent, title: "Código de Descuento", desc: "Recibe un código QR para obtener 10% de descuento y comisiones por referidos" },
            { icon: Clock, title: "Pagos Puntuales", desc: "Depósitos directos a tu cuenta bancaria cada mes" },
            { icon: CheckCircle2, title: "Transparencia Total", desc: "Accede a tu dashboard para ver el estado de tu inversión" },
          ].map((benefit, i) => (
            <div key={i} className="flex gap-4 p-4 bg-[#161616] rounded-lg border border-[#27272A]">
              <div className="p-3 bg-[#708238]/20 rounded-lg h-fit">
                <benefit.icon className="h-6 w-6 text-[#708238]" />
              </div>
              <div>
                <h3 className="text-white font-bold mb-1">{benefit.title}</h3>
                <p className="text-[#A1A1AA] text-sm">{benefit.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="bg-gradient-to-r from-[#708238]/30 via-[#708238]/20 to-transparent py-16">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
            ¿Listo para invertir en tu futuro?
          </h2>
          <p className="text-[#A1A1AA] mb-8">
            Únete a nuestra comunidad de socios inversionistas y comienza a recibir rendimientos mensuales
          </p>
          <Link to="/socios/registro">
            <Button 
              size="lg" 
              className="bg-[#708238] hover:bg-[#5a692d] text-white font-semibold px-12 py-6 text-lg"
            >
              Comenzar Ahora
              <ChevronRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-[#27272A] py-8">
        <div className="max-w-5xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <img 
                src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
                alt="Doré" 
                className="h-8 w-auto"
              />
              <span className="text-white font-manrope font-bold">Le Pain Doré</span>
            </div>
            <div className="flex gap-6 text-sm text-[#71717A]">
              <Link to="/" className="hover:text-white transition-colors">
                Programa de Lealtad
              </Link>
              <Link to="/admin" className="hover:text-white transition-colors">
                Acceso Empleados
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PartnersLanding;
