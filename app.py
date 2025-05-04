from flask import Flask, request, render_template, jsonify
from pdfminer.high_level import extract_text
import re
import io

app = Flask(__name__)

# Dirección fija para cuando la cancha es LOCAL
DIRECCION_LOCAL = "Complejo Arena, Monte Grande"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'pdfFile' not in request.files:
        return jsonify({"error": "No se encontró el archivo PDF"}), 400

    file = request.files['pdfFile']

    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    if file and file.filename.endswith('.pdf'):
        try:
            # --- Leer el contenido del PDF desde la memoria (SOLO UNA VEZ) ---
            # Usamos io.BytesIO porque pdfminer.six necesita un objeto tipo archivo
            file_stream = io.BytesIO(file.read())

            # --- Extracción de texto y depuración ---
            # Extrae todo el texto del PDF
            text = extract_text(file_stream)

            # Línea para imprimir el texto extraído en la terminal (para depuración)
            print("\n--- Texto extraído del PDF ---\n")
            print(text)
            print("\n--- Fin del texto extraído ---\n")
            # --- Fin de extracción de texto ---


            # --- Lógica de Extracción de Información ---

            data = {}

            # 1. Fecha: Buscar al final del texto
            lines = text.strip().split('\n')
            non_empty_lines = [line.strip() for line in lines if line.strip()]
            data['fecha'] = "Fecha no encontrada" # Valor por defecto
            if non_empty_lines:
                # Buscar la última línea que contenga "SÁBADO" o "DOMINGO" y un formato de fecha DD/MM/YYYY
                fecha_pattern = re.compile(r'(SÁBADO|DOMINGO)\s+\d{2}/\d{2}/\d{4}', re.IGNORECASE)
                for line in reversed(non_empty_lines):
                    match = fecha_pattern.search(line)
                    if match:
                        data['fecha'] = match.group(0)
                        break # Salimos una vez que encontramos la última fecha

            # 2. Cancha: Buscar "SOMOS LOCALES" o "SOMOS VISITANTES"
            if "SOMOS LOCALES" in text:
                data['cancha'] = "LOCALES"
            elif "SOMOS VISITANTES" in text:
                data['cancha'] = "VISITANTES"
            else:
                data['cancha'] = "Cancha no especificada"

            # 3. Vs: Buscar "VS" seguido del nombre entre comillas
            vs_match = re.search(r'VS\s+"([^"]+)"', text)
            if vs_match:
                data['vs'] = vs_match.group(1)
            else:
                data['vs'] = "Rival no encontrado"

            # 4. Dirección: Buscar "DIRECCIÓN:"
            if data['cancha'] == "LOCALES":
                data['direccion'] = DIRECCION_LOCAL
            else:
                # Buscar la etiqueta "DIRECCIÓN:" y capturar el texto que le sigue
                direccion_match = re.search(r'DIRECCIÓN:\s*(.*)', text)
                if direccion_match:
                    # Tomar el texto capturado después de "DIRECCIÓN:", limpiar espacios
                    direccion_texto = direccion_match.group(1).strip()
                    # Considerar si la dirección pudiera extenderse a la siguiente línea
                    # (la lógica actual busca solo en la línea del "DIRECCIÓN:").
                    # Si necesitas que abarque múltiples líneas, la lógica sería más compleja,
                    # implicando buscar la siguiente línea no vacía si la actual es corta.
                    # Para los PDFs de ejemplo, capturar el resto de la línea parece funcionar.
                    data['direccion'] = direccion_texto if direccion_texto else "Dirección no encontrada en PDF"
                else:
                    data['direccion'] = "Dirección no encontrada"

            # 5. Entrada: Buscar "VALOR DE LA ENTRADA:"
            entrada_match = re.search(r'VALOR DE LA ENTRADA:\s*\$?(\d+)', text)
            if entrada_match:
                data['entrada'] = entrada_match.group(1) # Captura solo el número sin el $
            else:
                data['entrada'] = "Valor no encontrado"

