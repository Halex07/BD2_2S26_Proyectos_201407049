#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
carga_masiva.py
---------------
Genera datos sinteticos y carga al menos 100,000 reservas en el keyspace
'aerolinea' de Cassandra usando Batch Writes.

Estrategia de escritura
  * Cada reserva se escribe en 3 o 4 tablas denormalizadas
    (reservas_por_id, pagos_por_reserva, historial_por_pasajero y, si la
    reserva no esta cancelada, manifiesto_por_vuelo) dentro de UN BATCH LOGGED.
    Asi las copias denormalizadas quedan consistentes entre si (atomicidad).
  * Los contadores (Q1, Q4, Q5) se acumulan en memoria y se aplican al final
    con BATCH COUNTER: son ~800 escrituras en lugar de 100,000 incrementos.
  * Las escrituras se paralelizan con execute_concurrent.

Uso (desde un contenedor en la red 'cassnet'):
    python python/carga_masiva.py --dry-run     # solo genera y valida en memoria
    python python/carga_masiva.py --truncate    # borra las tablas y carga todo

IMPORTANTE: los contadores no son idempotentes. Si vuelves a cargar sobre
datos existentes se duplican; usa --truncate para empezar de cero.
"""
import argparse
import os
import random
import time
import uuid
from collections import Counter, defaultdict, namedtuple
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import islice

from faker import Faker
from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.concurrent import execute_concurrent
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra.query import BatchStatement, BatchType, UNSET_VALUE

# ----------------------------- Configuracion ------------------------------
KEYSPACE = "aerolinea"
DC_LOCAL = "dc1"
HOSTS = os.environ.get("CASSANDRA_HOSTS", "cass1,cass2,cass3").split(",")
CONCURRENCIA = 128          # operaciones simultaneas en vuelo
TAMANO_BLOQUE = 2000        # operaciones que se arman en memoria a la vez

AHORA = datetime(2026, 9, 20, 12, 0, 0)     # fecha de referencia
INICIO_VUELOS = datetime(2026, 10, 1)       # vuelos entre oct-2026 y mar-2027

AEROPUERTOS = ["GUA", "MIA", "MEX", "PTY", "SAL", "SJO", "MAD", "LAX", "BOG", "JFK"]
AEROLINEAS = ["Aerolineas GT", "CentroAir", "Pacifico Air", "Istmo Jet"]
MODELOS = [("Embraer E190", 20), ("Airbus A319", 25), ("Airbus A320", 30)]  # (modelo, filas)
NACIONALIDADES = ["Guatemala", "Mexico", "El Salvador", "Honduras", "Costa Rica",
                  "Panama", "Espana", "Estados Unidos", "Colombia"]
METODOS_PAGO = ["tarjeta", "transferencia", "efectivo", "paypal"]
LETRAS = "ABCDEF"
NUM_AERONAVES = 12

# Rango de precios por clase, en quetzales/dolares (unidad monetaria abstracta)
PRECIOS = {"economica": (80, 350), "ejecutiva": (400, 900), "primera": (1200, 2500)}

TABLAS = [
    "pasajeros_por_id", "aeronaves_por_id", "vuelos_por_codigo",
    "asientos_por_vuelo", "reservas_por_id", "pagos_por_reserva",
    "asientos_contadores_por_vuelo", "historial_por_pasajero",
    "manifiesto_por_vuelo", "ocupacion_por_ruta_mes",
    "ingresos_por_vuelo", "top_vuelos_por_ingresos",
]

Reserva = namedtuple("Reserva", [
    "reserva_id", "pasajero", "vuelo", "fila", "letra", "clase",
    "fecha_reserva", "estado", "pago_id", "monto", "metodo",
    "fecha_pago", "estado_pago",
])


def clase_de_fila(fila):
    """Filas 1-2 primera clase, 3-6 ejecutiva, el resto economica."""
    if fila <= 2:
        return "primera"
    if fila <= 6:
        return "ejecutiva"
    return "economica"


# ----------------------------- Generacion ---------------------------------
def generar(n_reservas, n_vuelos, n_pasajeros):
    """Crea todos los datos en memoria y calcula los agregados de los contadores."""
    fake = Faker("es_ES")

    pasajeros = [
        (uuid.uuid4(), fake.name(), fake.email(),
         "".join(random.choices("0123456789", k=13)),          # DPI / pasaporte
         "+502" + "".join(random.choices("0123456789", k=8)),  # telefono como texto
         random.choice(NACIONALIDADES))
        for _ in range(n_pasajeros)
    ]

    aeronaves = []
    for i in range(NUM_AERONAVES):
        modelo, filas = random.choice(MODELOS)
        aeronaves.append({"id": uuid.uuid4(), "modelo": modelo,
                          "aerolinea": random.choice(AEROLINEAS),
                          "matricula": "TG-%03d" % i,
                          "filas": filas, "capacidad": filas * len(LETRAS)})

    vuelos = []
    for i in range(n_vuelos):
        nave = random.choice(aeronaves)
        origen, destino = random.sample(AEROPUERTOS, 2)
        salida = INICIO_VUELOS + timedelta(
            days=random.randint(0, 181), hours=random.randint(5, 22),
            minutes=random.choice((0, 15, 30, 45)))
        llegada = salida + timedelta(hours=random.randint(1, 6),
                                     minutes=random.choice((0, 30)))
        vuelos.append({
            "codigo": "GT%04d-%s" % (i, salida.strftime("%Y%m%d")),
            "aeronave_id": nave["id"], "filas": nave["filas"],
            "capacidad": nave["capacidad"],
            "origen": origen, "destino": destino, "ruta": "%s-%s" % (origen, destino),
            "salida": salida, "llegada": llegada, "mes": salida.strftime("%Y-%m"),
            "estado": "programado" if random.random() < 0.9 else "retrasado",
        })

    # Reservas por vuelo proporcionales a su capacidad (nunca sobreventa)
    cap_total = sum(v["capacidad"] for v in vuelos)
    if n_reservas > cap_total * 0.95:
        raise SystemExit("Pocos asientos (%d) para %d reservas: sube --vuelos." %
                         (cap_total, n_reservas))
    for v in vuelos:
        v["cuota"] = n_reservas * v["capacidad"] // cap_total
    for v in vuelos[: n_reservas - sum(v["cuota"] for v in vuelos)]:
        v["cuota"] += 1

    reservas = []
    for v in vuelos:
        asientos = [(f, l, clase_de_fila(f))
                    for f in range(1, v["filas"] + 1) for l in LETRAS]
        random.shuffle(asientos)
        v["totales"] = Counter(c for _, _, c in asientos)
        v["ocupados"] = defaultdict(int)      # asientos ocupados por clase (Q1)
        v["confirmadas"] = 0                  # reservas confirmadas (Q4)
        v["ingresos_cent"] = 0                # pagos 'pagado' en centavos (Q5)
        ocupado = {}                          # (fila, letra) -> reserva_id

        # Un pasajero no repite el mismo vuelo
        for k, idx in enumerate(random.sample(range(n_pasajeros), v["cuota"])):
            fila, letra, clase = asientos[k]
            r = random.random()
            if r < 0.80:
                estado, estado_pago = "confirmada", "pagado"
            elif r < 0.92:
                estado, estado_pago = "pendiente", "pendiente"
            else:
                estado, estado_pago = "cancelada", "reembolsado"

            lo, hi = PRECIOS[clase]
            centavos = random.randint(lo * 100, hi * 100)
            f_reserva = AHORA - timedelta(days=random.randint(0, 60),
                                          minutes=random.randint(0, 1439))
            f_pago = None if estado == "pendiente" else \
                f_reserva + timedelta(minutes=random.randint(1, 60))
            rid = uuid.uuid4()

            if estado != "cancelada":         # pendiente y confirmada retienen el asiento
                ocupado[(fila, letra)] = rid
                v["ocupados"][clase] += 1
            if estado == "confirmada":
                v["confirmadas"] += 1
                v["ingresos_cent"] += centavos

            reservas.append(Reserva(
                rid, pasajeros[idx], v, fila, letra, clase, f_reserva, estado,
                uuid.uuid4(), Decimal(centavos) / 100,
                random.choice(METODOS_PAGO), f_pago, estado_pago))

        # Estado final de cada asiento del vuelo
        v["asientos"] = [
            (f, l, c, "ocupado" if (f, l) in ocupado else "disponible",
             ocupado.get((f, l)))
            for f, l, c in asientos]

    return {"pasajeros": pasajeros, "aeronaves": aeronaves,
            "vuelos": vuelos, "reservas": reservas}


def resumen(datos):
    """Imprime estadisticas y verifica invariantes del negocio."""
    res, vuelos = datos["reservas"], datos["vuelos"]
    estados = Counter(r.estado for r in res)
    print("  Reservas:", len(res), dict(estados))
    print("  Vuelos: %d | asientos totales: %d" %
          (len(vuelos), sum(v["capacidad"] for v in vuelos)))
    print("  Ingresos confirmados: %.2f" % (sum(v["ingresos_cent"] for v in vuelos) / 100))
    print("  Vuelos por mes:", dict(sorted(Counter(v["mes"] for v in vuelos).items())))
    for v in vuelos:
        # Regla 4: sin sobreventa
        assert sum(v["ocupados"].values()) <= v["capacidad"]
        assert len(v["asientos"]) == v["capacidad"]
        # Regla 2: cada asiento tiene a lo sumo una reserva
        ids = [a[4] for a in v["asientos"] if a[4]]
        assert len(ids) == len(set(ids))
    print("  Invariantes OK (sin sobreventa, un asiento por reserva)")


# ------------------------------ Carga --------------------------------------
def conectar():
    perfil = ExecutionProfile(
        load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy(local_dc=DC_LOCAL)),
        consistency_level=ConsistencyLevel.QUORUM,
        request_timeout=60)
    cluster = Cluster(HOSTS, execution_profiles={EXEC_PROFILE_DEFAULT: perfil})
    return cluster, cluster.connect(KEYSPACE)


def ejecutar(session, operaciones, etiqueta):
    """Ejecuta (sentencia, parametros) en bloques con concurrencia y mide tiempo."""
    t0, n, it = time.perf_counter(), 0, iter(operaciones)
    while True:
        bloque = list(islice(it, TAMANO_BLOQUE))
        if not bloque:
            break
        execute_concurrent(session, bloque, concurrency=CONCURRENCIA,
                           raise_on_first_error=True)
        n += len(bloque)
        print("\r  %-28s %8d" % (etiqueta, n), end="", flush=True)
    dt = max(time.perf_counter() - t0, 1e-9)
    print("\r  %-28s %8d ops en %6.1fs (%.0f ops/s)" % (etiqueta, n, dt, n / dt))
    return dt


def preparar(session):
    p = session.prepare
    return {
        "pasajero": p("INSERT INTO pasajeros_por_id (pasajero_id, nombre, email, identificacion, telefono, nacionalidad) VALUES (?,?,?,?,?,?)"),
        "aeronave": p("INSERT INTO aeronaves_por_id (aeronave_id, modelo, aerolinea, matricula, capacidad_max) VALUES (?,?,?,?,?)"),
        "vuelo": p("INSERT INTO vuelos_por_codigo (codigo_vuelo, aeronave_id, origen, destino, ruta, fecha_salida, fecha_llegada, estado, capacidad) VALUES (?,?,?,?,?,?,?,?,?)"),
        "asiento": p("INSERT INTO asientos_por_vuelo (codigo_vuelo, fila, letra, clase, estado, reserva_id) VALUES (?,?,?,?,?,?)"),
        "reserva": p("INSERT INTO reservas_por_id (reserva_id, pasajero_id, codigo_vuelo, fila, letra, clase, fecha_reserva, estado) VALUES (?,?,?,?,?,?,?,?)"),
        "pago": p("INSERT INTO pagos_por_reserva (reserva_id, pago_id, monto, metodo, fecha_pago, estado) VALUES (?,?,?,?,?,?)"),
        "hist": p("INSERT INTO historial_por_pasajero (pasajero_id, fecha_salida, reserva_id, codigo_vuelo, origen, destino, fila, letra, clase, fecha_reserva, estado_reserva, monto, estado_pago) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"),
        "manif": p("INSERT INTO manifiesto_por_vuelo (codigo_vuelo, fila, letra, reserva_id, pasajero_id, nombre_pasajero, identificacion, clase, estado_reserva, estado_pago) VALUES (?,?,?,?,?,?,?,?,?,?)"),
        "q1": p("UPDATE asientos_contadores_por_vuelo SET disponibles = disponibles + ?, ocupados = ocupados + ? WHERE codigo_vuelo = ? AND clase = ?"),
        "q4": p("UPDATE ocupacion_por_ruta_mes SET confirmadas = confirmadas + ? WHERE ruta = ? AND mes = ? AND fecha_salida = ? AND codigo_vuelo = ? AND capacidad = ?"),
        "q5c": p("UPDATE ingresos_por_vuelo SET total_centavos = total_centavos + ? WHERE codigo_vuelo = ?"),
        "q5": p("INSERT INTO top_vuelos_por_ingresos (periodo, total_centavos, codigo_vuelo, ruta) VALUES (?,?,?,?)"),
    }


def ops_entidades(datos, ps):
    for a in datos["aeronaves"]:
        yield ps["aeronave"], (a["id"], a["modelo"], a["aerolinea"], a["matricula"], a["capacidad"])
    for p in datos["pasajeros"]:
        yield ps["pasajero"], p
    for v in datos["vuelos"]:
        yield ps["vuelo"], (v["codigo"], v["aeronave_id"], v["origen"], v["destino"],
                            v["ruta"], v["salida"], v["llegada"], v["estado"], v["capacidad"])
        for fila, letra, clase, estado, rid in v["asientos"]:
            yield ps["asiento"], (v["codigo"], fila, letra, clase, estado,
                                  rid if rid else UNSET_VALUE)


def ops_reservas(datos, ps):
    """Un BATCH LOGGED por reserva: mantiene consistentes las tablas denormalizadas."""
    for r in datos["reservas"]:
        v = r.vuelo
        pid, nombre, _, ident, _, _ = r.pasajero
        b = BatchStatement(batch_type=BatchType.LOGGED)
        b.add(ps["reserva"], (r.reserva_id, pid, v["codigo"], r.fila, r.letra,
                              r.clase, r.fecha_reserva, r.estado))
        b.add(ps["pago"], (r.reserva_id, r.pago_id, r.monto, r.metodo,
                           r.fecha_pago or UNSET_VALUE, r.estado_pago))
        b.add(ps["hist"], (pid, v["salida"], r.reserva_id, v["codigo"], v["origen"],
                           v["destino"], r.fila, r.letra, r.clase, r.fecha_reserva,
                           r.estado, r.monto, r.estado_pago))
        if r.estado != "cancelada":           # una reserva cancelada libera el asiento
            b.add(ps["manif"], (v["codigo"], r.fila, r.letra, r.reserva_id, pid,
                                nombre, ident, r.clase, r.estado, r.estado_pago))
        yield b, None


def ops_contadores(datos, ps):
    """Aplica los contadores ya acumulados en memoria (BATCH COUNTER por vuelo)."""
    for v in datos["vuelos"]:
        b = BatchStatement(batch_type=BatchType.COUNTER)
        for clase, total in v["totales"].items():
            ocu = v["ocupados"].get(clase, 0)
            b.add(ps["q1"], (total - ocu, ocu, v["codigo"], clase))      # Q1
        yield b, None
        yield ps["q4"], (v["confirmadas"], v["ruta"], v["mes"], v["salida"],
                         v["codigo"], v["capacidad"])                    # Q4
        yield ps["q5c"], (v["ingresos_cent"], v["codigo"])               # Q5 (acumulado)


def ops_top(datos, ps):
    for v in datos["vuelos"]:
        if v["ingresos_cent"] > 0:
            yield ps["q5"], (v["mes"], v["ingresos_cent"], v["codigo"], v["ruta"])


def validar(session, datos):
    """Compara lo cargado contra lo esperado y revisa los contadores."""
    res, vuelos = datos["reservas"], datos["vuelos"]
    esperado = {
        "pasajeros_por_id": len(datos["pasajeros"]),
        "vuelos_por_codigo": len(vuelos),
        "asientos_por_vuelo": sum(v["capacidad"] for v in vuelos),
        "reservas_por_id": len(res),
        "pagos_por_reserva": len(res),
        "historial_por_pasajero": len(res),
        "manifiesto_por_vuelo": sum(1 for r in res if r.estado != "cancelada"),
    }
    ok = True
    for tabla, esp in esperado.items():
        real = session.execute("SELECT COUNT(*) FROM %s" % tabla, timeout=600).one()[0]
        marca = "OK " if real == esp else "ERR"
        ok &= real == esp
        print("  [%s] %-26s esperado=%-7d real=%d" % (marca, tabla, esp, real))

    for v in random.sample(vuelos, min(10, len(vuelos))):
        filas = session.execute(
            "SELECT ocupados FROM asientos_contadores_por_vuelo WHERE codigo_vuelo=%s",
            (v["codigo"],)).all()
        contador = sum(f.ocupados for f in filas)
        real = session.execute(
            "SELECT COUNT(*) FROM manifiesto_por_vuelo WHERE codigo_vuelo=%s",
            (v["codigo"],)).one()[0]
        marca = "OK " if contador == real else "ERR"
        ok &= contador == real
        print("  [%s] contador ocupados %s = %d vs manifiesto = %d" %
              (marca, v["codigo"], contador, real))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reservas", type=int, default=100_000)
    ap.add_argument("--vuelos", type=int, default=800)
    ap.add_argument("--pasajeros", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=42, help="semilla (datos reproducibles)")
    ap.add_argument("--truncate", action="store_true", help="vacia las tablas antes de cargar")
    ap.add_argument("--dry-run", action="store_true", help="genera y valida sin tocar Cassandra")
    args = ap.parse_args()

    random.seed(args.seed)
    Faker.seed(args.seed)

    print("1) Generando datos en memoria...")
    t0 = time.perf_counter()
    datos = generar(args.reservas, args.vuelos, args.pasajeros)
    print("   listo en %.1fs" % (time.perf_counter() - t0))
    resumen(datos)
    if args.dry_run:
        return

    cluster, session = conectar()
    try:
        if args.truncate:
            print("2) Vaciando tablas...")
            for t in TABLAS:
                session.execute("TRUNCATE %s" % t, timeout=120)
        ps = preparar(session)

        print("3) Cargando entidades base...")
        ejecutar(session, ops_entidades(datos, ps), "entidades")
        print("4) Cargando reservas con BATCH LOGGED (1 batch por reserva)...")
        dt = ejecutar(session, ops_reservas(datos, ps), "reservas (batches)")
        print("   >> %.0f reservas/s" % (len(datos["reservas"]) / dt))
        print("5) Aplicando contadores (BATCH COUNTER)...")
        ejecutar(session, ops_contadores(datos, ps), "contadores")
        ejecutar(session, ops_top(datos, ps), "top ingresos")

        print("6) Validando integridad...")
        print("\nRESULTADO:", "TODO OK" if validar(session, datos) else "HAY DIFERENCIAS")
        print("\nSiguiente: docker exec cass1 nodetool status aerolinea  (distribucion entre nodos)")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
