#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consultas.py
------------
Ejecuta las 5 consultas del negocio contra Cassandra, muestra resultados de
ejemplo y mide la latencia (promedio, p50, p95) repitiendo cada una N veces.
Imprime una tabla en Markdown lista para pegar en la documentacion.

Uso (desde el contenedor Python en la red 'cassnet'):
    python python/consultas.py                # QUORUM, 100 repeticiones
    python python/consultas.py --cl ONE --n 200
    python python/consultas.py --vuelo GT0476-20261204
Ninguna consulta usa ALLOW FILTERING.
"""
import argparse
import calendar
import os
import statistics
import time
from datetime import datetime

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy

KEYSPACE = "aerolinea"
DC_LOCAL = "dc1"
HOSTS = os.environ.get("CASSANDRA_HOSTS", "cass1,cass2,cass3").split(",")


def conectar(cl):
    perfil = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=DC_LOCAL)),
        consistency_level=cl, request_timeout=30)
    cluster = Cluster(HOSTS, execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
    return cluster, cluster.connect(KEYSPACE)


def meses(desde, hasta):
    """Itera los buckets 'YYYY-MM' entre dos fechas (inclusive)."""
    y, m = desde.year, desde.month
    while (y, m) <= (hasta.year, hasta.month):
        yield "%04d-%02d" % (y, m)
        m += 1
        if m == 13:
            y, m = y + 1, 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cl", default="QUORUM", choices=["ONE", "QUORUM", "ALL"])
    ap.add_argument("--n", type=int, default=100, help="repeticiones por consulta")
    ap.add_argument("--vuelo", default=None, help="codigo de vuelo para Q1/Q3/Q4")
    ap.add_argument("--top", type=int, default=5, help="N del Top N (Q5)")
    args = ap.parse_args()

    cl = getattr(ConsistencyLevel, args.cl)
    cluster, s = conectar(cl)
    try:
        # ---- Parametros de ejemplo (se leen de los datos cargados) ----
        if args.vuelo:
            vuelo = s.execute("SELECT codigo_vuelo, ruta, fecha_salida FROM vuelos_por_codigo "
                              "WHERE codigo_vuelo = %s", (args.vuelo,)).one()
        else:
            vuelo = s.execute("SELECT codigo_vuelo, ruta, fecha_salida FROM vuelos_por_codigo LIMIT 1").one()
        if vuelo is None:
            raise SystemExit("No se encontro el vuelo. Ya cargaste los datos?")
        codigo, ruta, f_salida = vuelo.codigo_vuelo, vuelo.ruta, vuelo.fecha_salida
        pasajero = s.execute("SELECT pasajero_id FROM historial_por_pasajero LIMIT 1").one().pasajero_id

        d1, d2 = datetime(2026, 10, 1), datetime(2027, 3, 31, 23, 59, 59)   # rango Q2
        r1, r2 = datetime(2026, 10, 1), datetime(2026, 12, 31, 23, 59, 59)  # rango Q4 / Q5
        m_ini = datetime(f_salida.year, f_salida.month, 1)
        ultimo = calendar.monthrange(f_salida.year, f_salida.month)[1]
        m_fin = datetime(f_salida.year, f_salida.month, ultimo, 23, 59, 59)

        # ---- Sentencias preparadas ----
        p1 = s.prepare("SELECT clase, disponibles, ocupados FROM asientos_contadores_por_vuelo WHERE codigo_vuelo = ?")
        p2 = s.prepare("SELECT fecha_salida, codigo_vuelo, origen, destino, fila, letra, clase, estado_reserva, monto, estado_pago "
                       "FROM historial_por_pasajero WHERE pasajero_id = ? AND fecha_salida >= ? AND fecha_salida <= ? "
                       "ORDER BY fecha_salida ASC")
        p3 = s.prepare("SELECT fila, letra, nombre_pasajero, identificacion, clase, estado_reserva, estado_pago "
                       "FROM manifiesto_por_vuelo WHERE codigo_vuelo = ?")
        p4 = s.prepare("SELECT fecha_salida, codigo_vuelo, capacidad, confirmadas FROM ocupacion_por_ruta_mes "
                       "WHERE ruta = ? AND mes = ? AND fecha_salida >= ? AND fecha_salida <= ?")
        p5 = s.prepare("SELECT codigo_vuelo, ruta, total_centavos FROM top_vuelos_por_ingresos WHERE periodo = ? LIMIT ?")

        def q1():
            return s.execute(p1, (codigo,)).all()

        def q2():
            return s.execute(p2, (pasajero, d1, d2)).all()

        def q3():
            return s.execute(p3, (codigo,)).all()

        def q4():
            # Una consulta por cada bucket (ruta, mes) dentro del rango
            filas = []
            for mes in meses(m_ini, m_fin):
                filas += s.execute(p4, (ruta, mes, m_ini, m_fin)).all()
            return [(f.codigo_vuelo, f.capacidad, f.confirmadas,
                     round(f.confirmadas * 100.0 / f.capacidad, 2)) for f in filas]

        def q5():
            # Una consulta por mes (cada vuelo esta en un solo periodo); se mezclan los N mayores
            filas = []
            for mes in meses(r1, r2):
                filas += s.execute(p5, (mes, args.top)).all()
            filas.sort(key=lambda f: f.total_centavos, reverse=True)
            return [(f.codigo_vuelo, f.ruta, f.total_centavos / 100.0) for f in filas[:args.top]]

        consultas = [
            ("Q1 Disponibilidad por clase", q1),
            ("Q2 Historial de pasajero", q2),
            ("Q3 Manifiesto de vuelo", q3),
            ("Q4 % ocupacion ruta/fechas", q4),
            ("Q5 Top N ingresos", q5),
        ]

        print("Consistency Level: %s | repeticiones: %d | vuelo: %s | ruta: %s\n" %
              (args.cl, args.n, codigo, ruta))
        print("| Consulta | filas | promedio (ms) | p50 (ms) | p95 (ms) | max (ms) |")
        print("|---|---|---|---|---|---|")
        muestras = {}
        for nombre, fn in consultas:
            fn()                                  # calentamiento (no se mide)
            tiempos = []
            for _ in range(args.n):
                t0 = time.perf_counter()
                res = fn()
                tiempos.append((time.perf_counter() - t0) * 1000)
            muestras[nombre] = res
            tiempos.sort()
            print("| %s | %d | %.2f | %.2f | %.2f | %.2f |" % (
                nombre, len(res), statistics.mean(tiempos),
                tiempos[len(tiempos) // 2], tiempos[int(len(tiempos) * 0.95) - 1],
                tiempos[-1]))

        print("\n--- Resultados de ejemplo (primeras filas) ---")
        for nombre, res in muestras.items():
            print("\n%s" % nombre)
            for fila in res[:5]:
                print("   ", tuple(fila) if hasattr(fila, "_fields") else fila)
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
