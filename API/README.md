# API de estudiantes — entrega portable

## Qué hace

Servicio HTTP desarrollado con FastAPI para consultar estudiantes históricos y gestionar matrículas nuevas. Se ejecuta con Docker Compose e incluye una API, MariaDB para matrículas y cuatro motores históricos:

- **MariaDB** replica las matrículas guardadas en SQLite y conserva los datos de prueba de `data/Central.csv`; permite modificarlas y eliminarlas.
- **Derby, HSQLDB, H2 y Oracle** alojan los registros históricos de las cuatro casas. La API los consulta, sin ofrecer operaciones de escritura sobre ellos.
- **SQLite** guarda primero las matrículas nuevas y conserva temporalmente resultados históricos para acelerar consultas repetidas. MariaDB replica esas matrículas.

La consulta de estudiantes combina las matrículas de SQLite y MariaDB con los datos históricos y evita duplicados. Las búsquedas por identificador admiten IDs base con variantes. Los datos CSV se usan para inicializar las tablas históricas vacías y las matrículas de Central en MariaDB.

## Cómo funciona

FastAPI expone las rutas y la documentación interactiva. Las consultas y operaciones de matrícula (excepto el estado y la documentación) requieren la cabecera `X-API-Key`. La clave se configura por instalación y no debe compartirse.

La ruta `/salud` comprueba la API y MariaDB. `/docs` ofrece Swagger UI; también están disponibles `/redoc` y `/openapi.json`. Las conexiones de bases de datos son internas a la red de Docker. SQLite se guarda en un volumen persistente.

La inicialización puede crear tablas y cargar los CSV cuando las tablas están vacías. Por ello, el primer arranque escribe los datos iniciales en los motores históricos y carga `data/Central.csv` en `enrollments` de MariaDB si esa tabla está vacía. Si ya contiene alguna matrícula, no se importa Central: no se sobrescriben ni se mezclan los datos existentes. La carga conserva los IDs del CSV, valida nombres, apellidos, fechas y casa Central, y se confirma en una sola transacción; si hay un error, se revierte la carga completa. Reiniciar con una tabla no vacía no duplica ni restaura filas eliminadas. Si se vacía por completo, el siguiente arranque vuelve a cargarla. Las matrículas nuevas se guardan primero en SQLite y después se replican en MariaDB; si MariaDB no confirma el alta, la fila queda pendiente y se reintenta al arrancar. Los volúmenes Docker conservan datos entre reinicios.

## Por qué está organizado así

Separar matrículas nuevas de los registros históricos evita modificar las fuentes históricas. Las matrículas nuevas se guardan primero en SQLite y después se replican en MariaDB; la caché de históricos reduce consultas repetidas sin sustituir a las fuentes originales. Docker Compose reúne la API y sus dependencias, de modo que otro equipo pueda iniciar el conjunto sin instalar localmente Java, JDBC ni los cinco servidores de base de datos. La clave y las contraseñas se generan en el equipo destino, en lugar de trasladar credenciales del PC original.

## Contenido

- `app/main.py`: aplicación, endpoints, autenticación, consultas y caché.
- `compose.yaml`: API y servicios de base de datos aislados en Docker.
- `Dockerfile`, `db-image/`: imágenes de la API y de los motores JDBC.
- `init/mariadb.sql`: esquema inicial para matrículas nuevas.
- `data/*.csv`: datos de inicialización de ejemplo para las fuentes históricas y MariaDB (`Central.csv`).
- `requirements.txt`: dependencias Python.
- `.env.example`, `preparar_config.py`: configuración inicial sin secretos reales.

El paquete no incluye contraseñas del servidor original, bases de datos en ejecución, cachés, entornos virtuales ni respaldos de matrículas. Los CSV pueden contener datos personales o de prueba; distribuye la carpeta solo con autorización para compartirlos.

## Instalación en otro equipo

Requisitos: Docker Desktop con contenedores Linux, Python 3 para generar la configuración, conexión a Internet para descargar imágenes y paquetes, y recursos suficientes para ejecutar cinco bases de datos. El paquete está orientado a x86-64; Oracle puede requerir una plataforma compatible.

1. Copia la carpeta completa a otro equipo y abre una terminal en ella.
2. Genera credenciales propias. El script no muestra secretos ni reemplaza un `.env` existente:

   ```powershell
   python preparar_config.py
   ```

   Si el comando no está disponible, prueba `py preparar_config.py`. No compartas ni subas `.env`.

3. Valida y arranca el proyecto:

   ```powershell
   docker compose -p api config -q
   docker compose -p api up -d --build
   docker compose -p api ps
   ```

   El primer arranque descarga imágenes, inicia cinco motores y carga los CSV en las tablas históricas vacías y `Central.csv` en MariaDB si no hay matrículas. Puede tardar varios minutos.

4. Comprueba el servicio y abre la documentación:

   ```powershell
   Invoke-RestMethod http://(ip del equipo donde esta alojada la api):8000/salud
   Start-Process http://(ip del equipo donde esta alojada la api):8000/docs
   ```

   En Swagger, pulsa **Authorize** e introduce el valor local de `API_ACCESS_KEY` de `.env`.

## Endpoints principales

