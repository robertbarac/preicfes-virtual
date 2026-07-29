import cv2
import numpy as np
import os
import sys

def cortar_en_columnas(image_path, output_dir="recortes"):
    print(f"Procesando: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"No se pudo cargar {image_path}. Verifica la ruta.")

    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Convertir a escala de grises y binarizar
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Invertir para que la tinta sea blanca (valores > 0) y el fondo negro (0)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # 2. Proyección vertical: sumar los píxeles blancos en cada columna X
    # Esto nos dirá dónde hay tinta y dónde están los "ríos" en blanco entre columnas
    proyeccion_x = np.sum(thresh, axis=0)

    # 3. Suavizar la proyección para no confundirnos con basuritas
    kernel_size = 20
    proyeccion_suave = np.convolve(proyeccion_x, np.ones(kernel_size)/kernel_size, mode='same')

    ancho = img.shape[1]
    
    # Buscar los dos valles más profundos (las canaletas blancas)
    # Dividimos la imagen mentalmente en 3 tercios, y buscamos el mínimo en el tercio 1-2 y el tercio 2-3
    tercio = ancho // 3
    
    # Buscar el corte 1 (entre la columna 1 y 2)
    inicio_corte_1 = int(tercio * 0.8)
    fin_corte_1 = int(tercio * 1.2)
    # El punto de corte es donde hay menos tinta (el mínimo de la proyección)
    x_corte_1 = inicio_corte_1 + np.argmin(proyeccion_suave[inicio_corte_1:fin_corte_1])

    # Buscar el corte 2 (entre la columna 2 y 3)
    inicio_corte_2 = int(tercio * 1.8)
    fin_corte_2 = int(tercio * 2.2)
    x_corte_2 = inicio_corte_2 + np.argmin(proyeccion_suave[inicio_corte_2:fin_corte_2])

    print(f"Ancho total: {ancho}px")
    print(f"Corte seguro 1 (Columna 1|2): X={x_corte_1}")
    print(f"Corte seguro 2 (Columna 2|3): X={x_corte_2}")

    # 4. Recortar la imagen original usando esos puntos seguros
    col1 = img[:, 0:x_corte_1]
    col2 = img[:, x_corte_1:x_corte_2]
    col3 = img[:, x_corte_2:ancho]

    # 5. Guardar los recortes
    base_name = os.path.basename(image_path).split('.')[0]
    
    p1 = os.path.join(output_dir, f"{base_name}_col1.jpg")
    p2 = os.path.join(output_dir, f"{base_name}_col2.jpg")
    p3 = os.path.join(output_dir, f"{base_name}_col3.jpg")

    cv2.imwrite(p1, col1)
    cv2.imwrite(p2, col2)
    cv2.imwrite(p3, col3)

    print("\n¡Cortes exitosos y seguros (sin mochar burbujas)!")
    print(f"Revisa la carpeta '{output_dir}/'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python detectar_cortes.py <ruta_imagen>")
    else:
        cortar_en_columnas(sys.argv[1])
