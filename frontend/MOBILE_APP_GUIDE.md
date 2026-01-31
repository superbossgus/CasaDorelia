# 📱 Doré - Guía para Apps Móviles

## Requisitos Previos

### Para Android:
- [Android Studio](https://developer.android.com/studio) instalado
- Java JDK 11 o superior
- Cuenta de Google Play Developer ($25 USD, pago único)

### Para iOS:
- Mac con macOS
- [Xcode](https://apps.apple.com/us/app/xcode/id497799835) instalado
- Cuenta de Apple Developer ($99 USD/año)

---

## 🚀 Pasos para Generar las Apps

### 1. Construir la versión de producción
```bash
cd /app/frontend
yarn build
```

### 2. Agregar las plataformas (solo primera vez)

**Android:**
```bash
yarn cap:add:android
```

**iOS:**
```bash
yarn cap:add:ios
```

### 3. Sincronizar cambios
Cada vez que hagas cambios en la app:
```bash
yarn cap:build
```
o
```bash
yarn build && yarn cap:sync
```

### 4. Abrir en el IDE nativo

**Android Studio:**
```bash
yarn cap:android
```

**Xcode (solo Mac):**
```bash
yarn cap:ios
```

---

## 📦 Generar APK/IPA para las Tiendas

### Android (APK/AAB):
1. Abre Android Studio con `yarn cap:android`
2. Ve a **Build > Generate Signed Bundle/APK**
3. Crea o selecciona tu keystore
4. Genera el archivo AAB (recomendado para Play Store)

### iOS (IPA):
1. Abre Xcode con `yarn cap:ios`
2. Selecciona tu equipo de desarrollo
3. Ve a **Product > Archive**
4. Sube a App Store Connect

---

## 🎨 Personalizar Iconos y Splash Screen

### Iconos de la App:
- **Android**: Reemplaza los archivos en `android/app/src/main/res/mipmap-*`
- **iOS**: Reemplaza en `ios/App/App/Assets.xcassets/AppIcon.appiconset`

Tamaños requeridos:
- Android: 48x48, 72x72, 96x96, 144x144, 192x192 px
- iOS: 20x20 a 1024x1024 px (múltiples tamaños)

### Splash Screen:
Configura en `capacitor.config.json`:
```json
{
  "plugins": {
    "SplashScreen": {
      "launchShowDuration": 2000,
      "backgroundColor": "#0D0D0D",
      "showSpinner": true,
      "spinnerColor": "#708238"
    }
  }
}
```

---

## 🔧 Configuración del Backend para Producción

Antes de publicar, actualiza la URL del backend:

1. En el build de producción, asegúrate de que `REACT_APP_BACKEND_URL` apunte a tu servidor de producción
2. Considera usar variables de entorno diferentes para desarrollo y producción

---

## 📝 Checklist para Publicación

### Google Play Store:
- [ ] App firmada con tu keystore
- [ ] Capturas de pantalla (mínimo 2)
- [ ] Ícono de alta resolución (512x512)
- [ ] Descripción corta y larga
- [ ] Política de privacidad (URL)
- [ ] Categoría: Negocios / Punto de Venta

### Apple App Store:
- [ ] App firmada con certificado de distribución
- [ ] Capturas de pantalla para iPhone y iPad
- [ ] Ícono (1024x1024)
- [ ] Descripción y palabras clave
- [ ] Política de privacidad (URL)
- [ ] Información de contacto

---

## 💡 Tips

1. **Prueba antes de publicar**: Usa TestFlight (iOS) y Google Play Internal Testing (Android)
2. **Versiones**: Incrementa el número de versión en `capacitor.config.json` antes de cada release
3. **Permisos**: Revisa los permisos solicitados en ambas plataformas

---

## 🆘 Solución de Problemas

### Error: "SDK location not found"
Crea el archivo `android/local.properties`:
```
sdk.dir=/ruta/a/tu/Android/Sdk
```

### Error en iOS: "Signing requires a development team"
En Xcode, selecciona tu equipo en **Signing & Capabilities**

---

¿Necesitas ayuda? Contacta soporte en Emergent.