| Método | Ruta | Función |
|---|---|---|
| GET | `/salud` | Estado del servicio |
| GET | `/estudiantes?name=Ana&house=Central&limit=20` | Búsqueda por nombre/casa |
| GET | `/estudiantes/{student_id}` | Detalle o coincidencias por ID |
| POST | `/matriculas` | Alta: primero SQLite y después MariaDB |
| PUT | `/matriculas/{student_id}` | Modificación en MariaDB y en su copia local |
| DELETE | `/matriculas/{student_id}` | Baja en MariaDB y en su copia local |

Consulta `/docs` para los campos exactos, parámetros y respuestas actuales. La API también conserva alias en inglés para clientes anteriores.

## Mantenimiento y límites

```powershell
docker compose -p api logs --tail=100 api
docker compose -p api stop
docker compose -p api start
docker compose -p api down
```

`down` conserva los volúmenes. No uses `down -v` salvo que quieras borrar permanentemente las bases y la caché de esta instalación.

El puerto publicado se limita a `0.0.0.0`: la API queda accesible desde cualquier equipo de la red.

## Incorporar cambios en Central.csv

Los CSV se copian dentro de la imagen de la API. Tras añadir o cambiar `data/Central.csv`, reconstruye la API desde esta carpeta:

```powershell
docker compose -p api up -d --build
```

Esto conserva los volúmenes. No borres matrículas ni volúmenes para forzar la importación: si MariaDB ya contiene datos, conserva esos datos y planifica una importación adicional por separado.

## Pruebas Python aisladas con .venv

La carpeta `test/` contiene pruebas automatizadas del codigo real de `app/main.py`.
No hay una copia de la API: asi los tests siempre comprueban tu implementacion actual.
Usan `unittest` (incluido con Python), FastAPI TestClient y SQLite temporal.
No necesitan arrancar Docker, Java ni servidores de bases de datos.

### Crear el entorno virtual (Windows / PowerShell)

Abre una terminal en la carpeta del proyecto. Python 3.10 o posterior es necesario;
la preparacion se ha realizado con Python 3.13.

```powershell
cd (Tu ruta de la api)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r \requirements.txt
```

Si no existe el comando `python`, usa `py -3 -m venv .venv` en su lugar.
Si `.venv` ya existe, reutilizalo: no hace falta recrearlo en cada ejecucion.
Estos comandos instalan solo las dependencias necesarias para las pruebas aisladas.
`requirements.txt` sigue siendo la lista de dependencias del servicio completo en Docker;
este entorno de pruebas no sustituye ese despliegue ni sus controladores JDBC/Oracle.

### Ejecutar los tests

Desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -v
```

Ejecutar un unico test:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_*.py" -k test_crear_genera_id -v
```
Listado de teses individuales por si se quieren probar uno a uno 
```
test_rutas_protegidas_sin_clave
test_clave_incorrecta
test_limites_invalidos
test_listado_vacio
test_identificadores_repetidos
test_crear_genera_id_e_ignora_id_cliente
test_openapi_publico
test_cache_temporal
test_alias_en_ingles
test_consulta_base_devuelve_variantes
test_fecha_invalida
test_busqueda_por_nombre_y_casa
test_historicos_sin_duplicar_matricula
test_modificar_inexistente
test_actualizar_matricula
test_eliminar_matricula
test_consultar_matricula_por_id
test_validacion_nombres
test_clave_no_configurada
```

Si todo esta bien aparece `OK`; un fallo muestra la prueba y su motivo.
Las pruebas cubren autenticacion, salud, validacion de entradas, altas, consultas,
filtros, identificadores repetidos, modificaciones, bajas, cache, alias y OpenAPI.

### Activacion opcional y aislamiento de otros proyectos

No necesitas activar el entorno si usas la ruta completa a su `python.exe`, como arriba.
Asi no cambias el Python ni los paquetes de otros proyectos, y tampoco necesitas
cambiar la politica de ejecucion de PowerShell. Nunca uses `pip` global para estas pruebas.

Si prefieres activarlo:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s test -p "test_*.py" -v
deactivate
```

Si PowerShell bloquea `Activate.ps1`, usa directamente `.\.venv\Scripts\python.exe`;
no es necesario modificar la politica del equipo. En VS Code selecciona ese mismo
interprete con **Python: Select Interpreter**. Cada proyecto debe tener su propio `.venv`.
No copies ni compartas `.venv`: se reconstruye con los comandos anteriores.

### Que se aisla y que no se comprueba

Cada prueba crea sus propias bases SQLite dentro del directorio temporal del sistema,
las cierra y las elimina al terminar. Se usa una clave ficticia; no se lee `.env`.
No se consultan tus CSV reales, no se envian peticiones a una API desplegada y no
se modifican matriculas ni volumenes Docker reales.

Se sustituyen los controladores externos, las consultas historicas y el bloqueo
especifico de MariaDB; el CRUD y los modelos usan SQLAlchemy real con SQLite.
TestClient se utiliza sin arrancar el ciclo de inicio que carga las bases reales.
Por tanto, son pruebas aisladas de logica y rutas HTTP, no pruebas de integracion
contra MariaDB, Oracle, H2, HSQLDB o Derby, ni de concurrencia del bloqueo MariaDB.
Para esos casos haria falta un despliegue de integracion separado con datos desechables.

