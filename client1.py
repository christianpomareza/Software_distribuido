import sys
import json
import uuid # Para generar IDs de cliente únicos
import os   # Para leer variables de entorno si se quisiera un servidor por defecto

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Importar el cliente de Socket.IO
import socketio

# --- Clase principal de la Aplicación Cliente ---
class ClientApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cliente de Sistema Distribuido (Socket.IO)")
        self.setGeometry(100, 100, 800, 600)

        self.sio = socketio.Client() # Instancia del cliente Socket.IO
        self.client_id = f"Cliente-{uuid.uuid4().hex[:4]}" # ID único para este cliente
        self.connected_to_server = False

        # --- Conexión predeterminada ---
        # Para pruebas locales:
        self.default_server_url = "http://127.0.0.1:5000"
        # Para pruebas en la nube (¡REEMPLAZAR CON LA URL REAL DE TU APP EN HEROKU!):
        # self.default_server_url = "https://tu-nombre-de-app-unico.herokuapp.com"


        self.setup_ui()
        self.setup_socketio_events()

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # Configuración de Conexión
        connection_layout = QHBoxLayout()
        self.server_url_label = QLabel("URL del Servidor:")
        self.server_url_entry = QLineEdit(self.default_server_url) # Usar URL por defecto
        self.connect_button = QPushButton("Conectar")
        self.disconnect_button = QPushButton("Desconectar")

        connection_layout.addWidget(self.server_url_label)
        connection_layout.addWidget(self.server_url_entry)
        connection_layout.addWidget(self.connect_button)
        connection_layout.addWidget(self.disconnect_button)
        main_layout.addLayout(connection_layout)

        # Área de Chat
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        main_layout.addWidget(self.chat_display)

        # Entrada de Mensajes
        message_layout = QHBoxLayout()
        self.message_entry = QLineEdit()
        self.message_entry.setPlaceholderText("Escribe tu comando (ej: agregar leche) o mensaje...")
        self.send_button = QPushButton("Enviar")

        message_layout.addWidget(self.message_entry)
        message_layout.addWidget(self.send_button)
        main_layout.addLayout(message_layout)

        self.setLayout(main_layout)

        # Conectar señales y slots
        self.connect_button.clicked.connect(self.connect_to_server)
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        self.send_button.clicked.connect(self.send_message)
        self.message_entry.returnPressed.connect(self.send_message) # Enviar con Enter

        # Estado inicial de botones
        self.update_ui_state(False)

    def setup_socketio_events(self):
        # Evento de conexión exitosa
        @self.sio.event
        def connect():
            self.write_to_chat(f"Conectado al servidor Socket.IO en {self.server_url_entry.text()}\\n")
            self.connected_to_server = True
            self.update_ui_state(True)
            # Emitir un evento para que el servidor sepa que un nuevo cliente está listo
            self.sio.emit('client_ready', {'id': self.client_id})

        # Evento de desconexión
        @self.sio.event
        def disconnect():
            self.write_to_chat("Desconectado del servidor Socket.IO.\\n")
            self.connected_to_server = False
            self.update_ui_state(False)

        # Evento para recibir mensajes de respuesta específicos del servidor
        @self.sio.event
        def receive_message(data):
            response = data.get('response', 'Mensaje vacío')
            items = data.get('items', [])
            self.write_to_chat(f"--> [Servidor]: {response}\\n")
            self.write_to_chat(f"    Estado actual de ítems: {items}\\n")

        # Evento para recibir actualizaciones de ítems (broadcast a todos los clientes)
        @self.sio.event
        def update_items(data):
            items = data.get('items', [])
            self.write_to_chat(f"    [ACTUALIZACIÓN GLOBAL DE ITEMS]: {items}\\n")

        # Manejo de errores de conexión
        @self.sio.event
        def connect_error(data):
            self.write_to_chat(f"Error de conexión a Socket.IO: {data}\\n")
            self.connected_to_server = False
            self.update_ui_state(False)
            QMessageBox.critical(self, "Error de Conexión", f"No se pudo conectar al servidor:\n{data}")

    def write_to_chat(self, text):
        self.chat_display.append(text)

    def update_ui_state(self, is_connected):
        self.connect_button.setEnabled(not is_connected)
        self.disconnect_button.setEnabled(is_connected)
        self.server_url_entry.setEnabled(not is_connected)
        self.message_entry.setEnabled(is_connected)
        self.send_button.setEnabled(is_connected)

    def connect_to_server(self):
        if self.connected_to_server:
            QMessageBox.information(self, "Ya Conectado", "Ya estás conectado al servidor.")
            return

        server_url = self.server_url_entry.text().strip()
        if not server_url:
            QMessageBox.warning(self, "URL Vacía", "Por favor, introduce la URL del servidor.")
            return

        try:
            self.write_to_chat(f"Intentando conectar a: {server_url}\\n")
            # Conecta el cliente Socket.IO
            self.sio.connect(server_url)
            # La conexión exitosa o el error se manejarán en los eventos @self.sio.event
        except Exception as e:
            self.write_to_chat(f"Error al iniciar conexión: {e}\\n")
            self.connected_to_server = False
            self.update_ui_state(False)
            QMessageBox.critical(self, "Error de Conexión", f"No se pudo iniciar la conexión:\n{e}")

    def disconnect_from_server(self):
        if self.connected_to_server:
            self.sio.disconnect()
        else:
            QMessageBox.information(self, "Desconectado", "No estás conectado al servidor.")

    def send_message(self):
        if not self.connected_to_server:
            QMessageBox.warning(self, "No Conectado", "Por favor, conéctate al servidor primero.")
            return

        user_input = self.message_entry.text().strip()
        if not user_input:
            return

        self.write_to_chat(f"[{self.client_id}]: {user_input}\\n")
        self.message_entry.clear()

        try:
            # Emitir el mensaje al servidor usando el evento 'send_message'
            self.sio.emit('send_message', {'message': user_input, 'client_id': self.client_id})
        except Exception as e:
            self.write_to_chat(f"Error al emitir mensaje Socket.IO: {e}\\n")
            QMessageBox.critical(self, "Error de Envío", f"Hubo un error al enviar el mensaje:\n{e}")


# --- Punto de Entrada de la Aplicación ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    client_app = ClientApp()
    client_app.show()
    sys.exit(app.exec())