# Doré - Sistema de Gestión de Cafeterías

## Resumen del Proyecto
Sistema web integral para gestión de cafeterías con modelo **SaaS multi-tenant**. Permite controlar ventas, inventario, costos, menús y utilidad. Diseñado para vender a múltiples negocios de cafeterías.

## Fecha de Creación
28 de Enero, 2026

## Última Actualización
1 de Marzo, 2026

## Modelo de Negocio: SaaS Multi-Tenant
- **Prueba gratuita**: 7 días
- **Planes de suscripción** (MXN/mes):
  - 1 Sucursal: $399
  - 2 Sucursales: $599
  - 3-5 Sucursales: $799
  - 5-10 Sucursales: $999
  - 10-20 Sucursales: $1,199
- **Pagos**: Stripe (tarjeta de crédito/débito)
- **Registro**: Abierto (cualquiera puede registrarse)

## Arquitectura Técnica
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Recharts
- **Backend**: FastAPI + Python
- **Base de Datos**: MongoDB
- **Autenticación**: JWT con soporte multi-tenant + Google OAuth (Emergent Auth)
- **Pagos**: Stripe (emergentintegrations)
- **Notificaciones**: Twilio WhatsApp API
- **Email**: Resend (recuperación de contraseña)
- **Mobile**: Capacitor (iOS/Android)

## Roles de Usuario
1. **Administrador**: Acceso completo al sistema
2. **Gerente de Sucursal**: Gestión de su cafetería asignada
3. **Cajero**: Registro de ventas e inventario básico

## Funcionalidades Implementadas

