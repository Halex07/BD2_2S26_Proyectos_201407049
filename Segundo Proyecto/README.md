# Segundo Proyecto – Sistema de Recomendación de Restaurantes con Neo4j

```
Segundo Proyecto/
├── modelo/     01_schema.cypher               constraints e índices
├── datos/      generar_datos.py + csv/        13 CSV (nodos y relaciones)
├── carga/      02_load_csv.cypher             LOAD CSV con MERGE y lotes
├── consultas/  03_consultas_negocio.cypher    5 consultas obligatorias (+Q1b)
│               04_analisis_redes.cypher       shortestPath y restaurantes conectados
│               05_validacion.cypher           validación de integridad
└── docs/       documentacion_tecnica.md · manual_usuario.md
```
Orden de ejecución: `01_schema` → copiar CSV a `import/` → `02_load_csv` → `05_validacion` → `03` / `04`.
