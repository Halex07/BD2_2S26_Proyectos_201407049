# Sistema de Gestión de Reservas y Boletos Aéreos con Apache Cassandra

Proyecto 1 — Sistemas de Bases de Datos 2  
Universidad de San Carlos de Guatemala, Facultad de Ingeniería

- **Estudiante:** Henry Alexander García Montúfar
- **Carnet:** 201407049

## Descripción

Base de datos distribuida en Apache Cassandra 4.1 para gestionar vuelos,
aeronaves, asientos, pasajeros, reservas y pagos de una aerolínea. El modelo
se diseñó a partir de las consultas (Query-Driven Modeling): una tabla
especializada por patrón de acceso, sin JOINs y sin `ALLOW FILTERING`.

## Requisitos

- Docker Desktop (con WSL2 en Windows), unos 8 GB de RAM libres
- Python 3.11+ (se ejecuta dentro de un contenedor, no hace falta instalarlo)

## Estructura

```
Primer Proyecto/
├── docker-compose.yml        # clúster de 3 nodos
├── cql/
│   ├── 01_keyspace.cql       # keyspace (NetworkTopologyStrategy, RF=3)
│   ├── 02_tablas.cql         # tablas del modelo lógico
│   └── 03_consultas.cql      # las 5 consultas con TRACING
├── python/
│   ├── requirements.txt
│   ├── carga_masiva.py       # 100,000 reservas con Batch Writes
│   ├── consultas.py          # las 5 consultas + medición de latencia
│   └── pruebas_consistencia.py  # ONE / QUORUM / ALL y nodos caídos
├── resultados/               # salidas de las pruebas (CSV)
└── docs/                     # modelo ER, documentación técnica, manual de usuario
```

## Puesta en marcha

Todos los comandos se ejecutan desde la carpeta `Primer Proyecto`.

**1. Levantar el clúster** (tarda de 3 a 6 minutos; los nodos se unen de uno en uno):

```powershell
docker compose up -d
docker exec -it cass1 nodetool status     # deben aparecer 3 nodos en UN
```

**2. Crear keyspace y tablas:**

```powershell
docker cp .\cql cass1:/tmp/cql
docker exec -it cass1 cqlsh -f /tmp/cql/01_keyspace.cql
docker exec -it cass1 cqlsh -f /tmp/cql/02_tablas.cql
docker exec -it cass1 cqlsh -e "USE aerolinea; DESCRIBE TABLES;"
```

**3. Abrir un contenedor Python en la red del clúster:**

```powershell
docker run -it --rm --network cassnet -v "${PWD}:/app" -w /app python:3.11 bash
pip install -r python/requirements.txt
```

**4. Cargar los datos** (dentro del contenedor Python):

```bash
python python/carga_masiva.py --dry-run      # solo genera y valida en memoria
python python/carga_masiva.py --truncate     # carga real; termina con "TODO OK"
```

**5. Ejecutar y medir las consultas:**

```bash
python python/consultas.py                   # tabla de latencias (100 repeticiones)
```

O con TRACING en cqlsh, usando `cql/03_consultas.cql`.

**6. Pruebas de tolerancia a fallos y Consistency Levels:**

```bash
python python/pruebas_consistencia.py --escenario 3_nodos
# PowerShell: docker stop cass3   (esperar a ver DN en nodetool status)
python python/pruebas_consistencia.py --escenario 1_nodo_caido
# PowerShell: docker stop cass2
python python/pruebas_consistencia.py --escenario 2_nodos_caidos
# PowerShell: docker start cass2 cass3 ; docker exec cass1 nodetool repair aerolinea
python python/pruebas_consistencia.py --verificar
python python/pruebas_consistencia.py --resumen
```

## Configuración del clúster

| Parámetro | Valor |
|---|---|
| Nodos | 3 (`cass1`, `cass2`, `cass3`) en Docker |
| Datacenter / rack | `dc1` / `rack1` (GossipingPropertyFileSnitch) |
| Estrategia de replicación | `NetworkTopologyStrategy` |
| Replication Factor | 3 (`dc1: 3`) |
| Consistency Level por defecto | `QUORUM` (2 de 3 réplicas) |

## Modelo lógico: qué tabla responde cada consulta

| Consulta | Tabla | Primary Key |
|---|---|---|
| Q1 Disponibilidad de asientos por clase | `asientos_contadores_por_vuelo` | `((codigo_vuelo), clase)` |
| Q2 Historial cronológico de un pasajero | `historial_por_pasajero` | `((pasajero_id), fecha_salida, reserva_id)` |
| Q3 Manifiesto de vuelo enriquecido | `manifiesto_por_vuelo` | `((codigo_vuelo), fila, letra)` |
| Q4 % de ocupación por ruta y fechas | `ocupacion_por_ruta_mes` | `((ruta, mes), fecha_salida, codigo_vuelo, capacidad)` |
| Q5 Top N de vuelos por ingresos | `top_vuelos_por_ingresos` | `((periodo), total_centavos, codigo_vuelo)` |

Tablas de apoyo (por entidad): `pasajeros_por_id`, `aeronaves_por_id`,
`vuelos_por_codigo`, `asientos_por_vuelo`, `reservas_por_id`,
`pagos_por_reserva`, `ingresos_por_vuelo`.

La justificación de cada llave de partición y clustering está en
`docs/` (documentación técnica).
