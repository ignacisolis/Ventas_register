# Venta.py — Sistema de Gestión de Pedidos

Aplicación web construida con **Flask** para gestionar pedidos de un negocio de alimentos en tiempo real, desde cualquier dispositivo conectado a la misma red.

## ✨ Características

- **Seguimiento de pedidos multi-dispositivo en tiempo real**, sincronizado mediante *Server-Sent Events* (SSE), con indicador de conexión visible en la interfaz.
- **Ciclo de vida de pedidos en tres estados**: `por entregar` → `preparando` → `entregado`.
- **Ingreso de pedidos multi-producto**, con filas de formulario dinámicas y cálculo de totales en tiempo real.
- **Módulo de reservas**, con selector de horario, chips visuales de hora y theming propio.
- **Interfaz con tema oscuro**, tipografías Bebas Neue + DM Sans y estilos basados en CSS custom properties.
- Accesible desde cualquier dispositivo de la red local (`host='0.0.0.0'`).

## 🛠️ Stack técnico

- **Backend:** Python, Flask
- **Tiempo real:** Server-Sent Events (SSE)
- **Frontend:** HTML, CSS (custom properties), JavaScript
- **Estructura del proyecto:**
  ```
  venta.py
  templates/
    └── index.html
  ```

## 🚀 Instalación y uso

1. Clona el repositorio:
   ```bash
   git clone https://github.com/<tu-usuario>/<nombre-repo>.git
   cd <nombre-repo>
   ```
2. Instala las dependencias:
   ```bash
   pip install flask
   ```
3. Ejecuta la aplicación:
   ```bash
   python venta.py
   ```
4. Abre `http://localhost:5001` en tu navegador (o `http://<ip-de-tu-red>:5001` desde otro dispositivo de la misma red).

## 📋 Uso

- Desde la pantalla principal se pueden crear pedidos con múltiples productos, ver el total calculado automáticamente y hacer seguimiento de cada pedido a través de sus tres estados.
- La pestaña de reservas permite agendar horarios con un selector dedicado.
- Todos los dispositivos conectados ven las actualizaciones de pedidos en tiempo real gracias a SSE.

## 🗺️ Roadmap

- [ ] Selección de método de pago (efectivo / transferencia) con contadores financieros separados.
- [ ] Checkboxes de stock por producto.

## 📄 Licencia

Este proyecto es de uso personal / interno. Ajusta esta sección si decides publicarlo bajo una licencia abierta (MIT, GPL, etc.).
