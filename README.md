# Dumblewindows — Aplicaciones

Proyecto de consulta de estudiantes y gestión de matrículas compuesto por una **API común** y tres aplicaciones cliente: **DumbleFX**, **Dumbledroid** y **DumbleUnity**.

La API centraliza el acceso a los datos. Cada cliente ofrece una experiencia distinta: gestión desde el escritorio, consultas desde Android o visualización de patronus animados en Unity.

## Índice

- [Aplicaciones](#aplicaciones)
- [Arquitectura](#arquitectura)
- [Estructura](#estructura)
- [Requisitos](#requisitos)
- [Puesta en marcha](#puesta-en-marcha)
- [Configuración de la conexión](#configuración-de-la-conexión)
- [Endpoints principales](#endpoints-principales)
- [Problemas frecuentes](#problemas-frecuentes)
- [Seguridad y mantenimiento](#seguridad-y-mantenimiento)
- [Documentación](#documentación)

## Aplicaciones

| Módulo | Aplicación | Funcionalidades |
| --- | --- | --- |
| [API](API/) | Servicio de estudiantes | Consulta de registros históricos y gestión de matrículas en MariaDB. |
| [JavaFX](JavaFX/) | DumbleFX | Consulta por ID o datos y creación, actualización y eliminación de matrículas. Interfaz en español, inglés y euskera. |
| [Android](Android/) | Dumbledroid | Consulta de estudiantes y conservación temporal de resultados en el dispositivo. No modifica los datos del servidor. |
| [Unity](Unity/) | DumbleUnity | Búsqueda de estudiantes por nombre y visualización de su patronus animado en pixel art. Proyecto orientado a Windows y Android. |

> Las altas, modificaciones y eliminaciones afectan a las **matrículas de MariaDB**, no a los registros históricos de las casas.

## Arquitectura

```text
DumbleFX ───────┐
Dumbledroid ────┼── HTTP/HTTPS + JSON + X-API-Key ── API FastAPI
DumbleUnity ────┘                                      │
                                                     ├── MariaDB: réplica de matrículas
                                                     ├── Derby: histórico
                                                     ├── HSQLDB: histórico
                                                     ├── H2: histórico
                                                     ├── Oracle: histórico
                                                     └── SQLite: matrículas (primera escritura) y caché histórica
```

Los clientes se comunican con la API, no directamente con las bases de datos. SQLite guarda primero las matrículas nuevas y reduce consultas históricas repetidas, pero no sustituye a las fuentes originales.

Docker Compose reúne la API y sus servidores de bases de datos. Los CSV de `API/data/` permiten inicializar las tablas correspondientes cuando están vacías. Las matrículas nuevas se guardan primero en SQLite y se replican en MariaDB.

## Estructura

```text
Dumblewindows_Aplicaciones/
├── API/
│   ├── app/                   # Aplicación FastAPI
│   ├── data/                  # CSV de inicialización
│   ├── db-image/              # Imágenes para motores JDBC
│   ├── init/                  # Inicialización de MariaDB
│   ├── test/                  # Pruebas de la API
│   ├── compose.yaml
│   ├── preparar_config.py
│   └── README.md
├── Android/
│   ├── Dumbledroid/           # Proyecto para Android Studio
│   └── README.md
├── JavaFX/
│   ├── src/                   # Java, FXML, estilos y traducciones
│   ├── pom.xml
│   └── README.md
├── Unity/
│   ├── DumbleUnity/           # Proyecto para Unity Hub
│   └── README.md
└── README.md
```

## Requisitos

Instala únicamente las herramientas de los módulos que vayas a utilizar. Si ya dispones de una API accesible, no necesitas desplegar otra para ejecutar los clientes.

| Módulo | Herramientas y requisitos |
| --- | --- |
| API local | Docker Desktop con contenedores Linux, Python 3 para generar la configuración y recursos para ejecutar cinco servidores de bases de datos. Despliegue orientado a x86-64. |
| DumbleFX | JDK 21 y Maven o el wrapper incluido. El proyecto declara JavaFX 21.0.6 y Jackson 2.17.2. |
| Dumbledroid | Android Studio compatible con la configuración Gradle y los SDK solicitados. El módulo declara `minSdk 30` y `compileSdk`/`targetSdk 37`. |
| DumbleUnity | Unity Hub y Unity **6000.3.24f1**, con los módulos de compilación para Windows o Android según el destino. |

La primera preparación necesita Internet para descargar dependencias e imágenes.

## Puesta en marcha

### 1. Descargar el proyecto

```powershell
git clone --branch main https://github.com/alain8123/Dumblewindows_Aplicaciones.git
cd Dumblewindows_Aplicaciones
```

### 2. Arrancar la API local

Omite este paso si vas a utilizar un servidor ya disponible. Desde la raíz del repositorio:

```powershell
cd api
python preparar_config.py
docker compose -p api config -q
docker compose -p api up -d --build
docker compose -p api ps
```

Si Windows no reconoce `python`, utiliza `py preparar_config.py`.

El script prepara las credenciales de la instalación sin reemplazar un `.env` existente. No compartas ese archivo. El primer arranque puede tardar varios minutos mientras se preparan las bases de datos.

Comprueba el servicio desde el mismo equipo:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/salud
Start-Process http://127.0.0.1:8000/docs
```

En Swagger UI, pulsa **Authorize** e introduce el valor de `API_ACCESS_KEY` de tu instalación para probar las operaciones protegidas.

### 3. Ejecutar DumbleFX

Abre una terminal en `JavaFX/`:

```powershell
.\mvnw.cmd clean javafx:run
```

En Linux, con permiso de ejecución para el wrapper:

```bash
./mvnw clean javafx:run
```

También puedes usar `mvn clean javafx:run` si tienes Maven instalado.

Configura la dirección de la API y la clave mediante el diálogo de la aplicación. El botón **Configuración** permite revisar esos valores.

Para generar y ejecutar el JAR con dependencias desde `JavaFX/`:

```powershell
.\mvnw.cmd clean package
java -jar target/dumbleFX_v1.jar
```

Para distribuirlo, utiliza una configuración externa; no presupongas que `config.properties` se incluye dentro del JAR:

```powershell
java -Ddumblefx.config="C:\ruta\config.properties" -jar target/dumbleFX_v1.jar
```

### 4. Ejecutar Dumbledroid

1. Abre **`Android/Dumbledroid/`** en Android Studio, no la carpeta superior `Android/`.
2. Copia `secrets.properties.example` como `secrets.properties` en la raíz del proyecto Android.
3. Introduce tu clave en la propiedad `API_KEY`, sin publicarla.
4. Revisa la URL base en `app/src/main/java/com/dm2/dumbledroid/Constantes.kt` y las rutas de consulta.
5. Sincroniza Gradle y ejecuta la aplicación en un emulador o dispositivo compatible.

La clave se incorpora a `BuildConfig` durante la compilación. Si la cambias, vuelve a compilar la aplicación.

### 5. Ejecutar DumbleUnity

1. Añade **`Unity/DumbleUnity/`** a Unity Hub y ábrelo con la versión indicada.
2. Abre la escena **`Assets/Scenes/menu.unity`**.
3. Selecciona **`ControladorConsultaAlumno`** en la jerarquía.
4. Configura en el Inspector **Url Base**, **Api Key** y **Nombre Cabecera**.
5. Para una API en el mismo PC, utiliza `url/estudiantes`; la cabecera habitual es `X-API-Key`.
6. Pulsa **Play** para comprobar la búsqueda y la visualización del patronus.

Consulta la guía de Unity para generar las versiones de Windows y Android.

## Configuración de la conexión

### Dirección del servidor

- **Cliente y API en el mismo PC:** puedes usar `http://127.0.0.1:8000` como dirección del servidor.
- **Cliente en otro equipo o móvil:** utiliza una dirección del servidor accesible desde ese dispositivo. `localhost` y `127.0.0.1` apuntan al propio dispositivo, no al PC que aloja la API.
- **Servidor remoto:** utiliza la dirección HTTPS proporcionada para ese despliegue y comprueba su accesibilidad.

No todos los clientes esperan el mismo valor: DumbleFX utiliza una URL base del servidor; el campo de DumbleUnity incluye la ruta `/estudiantes`.

### Ejemplo para DumbleFX

En desarrollo, la ruta predeterminada se calcula respecto al directorio de ejecución:

```text
src/main/resources/Dumblewindows/javafx/dumblefx/config.properties
```

Configuración mínima para una API en el mismo equipo:

```properties
DUMBLEFX_API_URL=http://127.0.0.1:8000 (o si usas 0.0.0.0 en el .env)  http://tu_ip:8000
DUMBLEFX_API_KEY=REEMPLAZAR_POR_TU_CLAVE
```

Las propiedades opcionales `DUMBLEFX_API_URL_CONSULTA_ID`, `DUMBLEFX_API_URL_CONSULTA_DATOS`, `DUMBLEFX_API_URL_CREAR`, `DUMBLEFX_API_URL_ACTUALIZAR` y `DUMBLEFX_API_URL_ELIMINAR` permiten establecer URLs por operación. Si están vacías, se utilizan las rutas predeterminadas. Las que reciben un ID deben conservar el marcador `{student_id}`.

Las variables de entorno no vacías con esos nombres prevalecen sobre el archivo. Si editas el archivo externamente, reinicia la aplicación.

El cliente JavaFX selecciona la versión por petición según el esquema: **HTTP/1.1 para `http://`** y **preferencia por HTTP/2 para `https://`**, sujeta a la negociación con el servidor. HTTPS no garantiza que se utilice HTTP/2.

## Endpoints principales

| Método | Ruta | Finalidad |
| --- | --- | --- |
| GET | `/salud` | Estado del servicio y MariaDB. |
| GET | `/estudiantes` | Buscar por nombre, casa y límite de resultados. |
| GET | `/estudiantes/{student_id}` | Consultar por identificador. |
| POST | `/matriculas` | Crear una matrícula en MariaDB. |
| PUT | `/matriculas/{student_id}` | Actualizar una matrícula. |
| DELETE | `/matriculas/{student_id}` | Eliminar una matrícula. |

Las operaciones de consulta y matrícula requieren `X-API-Key`. La documentación interactiva está en `/docs`; consulta allí los campos, validaciones y respuestas del servidor utilizado.

## Problemas frecuentes

| Problema | Qué revisar |
| --- | --- |
| No se puede conectar | Dirección, puerto, estado de la API, conectividad y cortafuegos. Comprueba primero `/salud`. |
| La clave no se acepta | Que el cliente envíe `X-API-Key` y su valor corresponda a la instalación del servidor. |
| Funciona en el PC, pero no en el móvil | Que la URL no apunte a `localhost` o `127.0.0.1` y sea accesible desde el móvil. |
| JavaFX carga otra configuración | Directorio de ejecución, argumento `-Ddumblefx.config` y variables de entorno. |
| No se permite modificar un estudiante | Que sea una matrícula gestionada en MariaDB, no un registro histórico. |
| Unity no muestra una animación | Que el estudiante tenga patronus y exista el recurso correspondiente; revisa la consola. |

## Seguridad y mantenimiento

- No publiques `.env`, `secrets.properties`, configuraciones con claves reales ni capturas que las muestren.
- Usa credenciales propias para cada instalación y sustituye los valores de ejemplo.
- Las claves distribuidas con aplicaciones cliente son recuperables: no equivalen a identificación individual por usuario.
- Revisa los CSV antes de compartirlos: pueden contener datos personales o datos de prueba cuya distribución requiera autorización.
- No expongas el despliegue local a Internet sin revisar autenticación, HTTPS y acceso de red.
- Comprueba los derechos de uso de imágenes, vídeos, fuentes y otros recursos antes de redistribuirlos. Este README no concede una licencia sobre el código ni sobre esos recursos.

Para consultar los registros de la API, desde `API/`:

```powershell
docker compose -p api logs --tail=100 api
```

Para detener el despliegue:

```powershell
docker compose -p api down
```

> No añadas `-v` salvo que quieras eliminar los volúmenes y sus datos. Detener o reiniciar los contenedores no sustituye una copia de seguridad.

La guía de la API incluye pruebas Python aisladas y sus instrucciones. Esta puesta en marcha no sustituye la comprobación de cada cliente contra una API real.

## Documentación

- [API: instalación, bases de datos, endpoints, mantenimiento y pruebas](API/README.md).
- [DumbleFX: pantallas, configuración, arquitectura y ejecución](JavaFX/README.md).
- [Dumbledroid: configuración, búsquedas, caché y generación de APK](Android/README.md).
- [DumbleUnity: escena, API, patronus y compilación](Unity/README.md).

Cada guía amplía las instrucciones de su módulo; los archivos de configuración y el código de la revisión utilizada determinan el comportamiento concreto.