# 6. Hora: Buscar en la tabla la categoría "2013" y su horario
            hora_encontrada = "Hora no encontrada"

            # Dividimos el texto en líneas para analizar la tabla de horarios
            lines = text.split('\n')

            # Patrones
            category_pattern = re.compile(r'2013|2012-2013|2013\s*-', re.IGNORECASE) # Busca "2013" o variantes de categoría
            time_pattern = re.compile(r'(\d{2}:\d{2}\s*HS)', re.IGNORECASE) # Busca HH:MM HS
            category_line_pattern = re.compile(r'^\s*\d{4}', re.IGNORECASE) # Busca líneas que probablemente son categorías (empiezan con 4 dígitos)
            time_line_pattern = re.compile(r'^\s*\d{2}:\d{2}\s*HS', re.IGNORECASE) # Busca líneas que probablemente son horarios (empiezan con HH:MM HS)


            category_lines = []
            time_lines = []
            is_in_category_block = False
            is_in_time_block = False

            # Intentar encontrar los bloques de líneas de Categorías y Horarios
            for line in lines:
                stripped_line = line.strip()

                # Lógica para identificar si estamos en un bloque de categorías o horarios
                # Esto es heurístico y puede fallar si el formato cambia mucho
                if category_line_pattern.search(stripped_line):
                    is_in_category_block = True
                    is_in_time_block = False # No puede ser ambos a la vez
                    category_lines.append(stripped_line)
                elif time_line_pattern.search(stripped_line):
                     is_in_time_block = True
                     is_in_category_block = False # No puede ser ambos a la vez
                     time_lines.append(stripped_line)
                elif stripped_line == "CATEGORIAS": # Si encontramos el encabezado
                     is_in_category_block = True
                     is_in_time_block = False
                elif stripped_line == "HORARIOS": # Si encontramos el encabezado
                     is_in_time_block = True
                     is_in_category_block = False
                elif not stripped_line and (is_in_category_block or is_in_time_block):
                    # Línea vacía dentro de un bloque, puede ser un separador, seguir en el bloque
                    pass
                else:
                    # Si la línea no parece una categoría, horario o encabezado, y no es vacía, salimos de los bloques
                    if is_in_category_block or is_in_time_block:
                         # Si estábamos en un bloque y encontramos otra cosa, asumimos que el bloque terminó
                         is_in_category_block = False
                         is_in_time_block = False


            # Ahora que tenemos las líneas que parecen categorías y horarios,
            # buscamos la posición de nuestra categoría 2013
            category_2013_index = -1
            for i, cat_line in enumerate(category_lines):
                if category_pattern.search(cat_line):
                    category_2013_index = i
                    break # Encontramos la posición de la línea con 2013

            # Si encontramos la categoría 2013 y hay suficientes líneas de horario
            if category_2013_index != -1 and category_2013_index < len(time_lines):
                # La hora correspondiente debería estar en la misma posición relativa
                # dentro de las líneas de horario
                time_line = time_lines[category_2013_index]
                final_time_match = time_pattern.search(time_line)
                if final_time_match:
                    hora_encontrada = final_time_match.group(1).strip()


            data['hora'] = hora_encontrada
            

            # --- Fin de Lógica de Extracción ---

            # Retorna los datos extraídos en formato JSON
            return jsonify(data), 200

        except Exception as e:
            # Captura cualquier otro error durante el procesamiento del PDF
            app.logger.error(f"Error processing PDF: {e}")
            return jsonify({"error": f"Error al procesar el archivo PDF: {e}"}), 500
    else:
        # Maneja el caso donde el archivo no es un PDF
        return jsonify({"error": "Formato de archivo no soportado. Por favor, sube un PDF."}), 400

if __name__ == '__main__':
    # Ejecuta la aplicación Flask.
    # debug=True activa el modo depuración y el reinicio automático (útil en desarrollo).
    # Para producción, desactiva debug y usa un servidor WSGI.
    # Si ejecutas en Jupyter, usa app.run(debug=True, use_reloader=False)
    app.run(debug=True)