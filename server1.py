import threading
import datetime
import json
import os # Importar os para acceder a variables de entorno

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit

# --- Configuración de Flask ---
app = Flask(__name__)
# Configuración para Flask-SocketIO
# Permite conexiones desde cualquier origen (*) para desarrollo.
# En producción, considera especificar dominios específicos por seguridad.
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Estado Compartido del Servidor ---
shared_items = []
items_lock = threading.Lock() # Mecanismo para asegurar la concurrencia

# --- Funciones de Lógica de Negocio (Core del Microservicio) ---
def process_conversational_message(message_text):
    message_text_lower = message_text.lower().strip()
    response_message = "No entiendo tu solicitud. Puedes intentar 'agregar', 'listar' o 'eliminar' seguido de un ítem."
    action_performed = None
    current_items_state = None # Para retornar el estado actual de los ítems

    with items_lock: # Bloqueo para asegurar acceso exclusivo a shared_items
        if "hola" in message_text_lower or "saludo" in message_text_lower:
            response_message = "¡Hola! Soy un servidor de gestión de ítems. ¿En qué puedo ayudarte hoy?"
        elif "cómo estás" in message_text_lower or "que tal" in message_text_lower:
            response_message = "Soy un programa, así que estoy funcionando perfectamente. ¿Y tú?"
        elif "agregar" in message_text_lower:
            item = message_text_lower.replace("agregar", "").strip()
            if item:
                shared_items.append(item)
                response_message = f"Ítem '{item}' agregado. Total: {len(shared_items)}."
                action_performed = "add"
            else:
                response_message = "Por favor, especifica qué quieres agregar."
        elif "listar" in message_text_lower or "mostrar" in message_text_lower:
            if shared_items:
                response_message = "Los ítems actuales son: " + ", ".join(shared_items) + "."
            else:
                response_message = "No hay ítems en la lista."
            action_performed = "list"
        elif "eliminar" in message_text_lower or "quitar" in message_text_lower:
            item_to_remove = message_text_lower.replace("eliminar", "").replace("quitar", "").strip()
            if item_to_remove in shared_items:
                shared_items.remove(item_to_remove)
                response_message = f"Ítem '{item_to_remove}' eliminado."
                action_performed = "remove"
            else:
                response_message = f"El ítem '{item_to_remove}' no se encuentra en la lista."
        elif "vaciar" in message_text_lower or "limpiar" in message_text_lower:
            if shared_items:
                shared_items.clear()
                response_message = "La lista de ítems ha sido vaciada."
                action_performed = "clear"
            else:
                response_message = "La lista ya está vacía."
        elif "gracias" in message_text_lower or "adios" in message_text_lower:
            response_message = "De nada. ¡Hasta luego!"
        
        current_items_state = list(shared_items) # Obtener una copia del estado actual

    return {
        "message": response_message,
        "action": action_performed,
        "current_items": current_items_state # Devolver el estado actual
    }

# --- Rutas HTTP (Opcional, para un REST API simple si se necesitara, o para servir el HTML) ---
@app.route('/')
def index():
    # Sirve el cliente web HTML. Asegúrate de que client_web_app.html esté en una carpeta 'templates'
    # dentro del mismo directorio que server1.py, o modifica la ruta.
    return render_template('client_web_app.html')

# --- Manejadores de Eventos de SocketIO (para comunicación en tiempo real) ---

# Evento que se dispara cuando un cliente SocketIO se conecta
@socketio.on('connect')
def test_connect():
    print("Cliente SocketIO conectado.")
    # Emitir el estado actual de los ítems al nuevo cliente conectado
    with items_lock:
        emit('update_items', {'items': list(shared_items)})

# Evento que se dispara cuando un cliente SocketIO se desconecta
@socketio.on('disconnect')
def test_disconnect():
    print("Cliente SocketIO desconectado.")

# Evento para manejar mensajes enviados desde los clientes de SocketIO
@socketio.on('send_message')
def handle_socketio_message(data):
    user_message = data.get('message', '')
    if not user_message:
        return

    print(f"[Cliente SocketIO] Mensaje recibido: '{user_message}'")
    response_data = process_conversational_message(user_message)

    # Enviar la respuesta específica al cliente que envió el mensaje.
    emit('receive_message', {'response': response_data['message'], 'items': response_data['current_items']})

    # Si la lista de ítems cambió, notificar a TODOS los clientes (broadcast).
    # Esto es fundamental para la sincronización y consistencia global.
    if response_data.get("current_items") is not None:
        # CORRECCIÓN: Usar response_data en lugar de response_items
        socketio.emit('update_items', {'items': response_data['current_items']})

# --- Inicio del Servidor Flask (preparado para SaaS) ---
if __name__ == '__main__':
    # Obtener el puerto de las variables de entorno (fundamental para despliegue en la nube, ej. Heroku).
    # Si la variable PORT no está definida (como en desarrollo local), usa el puerto 5000.
    port = int(os.environ.get("PORT", 5000))

    # Para que Flask/SocketIO sea accesible desde otras máquinas y en Heroku, usa host='0.0.0.0'.
    # Usamos socketio.run() en lugar de app.run() porque estamos usando Flask-SocketIO.
    print(f"Servidor SocketIO iniciado en http://0.0.0.0:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=True)