### Core
- ✅ Autenticación JWT con roles
- ✅ **Google OAuth** (Emergent Auth) - Login con cuenta de Google (1 de Marzo, 2026)
- ✅ Dashboard con KPIs en tiempo real
- ✅ Gráficos de tendencias (últimos 7 días)
- ✅ Comparativas entre cafeterías
- ✅ Tema oscuro (negro #0D0D0D + verde aceituna #708238)
- ✅ **Banner "Made with Emergent" eliminado** (1 de Marzo, 2026)

### Módulos
- ✅ **Ventas**: Registro con múltiples productos, métodos de pago (Efectivo/Tarjeta/Clip)
- ✅ **Inventario de Productos**: Control de stock, alertas de stock bajo, movimientos
- ✅ **Inventario de Ingredientes**: Control de materia prima con consumo automático
- ✅ **Productos**: CRUD con categorías, precio, costo, margen de utilidad
- ✅ **Ingredientes**: Gestión de materias primas con costo por unidad
- ✅ **Recetas**: Vinculación ingredientes-productos con cálculo automático de costos
- ✅ **Proveedores**: Gestión de proveedores de insumos
- ✅ **Compras**: Registro de compras con actualización automática de inventario
- ✅ **Reportes**: Comparativas de ventas, análisis de utilidad, métricas por cafetería
- ✅ **Usuarios**: Gestión de usuarios con roles y asignación de cafetería
- ✅ **Cafeterías**: CRUD de sucursales

### Nuevas Funcionalidades (29-Ene-2026)
- ✅ **Alertas WhatsApp**: Notificaciones de stock crítico vía Twilio
  - Configuración de múltiples números de WhatsApp
  - Envío de alertas manuales
  - Envío de mensajes de prueba
  - Monitoreo de ingredientes con menos de 3 días de stock
- ✅ **Subida de Imágenes**: Upload de fotos de productos
  - 1 imagen principal
  - Hasta 3 imágenes adicionales
  - Formatos: JPEG, PNG, WebP, GIF (máx 5MB)
- ✅ **Exportación de Catálogo**: Descargar catálogo por cafetería
  - Formato JSON
  - Formato CSV
  - Incluye disponibilidad de stock
- ✅ **Dashboard de Alertas en Tiempo Real**:
  - Panel de alertas de inventario integrado en Dashboard
  - Notificaciones push del navegador (Web Notifications API)
  - Badge con contador de alertas en sidebar
  - Indicadores de alerta crítica (<3 días) y advertencia (<7 días)
  - Polling automático cada minuto para actualización

### Sistema Multi-Tenant y Suscripciones (31-Ene-2026)
- ✅ **Landing Page Pública**: Página de inicio con planes y registro
- ✅ **Registro de Negocios**: Onboarding con 7 días de prueba gratis
- ✅ **Sistema de Tenants**: Aislamiento de datos por negocio
- ✅ **Suscripciones con Stripe**: Checkout y activación automática
- ✅ **Página de Suscripción**: Gestión de planes y pagos
- ✅ **Banner de Trial**: Aviso en sidebar con días restantes
- ✅ **Apps Móviles**: Capacitor configurado para iOS y Android
- ✅ **Panel Super Admin**: Dashboard para gestionar todos los negocios
- ✅ **Logo Personalizado**: Cada negocio puede subir su marca
- ✅ **Reportes PDF/Excel**: Con logo del negocio incluido
  - Reporte de ventas en PDF
  - Reporte de ventas en Excel
  - Catálogo de productos en PDF

### Recuperación de Contraseña (1-Feb-2026)
- ✅ **Solicitud de recuperación**: Endpoint para solicitar código por email
- ✅ **Envío de email**: Integración con Resend para emails transaccionales
- ✅ **Enlace directo**: Botón en email que lleva a la página con código prellenado
- ✅ **Tokens seguros**: Códigos de un solo uso con expiración de 1 hora
- ✅ **UI completa**: Flujo de 3 pasos (email → código + nueva contraseña → éxito)
- ✅ **Branding por tenant**: Email incluye nombre del negocio del usuario

### Programa de Lealtad (8-Feb-2026)
- ✅ **Registro de Clientes**: App separada para clientes finales (`/loyalty/register`)
- ✅ **Sistema de Puntos**: $10 MXN = 1 punto con multiplicadores por nivel
- ✅ **Niveles de Gamificación**:
  - ☕ Bronce (0-199 pts): 1x multiplicador
  - ⭐ Plata (200-499 pts): 1.25x multiplicador
  - 👑 Oro (500+ pts): 1.5x multiplicador + Refill gratis
- ✅ **Catálogo de Descuentos**:
  - 50 pts = 10% descuento
  - 100 pts = 20% descuento
  - ... hasta 500 pts = 100% descuento (máx $200)
- ✅ **Cupones Digitales**: Código único con expiración de 30 días
- ✅ **QR en Tickets**: Generación de QR para acumular puntos
- ✅ **Validación de Cupones**: Módulo para cajeros
- ✅ **Regalo de Cumpleaños**: Cupón automático el día del cumpleaños
- ✅ **Panel Admin**: Dashboard de estadísticas y gestión de clientes
- ✅ **Expiración de Puntos**: 6 meses de vigencia
- ✅ **Bono de Bienvenida**: 10 puntos al registrarse

### Sistema de Vendedores/Afiliados (8-Feb-2026)
- ✅ **Registro de Vendedores**: Alta desde panel admin
- ✅ **Códigos QR únicos**: Para tracking de referidos
- ✅ **Descuentos automáticos**: 10% para clientes referidos
- ✅ **Sistema de Comisiones**: 10% de las ventas referidas
- ✅ **Panel Admin**: Gestión de vendedores y comisiones

### Sistema de Cupones de Descuento (28-Feb-2026)
- ✅ **Panel Admin** (`/coupons`):
  - Crear cupones con código único
  - Tipos de descuento: Porcentaje (%) o Monto Fijo ($)
  - Válido para: Suscripciones, Inversiones, o Ambos
  - Límite de usos configurable (o ilimitado)
  - Fecha de expiración opcional
  - Activar/Desactivar cupones
  - Eliminar cupones
  - KPIs: Total cupones, Usos, Descuento total, Promedio/uso
- ✅ **Reporte de Uso de Cupones**:
  - Historial detallado de cada uso
  - Fecha, cupón, tipo, monto original, descuento aplicado
  - Agrupación por cupón
- ✅ **Aplicación en Compra de Lotes**:
  - Campo de cupón en modal de compra
  - Validación en tiempo real
  - Muestra descuento calculado
  - Cupón aplicado con badge y opción de remover
- ✅ **Límite del Fondo Doré**:
  - Fondo total: $20,000,000 MXN
  - Máximo lotes: 5,000
  - Cada lote = $4,000 = 0.1% del fondo
  - Barra de progreso de lotes vendidos
  - Mensaje cuando se agoten: "Se ha llegado al máximo de lotes del fondo"

### Módulo de Socios/Inversionistas (28-Feb-2026)
- ✅ **Landing Page** (`/socios`): Información del programa de inversión con logo en blanco
- ✅ **Registro de Socios** (`/socios/registro`): Con auto-registro como vendedor
  - Opción de cuenta bancaria (CLABE)
  - Opción de PayPal (correo)
- ✅ **Login de Socios** (`/socios/login`): Autenticación separada
- ✅ **Dashboard Avanzado** (`/socios/dashboard`) con 3 pestañas:
  
  **Pestaña 1: Resumen Ejecutivo**
  - KPIs principales: Inversión Total, Participación %, Dividendo Mensual, Valor Portafolio
  - Proyección resumida a 48 meses (lotes finales, dividendo final, ROI)
  - Gráfica de crecimiento del portafolio
  - Código QR para descuentos/comisiones
  - Comprar más lotes con 3 métodos de pago
  
  **Pestaña 2: Proyección de Inversión**
  - Configuración de reinversión automática (toggle on/off)
  - Selector "Reinvertir hasta el mes X" (1-48)
  - KPIs detallados: Inversión inicial, Lotes finales, Participación final, Mes de recuperación
  - Totales: Dividendos recibidos, Interés ganado
  - Gráfica de Crecimiento del Portafolio (AreaChart)
  - Gráfica de Crecimiento de Lotes (LineChart dual)
  - Tabla Detallada de Corrida Mensual (48 filas, colapsable)
    - Columnas: Mes, Lotes, Dividendo, Interés, Lotes+, Valor Port., ROI
  
  **Pestaña 3: Historial y Pagos**
  - Historial de compras con status (Completado/Pendiente/En verificación)
  - Historial de rendimientos mensuales
  - Datos de pago registrados (Banco o PayPal)

- ✅ **Métodos de Pago para Compra de Lotes**:
  - **Tarjeta Bancaria**: Pago seguro con Stripe
  - **PayPal**: paypal.me/grupoviter con subida de comprobante
  - **Depósito SPEI**: Datos de Grupo Viter (CLABE: 012180001064835429)
- ✅ **Subida de Comprobantes**: Imagen o PDF hasta 10MB
- ✅ **Configuración de Inversión**:
  - Precio por lote: $4,000 MXN
  - Participación: 0.1% por lote
  - Rendimiento: $100 MXN mensual por lote
  - Interés sobre saldo reinvertido: 10% anual
  - Duración: 48 meses de pagos
- ✅ **Panel Admin** (`/partners-admin`):
  - Lista de socios con búsqueda
  - Estadísticas globales
  - Generación de rendimientos mensuales
  - Verificación de comprobantes de pago
  - Actualización de precio de lote

### Integración Clip POS
- ⚠️ **MOCK**: Endpoints preparados para integración real
- Requiere credenciales de developer.clip.mx para activación

## Credenciales de Prueba
- **Email**: gustavo@lepaindore.com.mx
- **Password**: (la que configuraste en recuperación)
- **Super Admin**: superadmin@dore.com / superadmin123

## Datos de Prueba
El seed data genera:
- 1 usuario admin
- 3 cafeterías (Central, Norte, Sur)
- 4 categorías de productos
- 12 productos con precios y costos
- 9 ingredientes
- 4 recetas
- Inventario inicial por cafetería
- 3 proveedores

## Configuración Twilio WhatsApp
- **Account SID**: Configurado en .env
- **Auth Token**: Configurado en .env
- **Número WhatsApp**: +15096764561
- **Nota**: Usuarios deben enviar mensaje al sandbox de Twilio antes de recibir alertas

## Backlog - Próximas Funcionalidades

### P0 - Crítico (Multi-Tenant)
- [x] Filtrar datos por tenant_id en queries principales
- [x] Migrar usuario legacy (admin@cafecontrol.com) al tenant "Doré"
- [x] Panel de Super Admin para gestionar todos los tenants
- [ ] Renovación automática de suscripciones (webhook recurrente)

### P1 - Alta Prioridad
- [ ] Alertas automáticas programadas (cron job para envío diario)
- [ ] Sistema de alertas cuando el margen de ganancia baja por aumento de costos

### P2 - Media Prioridad
- [ ] Reporte comparativo de consumo teórico vs real de ingredientes
- [ ] Historial de cambios de precios
- [ ] Integración real con Clip POS API

### P3 - Baja Prioridad
- [ ] App móvil compilada y publicada en stores
- [ ] Integración con contabilidad
- [ ] Pronósticos de ventas con IA

## Endpoints API Principales
- `POST /api/auth/login` - Autenticación
- `POST /api/auth/google/session` - Intercambio de session_id de Emergent OAuth
- `POST /api/auth/google/logout` - Cerrar sesión de Google
- `GET /api/auth/me` - Obtener usuario actual
- `POST /api/auth/forgot-password` - Solicitar recuperación de contraseña
- `POST /api/auth/reset-password` - Restablecer contraseña con código
- `GET /api/dashboard/stats` - Estadísticas dashboard
- `GET/POST /api/sales` - Gestión de ventas
- `GET/POST /api/inventory` - Control de inventario de productos
- `GET/POST /api/ingredient-inventory` - Control de inventario de ingredientes
- `GET/POST /api/products` - Productos
- `POST /api/products/{id}/upload-image` - Subir imagen de producto
- `GET/POST /api/ingredients` - Ingredientes
- `GET/POST /api/recipes` - Recetas
- `GET/POST /api/suppliers` - Proveedores
- `GET/POST /api/purchases` - Compras
- `GET /api/catalog/export/{cafeteria_id}` - Exportar catálogo
- `GET/POST /api/whatsapp/numbers` - Gestión números WhatsApp
- `POST /api/whatsapp/send-test` - Enviar mensaje de prueba
- `POST /api/whatsapp/send-alerts` - Enviar alertas de stock crítico
- `GET /api/reports/sales-comparison` - Comparativa ventas
- `GET /api/reports/profit-analysis` - Análisis de utilidad

### Endpoints de Socios/Inversionistas
- `GET /api/partners/businesses` - Listar negocios disponibles
- `POST /api/partners/register` - Registro de nuevo socio
- `POST /api/partners/login` - Login de socio
- `GET /api/partners/dashboard` - Dashboard del socio
- `POST /api/partners/buy-lots` - Comprar lotes (Stripe checkout)
- `GET /api/partners/admin/all` - Listar todos los socios (admin)
- `GET /api/partners/admin/stats` - Estadísticas de socios (admin)
- `GET /api/partners/admin/pending-returns` - Rendimientos pendientes (admin)
- `POST /api/partners/admin/generate-returns` - Generar rendimientos mensuales
- `POST /api/partners/admin/mark-paid` - Marcar rendimiento como pagado

## Estructura de Archivos
```
/app/
├── backend/
│   ├── .env
│   ├── requirements.txt
│   ├── server.py
│   ├── uploads/products/  # Imágenes subidas
│   └── tests/
└── frontend/
    ├── android/           # Proyecto Android (Capacitor)
    ├── ios/               # Proyecto iOS (Capacitor)
    ├── public/
    ├── src/
    │   ├── components/
    │   │   └── ui/        # Componentes Shadcn
    │   ├── context/
    │   │   └── AuthContext.js
    │   ├── hooks/
    │   │   └── useAlerts.js
    │   ├── utils/
    │   │   └── capacitor.js
    │   ├── pages/
    │   │   ├── WhatsAppAlerts.js
    │   │   ├── Products.js
    │   │   └── ...
    │   └── App.js
    ├── capacitor.config.json
    ├── MOBILE_APP_GUIDE.md
    └── package.json
```

## 📱 Apps Móviles (Capacitor)

La aplicación está configurada para generar apps nativas:
- **Android**: `/app/frontend/android/`
- **iOS**: `/app/frontend/ios/`

### Comandos útiles:
```bash
yarn cap:build      # Construir y sincronizar
yarn cap:android    # Abrir en Android Studio
yarn cap:ios        # Abrir en Xcode (requiere Mac)
```

Ver guía completa en: `/app/frontend/MOBILE_APP_GUIDE.md`
