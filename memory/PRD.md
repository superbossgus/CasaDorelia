# CaféControl - Sistema de Gestión de Cafeterías

## Resumen del Proyecto
Sistema web integral para gestión de 3 cafeterías con control de ventas, inventario, costos, menús y utilidad.

## Fecha de Creación
28 de Enero, 2026

## Arquitectura Técnica
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + Recharts
- **Backend**: FastAPI + Python
- **Base de Datos**: MongoDB
- **Autenticación**: JWT

## Roles de Usuario
1. **Administrador**: Acceso completo al sistema
2. **Gerente de Sucursal**: Gestión de su cafetería asignada
3. **Cajero**: Registro de ventas e inventario básico

## Funcionalidades Implementadas

### Core
- ✅ Autenticación JWT con roles
- ✅ Dashboard con KPIs en tiempo real
- ✅ Gráficos de tendencias (últimos 7 días)
- ✅ Comparativas entre cafeterías
- ✅ Tema oscuro (negro #0D0D0D + verde aceituna #708238)

### Módulos
- ✅ **Ventas**: Registro con múltiples productos, métodos de pago (Efectivo/Tarjeta/Clip)
- ✅ **Inventario**: Control de stock, alertas de stock bajo, movimientos (entrada/salida/merma)
- ✅ **Productos**: CRUD con categorías, precio, costo, margen de utilidad
- ✅ **Proveedores**: Gestión de proveedores de insumos
- ✅ **Compras**: Registro de compras a proveedores con actualización automática de inventario
- ✅ **Reportes**: Comparativas de ventas, análisis de utilidad, métricas por cafetería
- ✅ **Usuarios**: Gestión de usuarios con roles y asignación de cafetería
- ✅ **Cafeterías**: CRUD de sucursales

### Integración Clip POS
- ⚠️ **MOCK**: Endpoints preparados para integración real
- `/api/clip/sync` - Sincronización de transacciones
- `/api/clip/status` - Estado de conexión
- Requiere credenciales de developer.clip.mx para activación

## Credenciales de Prueba
- **Email**: admin@cafecontrol.com
- **Password**: admin123

## Datos de Prueba
El botón "Crear Datos de Prueba" en login genera:
- 1 usuario admin
- 3 cafeterías (Central, Norte, Sur)
- 4 categorías de productos
- 12 productos con precios y costos
- Inventario inicial por cafetería
- 3 proveedores
- Ventas de prueba (últimos 7 días)

## Backlog - Próximas Funcionalidades

### P0 - Alta Prioridad
- [ ] Integración real con Clip POS API
- [ ] Exportación de reportes a PDF/Excel

### P1 - Media Prioridad
- [ ] Alertas por email de stock bajo
- [ ] Historial de cambios de precios
- [ ] Programa de fidelización de clientes

### P2 - Baja Prioridad
- [ ] App móvil para cajeros
- [ ] Integración con contabilidad
- [ ] Pronósticos de ventas con IA

## Endpoints API Principales
- `POST /api/auth/login` - Autenticación
- `GET /api/dashboard/stats` - Estadísticas dashboard
- `GET/POST /api/sales` - Gestión de ventas
- `GET/POST /api/inventory` - Control de inventario
- `GET/POST /api/products` - Productos
- `GET/POST /api/suppliers` - Proveedores
- `GET/POST /api/purchases` - Compras
- `GET /api/reports/sales-comparison` - Comparativa ventas
- `GET /api/reports/profit-analysis` - Análisis de utilidad
