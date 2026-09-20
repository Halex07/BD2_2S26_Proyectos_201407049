#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pruebas_consistencia.py
-----------------------
Mide disponibilidad y rendimiento de lecturas y escrituras con los
Consistency Levels ONE, QUORUM y ALL en distintos escenarios del clúster
(3 nodos arriba, 1 caido, 2 caidos).

Los nodos se apagan/encienden a mano desde PowerShell (este script corre
dentro de un contenedor y no controla Docker). Flujo completo:

  1) Con los 3 nodos arriba:
        python python/pruebas_consistencia.py --escenario 3_nodos
  2) PowerShell:  docker stop cass3      (espera ~30 s y revisa nodetool status)
        python python/pruebas_consistencia.py --escenario 1_nodo_caido
  3) PowerShell:  docker stop cass2
        python python/pruebas_consistencia.py --escenario 2_nodos_caidos
  4) PowerShell:  docker start cass2 cass3   (espera a que los 3 esten en UN)
        docker exec cass1 nodetool repair aerolinea
        python python/pruebas_consistencia.py --verificar
        python python/pruebas_consistencia.py --resumen

Cada corrida agrega filas a resultados/consistencia.csv.
No se reintenta ninguna operacion (FallthroughRetryPolicy) para que el
resultado refleje exactamente lo que permite cada Consistency Level.
"""
import argparse
import csv
import os
import socket
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import (DCAwareRoundRobinPolicy, FallthroughRetryPolicy,
                                TokenAwarePolicy)

KEYSPACE = "aerolinea"
DC_LOCAL = "dc1"
HOSTS = os.environ.get("CASSANDRA_HOSTS", "cass1,cass2,cass3").split(",")
NIVELES = ["ONE", "QUORUM", "ALL"]
CSV_POR_DEFECTO = "resultados/consistencia.csv"
CAMPOS = ["fecha", "escenario", "cl", "operacion", "n", "exitos", "errores",
          "avg_ms", "p50_ms", "p95_ms", "tipos_error"]

DDL = ("CREATE TABLE IF NOT EXISTS pruebas_cl ("
       "escenario text, cl text, id uuid, valor text, ts timestamp, "
       "PRIMARY KEY ((escenario), cl, id))")


def hosts_vivos():
    """Docker solo resuelve el nombre de los contenedores que estan corriendo."""
    vivos = []
    for h in HOSTS:
        try:
            socket.gethostbyname(h)
            vivos.append(h)
        except OSError:
            print("  (aviso) %s no resuelve: se asume caido" % h)
    if not vivos:
        raise SystemExit("Ningun nodo responde. Estan corriendo los contenedores?")
    return vivos


def conectar():
    perfil = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=DC_LOCAL)),
        consistency_level=ConsistencyLevel.QUORUM,
        retry_policy=FallthroughRetryPolicy(),
        request_timeout=10)
    cluster = Cluster(hosts_vivos(), execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
    return cluster, cluster.connect(KEYSPACE)


def medir(fn, n):
    """Ejecuta fn() n veces; devuelve latencias de los exitos y conteo de errores."""
    tiempos, errores = [], Counter()
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            fn()
            tiempos.append((time.perf_counter() - t0) * 1000)
        except Exception as e:                       # noqa: BLE001
            errores[type(e).__name__] += 1
    return tiempos, errores


def fila_resultado(escenario, cl, operacion, n, tiempos, errores):
    tiempos = sorted(tiempos)
    pct = lambda p: tiempos[max(0, int(len(tiempos) * p) - 1)] if tiempos else ""
    return {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "escenario": escenario, "cl": cl, "operacion": operacion, "n": n,
        "exitos": len(tiempos), "errores": sum(errores.values()),
        "avg_ms": "%.2f" % statistics.mean(tiempos) if tiempos else "",
        "p50_ms": "%.2f" % pct(0.50) if tiempos else "",
        "p95_ms": "%.2f" % pct(0.95) if tiempos else "",
        "tipos_error": ";".join("%s=%d" % kv for kv in errores.items()),
    }


def guardar(csv_path, filas):
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    nuevo = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def leer_csv(csv_path):
    if not os.path.exists(csv_path):
        raise SystemExit("No existe %s. Corre primero un escenario." % csv_path)
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def correr_escenario(args):
    cluster, s = conectar()
    try:
        s.execute(DDL)
        ins = s.prepare("INSERT INTO pruebas_cl (escenario, cl, id, valor, ts) VALUES (?,?,?,?,?)")
        sel = s.prepare("SELECT fila, letra, nombre_pasajero, clase, estado_reserva, estado_pago "
                        "FROM manifiesto_por_vuelo WHERE codigo_vuelo = ?")
        print("Escenario: %s | %d operaciones por CL y tipo\n" % (args.escenario, args.n))
        resultados = []
        for nombre in NIVELES:
            cl = getattr(ConsistencyLevel, nombre)

            def escribir(cl=cl, nombre=nombre):
                b = ins.bind((args.escenario, nombre, uuid.uuid4(), "prueba",
                              datetime.now(timezone.utc)))
                b.consistency_level = cl
                s.execute(b)

            def leer(cl=cl):
                b = sel.bind((args.vuelo,))
                b.consistency_level = cl
                s.execute(b).all()

            for operacion, fn in (("lectura", leer), ("escritura", escribir)):
                tiempos, errores = medir(fn, args.n)
                fila = fila_resultado(args.escenario, nombre, operacion, args.n, tiempos, errores)
                resultados.append(fila)
                print("  %-6s %-9s exitos %3d/%d  avg %6s ms  p95 %6s ms  %s" % (
                    nombre, operacion, fila["exitos"], args.n, fila["avg_ms"] or "-",
                    fila["p95_ms"] or "-", fila["tipos_error"]))
        guardar(args.csv, resultados)
        print("\nGuardado en %s. Siguiente escenario, o --resumen al terminar." % args.csv)
    finally:
        cluster.shutdown()


def resumen(args):
    filas = leer_csv(args.csv)
    print("| Escenario | CL | Operacion | Exitos | % exito | Prom (ms) | p50 (ms) | p95 (ms) | Errores |")
    print("|---|---|---|---|---|---|---|---|---|")
    for f in filas:
        n, ok = int(f["n"]), int(f["exitos"])
        print("| %s | %s | %s | %d/%d | %.0f%% | %s | %s | %s | %s |" % (
            f["escenario"], f["cl"], f["operacion"], ok, n, 100.0 * ok / n,
            f["avg_ms"] or "-", f["p50_ms"] or "-", f["p95_ms"] or "-",
            f["tipos_error"] or "-"))


def verificar(args):
    """Tras recuperar los nodos: lee con ALL lo escrito durante cada escenario."""
    filas = leer_csv(args.csv)
    escritas = defaultdict(int)
    for f in filas:
        if f["operacion"] == "escritura":
            escritas[(f["escenario"], f["cl"])] += int(f["exitos"])
    cluster, s = conectar()
    try:
        cnt = s.prepare("SELECT COUNT(*) FROM pruebas_cl WHERE escenario = ? AND cl = ?")
        cnt.consistency_level = ConsistencyLevel.ALL
        print("Lectura con CL=ALL (requiere los 3 nodos arriba)\n")
        print("| Escenario | CL escritura | Escrituras exitosas | Filas leidas con ALL | Estado |")
        print("|---|---|---|---|---|")
        for (esc, cl), ok in sorted(escritas.items()):
            try:
                real = s.execute(cnt, (esc, cl)).one()[0]
                # >= porque una escritura con timeout puede haberse aplicado igual
                estado = "OK" if real >= ok else "FALTAN DATOS"
            except Exception as e:                   # noqa: BLE001
                real, estado = "-", "ERROR %s" % type(e).__name__
            print("| %s | %s | %d | %s | %s |" % (esc, cl, ok, real, estado))
    finally:
        cluster.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--escenario", help="etiqueta: 3_nodos | 1_nodo_caido | 2_nodos_caidos")
    ap.add_argument("--n", type=int, default=100, help="operaciones por CL y tipo")
    ap.add_argument("--vuelo", default="GT0476-20261204", help="vuelo para la lectura (Q3)")
    ap.add_argument("--csv", default=CSV_POR_DEFECTO)
    ap.add_argument("--resumen", action="store_true", help="imprime la tabla comparativa")
    ap.add_argument("--verificar", action="store_true", help="comprueba la recuperacion")
    args = ap.parse_args()

    if args.resumen:
        resumen(args)
    elif args.verificar:
        verificar(args)
    elif args.escenario:
        correr_escenario(args)
    else:
        ap.error("indica --escenario, --resumen o --verificar")


if __name__ == "__main__":
    main()
