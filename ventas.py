from flask import Flask, render_template, request, redirect, url_for, Response
from datetime import datetime
import json
import queue
import threading
import os

app = Flask(__name__)

PRECIOS = {
    "consome": 1000,
    "papas fritas": 2000,
    "salchipapas": 3000,
    "sopaipillas": 300
}

DATA_FILE = "data.json"

# ── Persistencia ──────────────────────────────────────────────
def cargar_datos():
    """Lee data.json y devuelve pedidos, reservas, stock y contador."""
    if not os.path.exists(DATA_FILE):
        return [], [], {prod: True for prod in PRECIOS}, 1
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        pedidos   = d.get("pedidos", [])
        reservas  = d.get("reservas", [])
        stock     = d.get("stock", {prod: True for prod in PRECIOS})
        # Asegura que existan todos los productos en stock (por si se agregó uno nuevo)
        for prod in PRECIOS:
            stock.setdefault(prod, True)
        contador  = d.get("contador", 1)
        return pedidos, reservas, stock, contador
    except (json.JSONDecodeError, KeyError):
        return [], [], {prod: True for prod in PRECIOS}, 1

def guardar_datos():
    """Escribe el estado actual en data.json de forma atómica."""
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({
            "pedidos":  pedidos,
            "reservas": reservas,
            "stock":    stock,
            "contador": contador,
            "ultima_actualizacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)   # reemplazo atómico: evita corrupción si el proceso muere a mitad

# Carga inicial
pedidos, reservas, stock, contador = cargar_datos()

listeners      = []
listeners_lock = threading.Lock()

# ── Payload SSE ───────────────────────────────────────────────
def payload():
    return json.dumps({
        "pedidos": pedidos,
        "reservas": reservas,
        "total_pedidos": len(pedidos),
        "pendientes": sum(1 for p in pedidos if p["estado"] == "por entregar"),
        "recaudado": sum(p["total"] for p in pedidos) + sum(r["total"] for r in reservas),
        "recaudado_efectivo": (
            sum(p["total"] for p in pedidos if p.get("metodo_pago") == "efectivo") +
            sum(r["total"] for r in reservas if r.get("metodo_pago") == "efectivo")
        ),
        "recaudado_transferencia": (
            sum(p["total"] for p in pedidos if p.get("metodo_pago") == "transferencia") +
            sum(r["total"] for r in reservas if r.get("metodo_pago") == "transferencia")
        ),
        "total_reservas": len(reservas),
        "reservas_pendientes": sum(1 for r in reservas if r["estado"] == "por entregar"),
        "stock": stock
    })

def notificar_clientes():
    msg = f"data: {payload()}\n\n"
    with listeners_lock:
        for q in listeners:
            q.put(msg)

def parse_productos(form):
    productos_sel  = form.getlist("producto[]")
    cantidades_sel = form.getlist("cantidad[]")
    items, total = [], 0
    for prod, cant_str in zip(productos_sel, cantidades_sel):
        try: cant = int(cant_str)
        except ValueError: cant = 0
        if prod in PRECIOS and cant > 0:
            subtotal = PRECIOS[prod] * cant
            items.append({"producto": prod, "cantidad": cant,
                          "precio_unitario": PRECIOS[prod], "subtotal": subtotal})
            total += subtotal
    return items, total

# ── Rutas ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", pedidos=pedidos, reservas=reservas, precios=PRECIOS, stock=stock)

@app.route("/stream")
def stream():
    def event_stream(q):
        yield f"data: {payload()}\n\n"
        while True:
            try:
                yield q.get(timeout=30)
            except queue.Empty:
                yield ": ping\n\n"

    q = queue.Queue()
    with listeners_lock:
        listeners.append(q)

    def generator():
        try:
            yield from event_stream(q)
        finally:
            with listeners_lock:
                if q in listeners:
                    listeners.remove(q)

    return Response(generator(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ── Pedidos normales ──────────────────────────────────────────
@app.route("/agregar", methods=["POST"])
def agregar():
    global contador
    nombre      = request.form.get("nombre", "").strip()
    metodo_pago = request.form.get("metodo_pago", "efectivo")
    if not nombre:
        return redirect(url_for("index"))
    items, total = parse_productos(request.form)
    if items:
        pedidos.append({
            "id": contador, "nombre": nombre, "productos": items,
            "total": total, "estado": "por entregar",
            "hora": datetime.now().strftime("%H:%M"),
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "metodo_pago": metodo_pago
        })
        contador += 1
        guardar_datos()
        notificar_clientes()
    return redirect(url_for("index"))

@app.route("/toggle/<int:pedido_id>", methods=["POST"])
def toggle_estado(pedido_id):
    ciclo = {"por entregar": "preparando", "preparando": "entregado", "entregado": "por entregar"}
    for p in pedidos:
        if p["id"] == pedido_id:
            p["estado"] = ciclo.get(p["estado"], "por entregar")
            break
    guardar_datos()
    notificar_clientes()
    return redirect(url_for("index"))

@app.route("/eliminar/<int:pedido_id>", methods=["POST"])
def eliminar(pedido_id):
    global pedidos
    pedidos = [p for p in pedidos if p["id"] != pedido_id]
    guardar_datos()
    notificar_clientes()
    return redirect(url_for("index"))

# ── Reservas ──────────────────────────────────────────────────
@app.route("/reservas/agregar", methods=["POST"])
def agregar_reserva():
    global contador
    nombre       = request.form.get("nombre", "").strip()
    hora_reserva = request.form.get("hora_reserva", "").strip()
    metodo_pago  = request.form.get("metodo_pago", "efectivo")
    if not nombre or not hora_reserva:
        return redirect(url_for("index") + "#reservas")
    items, total = parse_productos(request.form)
    if items:
        reservas.append({
            "id": contador, "nombre": nombre, "productos": items,
            "total": total, "estado": "por entregar",
            "hora_registro": datetime.now().strftime("%H:%M"),
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "hora_reserva": hora_reserva,
            "metodo_pago": metodo_pago
        })
        contador += 1
        guardar_datos()
        notificar_clientes()
    return redirect(url_for("index") + "#reservas")

@app.route("/reservas/toggle/<int:res_id>", methods=["POST"])
def toggle_reserva(res_id):
    ciclo = {"por entregar": "preparando", "preparando": "entregado", "entregado": "por entregar"}
    for r in reservas:
        if r["id"] == res_id:
            r["estado"] = ciclo.get(r["estado"], "por entregar")
            break
    guardar_datos()
    notificar_clientes()
    return redirect(url_for("index") + "#reservas")

@app.route("/reservas/eliminar/<int:res_id>", methods=["POST"])
def eliminar_reserva(res_id):
    global reservas
    reservas = [r for r in reservas if r["id"] != res_id]
    guardar_datos()
    notificar_clientes()
    return redirect(url_for("index") + "#reservas")

# ── Stock ─────────────────────────────────────────────────────
@app.route("/stock/actualizar", methods=["POST"])
def actualizar_stock():
    for prod in PRECIOS:
        stock[prod] = request.form.get(f"stock_{prod}") == "1"
    guardar_datos()
    notificar_clientes()
    return redirect(url_for("index"))

# ── Exportar a Excel (bonus) ──────────────────────────────────
@app.route("/exportar")
def exportar():
    try:
        import pandas as pd
        from flask import send_file
        import io

        filas_pedidos = []
        for p in pedidos:
            for item in p["productos"]:
                filas_pedidos.append({
                    "ID": p["id"], "Tipo": "Pedido",
                    "Cliente": p["nombre"], "Fecha": p.get("fecha", ""),
                    "Hora": p["hora"], "Producto": item["producto"],
                    "Cantidad": item["cantidad"], "Precio Unit.": item["precio_unitario"],
                    "Subtotal": item["subtotal"], "Total Pedido": p["total"],
                    "Método Pago": p.get("metodo_pago", ""), "Estado": p["estado"]
                })

        filas_reservas = []
        for r in reservas:
            for item in r["productos"]:
                filas_reservas.append({
                    "ID": r["id"], "Tipo": "Reserva",
                    "Cliente": r["nombre"], "Fecha": r.get("fecha", ""),
                    "Hora Registro": r["hora_registro"], "Hora Reserva": r["hora_reserva"],
                    "Producto": item["producto"], "Cantidad": item["cantidad"],
                    "Precio Unit.": item["precio_unitario"], "Subtotal": item["subtotal"],
                    "Total Reserva": r["total"], "Método Pago": r.get("metodo_pago", ""),
                    "Estado": r["estado"]
                })

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_p = pd.DataFrame(filas_pedidos)
            df_r = pd.DataFrame(filas_reservas)
            df_p.to_excel(writer, sheet_name="Pedidos",  index=False)
            df_r.to_excel(writer, sheet_name="Reservas", index=False)
        buf.seek(0)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        return send_file(buf, as_attachment=True,
                         download_name=f"ventas_{fecha_hoy}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ImportError:
        return "Instala pandas y openpyxl: pip install pandas openpyxl", 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001, threaded=True)
