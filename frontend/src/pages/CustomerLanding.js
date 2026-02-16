import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Gift, Star, Crown, Coffee, QrCode, Percent, Cake, TrendingUp } from "lucide-react";

const CustomerLanding = () => {
  return (
    <div className="min-h-screen bg-[#0D0D0D]">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div 
          className="absolute inset-0 bg-cover bg-center opacity-30"
          style={{
            backgroundImage: `url('https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1920&q=80')`
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#0D0D0D] via-transparent to-[#0D0D0D]" />
        
        <div className="relative z-10 max-w-4xl mx-auto px-4 pt-16 pb-24 text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <img 
              src="https://customer-assets.emergentagent.com/job_cafe-dashboard-28/artifacts/mp6st7i6_Logotipo%2003.png" 
              alt="Doré" 
              className="h-16 w-auto"
            />
            <h1 className="font-manrope text-4xl md:text-5xl font-bold text-white">
              Le Pain Doré
            </h1>
          </div>
          
          <p className="text-xl md:text-2xl text-[#A1A1AA] mb-4">
            Programa de Recompensas
          </p>
          
          <p className="text-[#708238] text-lg mb-10">
            Acumula puntos en cada compra y canjéalos por descuentos
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/loyalty/register">
              <Button 
                size="lg" 
                className="bg-[#708238] hover:bg-[#5a692d] text-white font-semibold px-8 py-6 text-lg w-full sm:w-auto"
              >
                <Gift className="mr-2 h-5 w-5" />
                Crear mi Cuenta
              </Button>
            </Link>
            <Link to="/loyalty/login">
              <Button 
                size="lg" 
                variant="outline"
                className="border-[#708238] text-[#708238] hover:bg-[#708238]/10 font-semibold px-8 py-6 text-lg w-full sm:w-auto"
              >
                Ya tengo cuenta
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* How it works */}
      <div className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-12">
          ¿Cómo funciona?
        </h2>
        
        <div className="grid md:grid-cols-3 gap-8">
          <Card className="bg-[#161616] border-[#27272A] text-center">
            <CardContent className="pt-8 pb-6">
              <div className="w-16 h-16 bg-[#708238]/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <QrCode className="h-8 w-8 text-[#708238]" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">1. Compra</h3>
              <p className="text-[#A1A1AA]">
                Realiza tus compras normalmente y escanea el código QR de tu ticket
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A] text-center">
            <CardContent className="pt-8 pb-6">
              <div className="w-16 h-16 bg-[#708238]/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Star className="h-8 w-8 text-[#708238]" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">2. Acumula</h3>
              <p className="text-[#A1A1AA]">
                Gana <strong className="text-white">1 punto por cada $10 MXN</strong> de compra
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[#161616] border-[#27272A] text-center">
            <CardContent className="pt-8 pb-6">
              <div className="w-16 h-16 bg-[#708238]/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Percent className="h-8 w-8 text-[#708238]" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">3. Canjea</h3>
              <p className="text-[#A1A1AA]">
                Usa tus puntos para obtener descuentos de hasta el <strong className="text-white">100%</strong>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Levels */}
      <div className="bg-[#161616] py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-4">
            Sube de Nivel
          </h2>
          <p className="text-[#A1A1AA] text-center mb-12">
            Entre más compras, más beneficios obtienes
          </p>
          
          <div className="grid md:grid-cols-3 gap-6">
            <Card className="bg-[#0D0D0D] border-amber-600/30 border-2">
              <CardContent className="pt-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-amber-600/20 rounded-full">
                    <Coffee className="h-6 w-6 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-amber-600 font-bold text-lg">Bronce</p>
                    <p className="text-[#71717A] text-sm">0 - 199 puntos</p>
                  </div>
                </div>
                <ul className="space-y-2 text-[#A1A1AA] text-sm">
                  <li>• Acumula 1 punto por cada $10</li>
                  <li>• Acceso a todas las recompensas</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="bg-[#0D0D0D] border-slate-300/30 border-2">
              <CardContent className="pt-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-slate-300/20 rounded-full">
                    <Star className="h-6 w-6 text-slate-300" />
                  </div>
                  <div>
                    <p className="text-slate-300 font-bold text-lg">Plata</p>
                    <p className="text-[#71717A] text-sm">200 - 499 puntos</p>
                  </div>
                </div>
                <ul className="space-y-2 text-[#A1A1AA] text-sm">
                  <li>• <strong className="text-white">25% más puntos</strong> en cada compra</li>
                  <li>• Acceso a todas las recompensas</li>
                </ul>
              </CardContent>
            </Card>

            <Card className="bg-[#0D0D0D] border-yellow-400/30 border-2 relative overflow-hidden">
              <div className="absolute top-2 right-2 bg-yellow-400 text-black text-xs font-bold px-2 py-1 rounded">
                TOP
              </div>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-3 bg-yellow-400/20 rounded-full">
                    <Crown className="h-6 w-6 text-yellow-400" />
                  </div>
                  <div>
                    <p className="text-yellow-400 font-bold text-lg">Oro</p>
                    <p className="text-[#71717A] text-sm">500+ puntos</p>
                  </div>
                </div>
                <ul className="space-y-2 text-[#A1A1AA] text-sm">
                  <li>• <strong className="text-white">50% más puntos</strong> en cada compra</li>
                  <li>• <strong className="text-yellow-400">Refill de café gratis</strong></li>
                  <li>• Acceso prioritario a promociones</li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Rewards Preview */}
      <div className="max-w-5xl mx-auto px-4 py-16">
        <h2 className="text-2xl md:text-3xl font-bold text-white text-center mb-4">
          Recompensas Disponibles
        </h2>
        <p className="text-[#A1A1AA] text-center mb-12">
          Canjea tus puntos por descuentos increíbles
        </p>
        
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {[
            { points: 50, discount: "10%" },
            { points: 100, discount: "20%" },
            { points: 200, discount: "40%" },
            { points: 350, discount: "70%" },
            { points: 500, discount: "100%", highlight: true },
          ].map((reward, i) => (
            <Card 
              key={i} 
              className={`bg-[#161616] border-[#27272A] text-center ${reward.highlight ? 'border-[#708238] border-2' : ''}`}
            >
              <CardContent className="py-6">
                <p className={`text-2xl font-bold ${reward.highlight ? 'text-[#708238]' : 'text-white'}`}>
                  {reward.discount}
                </p>
                <p className="text-[#71717A] text-sm">descuento</p>
                <p className="text-[#A1A1AA] text-xs mt-2">{reward.points} pts</p>
              </CardContent>
            </Card>
          ))}
        </div>
        
        <p className="text-center text-[#71717A] text-sm mt-6">
          * El descuento del 100% aplica en compras de hasta $200 MXN
        </p>
      </div>

      {/* Birthday */}
      <div className="bg-[#161616] py-12">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Cake className="h-8 w-8 text-pink-400" />
            <h2 className="text-xl font-bold text-white">Regalo de Cumpleaños</h2>
          </div>
          <p className="text-[#A1A1AA]">
            Registra tu fecha de nacimiento y recibe un <strong className="text-pink-400">cupón especial</strong> cada año
          </p>
        </div>
      </div>

      {/* CTA */}
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <h2 className="text-2xl md:text-3xl font-bold text-white mb-4">
          ¡Únete Ahora!
        </h2>
        <p className="text-[#A1A1AA] mb-8">
          Crea tu cuenta gratis y recibe <strong className="text-[#708238]">10 puntos de bienvenida</strong>
        </p>
        <Link to="/loyalty/register">
          <Button 
            size="lg" 
            className="bg-[#708238] hover:bg-[#5a692d] text-white font-semibold px-12 py-6 text-lg"
          >
            Crear mi Cuenta Gratis
          </Button>
        </Link>
      </div>

      {/* Investor CTA */}
      <div className="bg-gradient-to-r from-[#708238]/10 to-transparent py-12 border-t border-[#27272A]">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-3 mb-4">
            <TrendingUp className="h-8 w-8 text-[#708238]" />
            <h2 className="text-xl font-bold text-white">¿Quieres invertir en Doré?</h2>
          </div>
          <p className="text-[#A1A1AA] mb-4">
            Conviértete en socio inversionista del Fondo Doré y recibe rendimientos mensuales garantizados
          </p>
          <Link to="/socios">
            <Button 
              variant="outline"
              className="border-[#708238] text-[#708238] hover:bg-[#708238]/10"
            >
              Conocer más sobre el programa de Socios
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
              <Link to="/socios" className="hover:text-white transition-colors">
                Socios Inversionistas
              </Link>
              <Link to="/admin" className="hover:text-white transition-colors">
                Acceso Empleados
              </Link>
              <Link to="/registro-negocio" className="hover:text-white transition-colors">
                Para Negocios
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default CustomerLanding;
