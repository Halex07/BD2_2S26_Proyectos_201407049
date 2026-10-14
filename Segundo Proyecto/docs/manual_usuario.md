# Manual de Usuario – Sistema de Recomendación de Restaurantes (Neo4j)

## 1. Requisitos
- Neo4j Desktop 5.x **o** Neo4j Community Edition 5.x
- Python 3.8+ (solo para regenerar los CSV; ya vienen incluidos en `datos/csv/`)

## 2. Instalar y configurar Neo4j
1. Descarga e instala **Neo4j Desktop** desde https://neo4j.com/download/ .
2. Crea un proyecto y un **DBMS local** (versión 5.x). Define una contraseña y presiona **Start**.
3. Abre **Neo4j Browser** (botón *Open*). Verifica con `RETURN 1;`.
4. (Community sin Desktop) Descomprime, ejecuta `bin/neo4j console` y abre http://localhost:7474 .

## 3. Preparar los CSV
1. (Opcional) Regenerar datos: `cd datos && python generar_datos.py`.
2. Copia **todos** los archivos de `datos/csv/` a la carpeta **import** del DBMS:
   - Desktop: DBMS → `…` → *Open folder* → **Import**.
   - Community: `<NEO4J_HOME>/import`.

## 4. Crear el esquema y cargar los datos
1. En Neo4j Browser ejecuta el contenido de `modelo/01_schema.cypher` (crea constraints e índices).
2. Abre `carga/02_load_csv.cypher` y ejecuta **cada bloque por separado, en orden** (primero nodos, luego relaciones). Mantén la línea `:auto` al inicio de cada bloque.
   - Con `cypher-shell -f carga/02_load_csv.cypher` elimina las líneas `:auto`.
3. Valida con `consultas/05_validacion.cypher`. Esperado: 500 Usuario, 200 Restaurante, 100 Chef, 50 Platillo, 15 TipoCocina; V3–V7 = 0.

## 5. Ejecutar las consultas
Define parámetros en Browser y ejecuta cada consulta de `consultas/`:

```cypher
:param userId => 'U0001';
:param origen  => 'U0001';
:param destino => 'U0250';
```

| Archivo / consulta | Parámetros | Cómo interpretar |
|---|---|---|
| `03` Q1 Recomendación social | `userId` | Ordenada por `amigos_coincidentes` y `promedio_amigos`. Más amigos y menor `grado_mas_cercano` = mejor recomendación. `ejemplo_amigos` explica el porqué. |
| `03` Q1b Chefs compartidos | `userId` | Restaurantes con chefs que ya conoces por lugares que calificaste ≥4. |
| `03` Q2 Chefs de alto impacto | — | Chefs en restaurantes bien calificados y con platillos muy difundidos. |
| `03` Q3 Infravalorados | — | Alta tasa de reserva pero calificación bajo el promedio. |
| `03` Q4 Precio vs consumo | — | `diferencia` > 0: se gasta más de lo esperado para su categoría. |
| `03` Q5 Cocina favorita vs real | — | Usuarios cuya cocina más visitada difiere de la declarada. |
| `04` A1 Ruta más corta | `origen`, `destino` | `grados_de_separacion` = número de amistades en la cadena. |
| `04` A2 Restaurantes conectados | — | `puntaje_conectividad` = chefs + platillos destacados. |

**Ejemplo práctico**: con `userId = 'U0001'`, Q1 devuelve hasta 10 restaurantes. Si el primero muestra `amigos_coincidentes = 4`, `promedio_amigos = 4.75`, `grado_mas_cercano = 1`, significa que 4 personas de su red (al menos una amiga directa) lo calificaron con ≥4 y U0001 nunca lo ha visitado.

## 6. Visualizar el grafo
- `CALL db.schema.visualization();` muestra el esquema.
- Vecindad de un usuario: `MATCH p=(:Usuario {id:'U0001'})-[*1..2]-() RETURN p LIMIT 100;`
- (Opcional) Neo4j Bloom para exploración visual.

## 7. Problemas comunes
| Síntoma | Solución |
|---|---|
| `Couldn't load the external resource at file:/.../usuarios.csv` | Los CSV no están en la carpeta **import**; revisa el nombre exacto. |
| `Invalid input 'IN'`/error con `IN TRANSACTIONS` | Falta el prefijo `:auto` en Browser, o estás en Neo4j 4.x (ahí usa `USING PERIODIC COMMIT`). |
| `Unknown function 'date'` o similares | Versión de Neo4j < 3.4; actualiza a 5.x. |
| Error de constraint al recargar | Los `MERGE` son idempotentes; si cambiaste los CSV, limpia con `MATCH (n) DETACH DELETE n;` y recarga. |
| Q1 devuelve vacío | El usuario no existe o sus amigos no tienen calificaciones ≥4 sobre restaurantes no visitados por él; prueba otro `userId`. |
| Error con identificadores `CALIFICÓ`/`VISITÓ` | Escríbelos entre backticks: `` `CALIFICÓ` ``. |
| `CALL { } IN TRANSACTIONS` no se puede en transacción explícita | Ejecuta el bloque como una sola sentencia, sin `BEGIN`. |
