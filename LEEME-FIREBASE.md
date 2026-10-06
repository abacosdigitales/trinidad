# Trinidad Computers · Pedidos y precios con Firebase

Cómo queda funcionando:

- El cliente arma su PC en `armador.html` y toca **Confirmar pedido**: el pedido llega solo a tu panel (`admin.html`), con aviso en pantalla y sonido.
- Los precios de venta viven en Firestore. El armador los lee de ahí (y de `precios.json` si Firebase no responde).
- **Una vez por semana** un robot (GitHub Actions) lee los precios de tu proveedor, actualiza tus costos y publica los precios nuevos. Si un precio cambia más de 35%, queda retenido para que lo revises.
- Tus costos y tu margen están en una zona privada de Firestore: solo los ve tu usuario.
- Si Firebase no está configurado, todo sigue funcionando como antes (WhatsApp y panel local).

Costo: el plan gratuito de Firebase (Spark) alcanza de sobra para este uso y no pide tarjeta. GitHub Actions también es gratis.

## Paso a paso (unos 30–40 minutos)

### 1. Crear el proyecto
1. Entrá a https://console.firebase.google.com con tu cuenta de Google → **Agregar proyecto** → nombre `trinidad-computers` (podés desactivar Google Analytics).
2. **Compilación → Firestore Database → Crear base de datos** → ubicación `southamerica-east1` (São Paulo) → modo **producción**.

### 2. Tu usuario administrador
1. **Compilación → Authentication → Comenzar → Correo electrónico/contraseña → Habilitar**.
2. Pestaña **Users → Agregar usuario** con tu correo y una contraseña larga.
3. Copiá el **UID de usuario** que aparece en esa lista.

### 3. Reglas de seguridad (lo más importante)
1. Abrí `firebase/firestore.rules` y reemplazá `TU_UID_ADMIN` por tu UID.
2. En Firestore → pestaña **Reglas**, pegá todo el contenido y tocá **Publicar**.

Qué permiten: cualquiera puede **crear** un pedido (con campos validados) pero **no leer, modificar ni borrar** pedidos; cualquiera puede **leer** los precios de venta; solo vos podés leer/escribir costos, margen y reportes.

### 4. Conectar las páginas
1. **Configuración del proyecto (engranaje) → Tus apps → Web (`</>`)** → registrá la app → copiá el objeto `firebaseConfig`.
2. Pegalo en `firebase-config.js` (esos datos no son secretos).
3. Subí al sitio, en la misma carpeta: `index.html`, `armador.html`, `admin.html`, `fb.js`, `firebase-config.js`, `precios.json` y los íconos.
4. En **Authentication → Configuración → Dominios autorizados** agregá el dominio donde publiques el sitio.

### 5. Cargar tus datos iniciales (una sola vez, desde tu PC)
1. En Firebase: **Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada**. Se descarga un `.json`. **Es una llave maestra: no la subas al sitio ni a GitHub.**
2. En una terminal, dentro de la carpeta `herramientas/`:
   ```
   pip install firebase-admin
   set GOOGLE_APPLICATION_CREDENTIALS=C:\ruta\a\la-clave.json      (Windows)
   export GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/la-clave.json     (Mac/Linux)
   python actualizar_precios.py --sembrar
   ```
   Esto sube tu margen, tus costos y los primeros precios de venta.
3. Probá: abrí `admin.html`, ingresá con tu correo → pestaña **Precios**: tienen que aparecer los 50 componentes.

### 6. El robot semanal
1. Subí el contenido del repositorio (ver la sección «Archivos del repositorio» más abajo). **No subas** `herramientas/config.json`, `herramientas/costos.json` ni la clave de servicio: tienen tu margen, tus costos o acceso total a tu proyecto. El `.gitignore` incluido los excluye.
2. En GitHub: **Settings → Secrets and variables → Actions → New repository secret** → nombre `FIREBASE_SERVICE_ACCOUNT`, valor: todo el contenido del `.json` del paso 5.
3. Pestaña **Actions → Actualizar precios (semanal) → Run workflow** para probarlo ya. Después corre solo todos los lunes a las 6:00 (hora de Argentina).
4. Mirá el resultado en `admin.html → Precios → Última actualización automática`: te muestra cuántos precios quedaron retenidos o sin actualizar.

Si el robot falla, GitHub te manda un correo. Aviso: los sitios de los proveedores pueden bloquear a los servidores de GitHub; si pasa, corré el script desde tu PC (`python actualizar_precios.py --firebase` con la clave configurada) o programalo en el Programador de tareas de Windows.

### 7. Probar el circuito completo
1. Abrí `armador.html`, armá una PC y tocá **Confirmar pedido** con datos de prueba.
2. Con `admin.html` abierto, tiene que aparecer el pedido con un aviso 🔔 y el contador en la pestaña del navegador.
3. Cambiale el estado, editalo, imprimí el presupuesto o mandale el texto al cliente por WhatsApp.

## Mantenimiento
- **Cambiar tu margen, armado o envío**: `admin.html → Precios`, ajustá y tocá **Guardar y publicar precios**. Los clientes ven el cambio al instante.
- **Corregir un costo a mano**: en esa misma tabla. El robot lo vuelve a actualizar la semana siguiente.
- **Agregar otro proveedor o pieza**: hay que ampliar `herramientas/actualizar_precios.py` (reglas `MATCH`).

## Seguridad y privacidad (leer)
- **Spam**: las reglas validan los campos, pero Firestore no puede limitar la cantidad de pedidos. El armador ya frena reenvíos en el mismo navegador durante 1 minuto. Para blindarlo contra bots, activá **App Check (reCAPTCHA v3)** en Firebase; se puede sumar después.
- **Datos personales**: los pedidos guardan nombre, teléfono y, si lo ponen, email y dirección. El armador pide aceptación expresa. Conviene sumar una política de privacidad al sitio y atender los pedidos de baja de datos (Ley 25.326).
- **Total del pedido**: el cliente envía solo las piezas elegidas; el panel recalcula el total con los precios actuales y te marca «cliente vio $X» si difiere.
- **Pedidos viejos del panel local**: si usabas `admin.html` sin Firebase, esos pedidos siguen en ese navegador; usá «Respaldo» y «Restaurar» para pasarlos a Firestore.
- **No te quedes sin acceso**: guardá tu contraseña y la clave de servicio en un lugar seguro.

## Archivos del repositorio

```
index.html                        portada
armador.html                      armador de PCs (con «Confirmar pedido»)
admin.html                        tu panel (pide usuario y contraseña)
fb.js                             conexión con Firebase
firebase-config.js                tu configuración de Firebase (pegala vos; no es secreta)
precios.json                      precios de venta de respaldo (sin costos ni margen)
favicon.ico  favicon-32.png  apple-touch-icon.png  icon-192.png  icon-512.png  site.webmanifest
img/                              fotos de componentes (opcional; nombres en imagenes-necesarias.csv)
imagenes-necesarias.csv           lista de nombres de archivo para las fotos
LEEME-FIREBASE.md                 esta guía
.gitignore                        evita subir archivos privados por error
.github/workflows/precios-semanales.yml    robot de los lunes
firebase/firestore.rules          reglas de seguridad (el UID real lo pegás en la consola, no acá)
herramientas/actualizar_precios.py         script de precios
herramientas/config.publica.json           proveedores a leer (sin tu margen)
herramientas/LEEME.txt  herramientas/actualizar.bat
```

**Solo en tu PC (nunca al repositorio):** `herramientas/config.json` y `herramientas/costos.json` (si querés usar el script sin Firebase) y el `.json` de la clave de servicio.
Si tu repositorio es **público** (GitHub Pages gratis lo requiere), esto es especialmente importante.

Nota: en repositorios públicos GitHub **desactiva los workflows programados tras 60 días sin actividad**. Si pasa, entrá a Actions y reactivalo, o hacé cualquier cambio en el repositorio cada tanto.
