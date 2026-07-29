import cv2
import numpy as np
from collections import Counter


def alinear_documento(image_path):
    """Carga y redimensiona la imagen. Sin CamScanner — la foto ya viene derecha."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {image_path}")
    img = cv2.resize(img, (900, 1200))
    imgGray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return [img.copy()], img, imgGray, imgGray, imgGray, img.copy(), img.copy()


def encontrar_ovalos(img_warped):
    """
    Detecta óvalos en la imagen con tres filtros en cascada:
    1. Aspect ratio + área + ignorar encabezado y bordes
    2. Mediana ±35% (los óvalos impresos tienen tamaño uniforme)
    """
    imgGray = cv2.cvtColor(img_warped, cv2.COLOR_BGR2GRAY)
    alto_total, ancho_total = img_warped.shape[:2]

    # Umbral adaptativo: nivela sombras y variaciones de iluminación
    imgThresh = cv2.adaptiveThreshold(
        imgGray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 10
    )

    contours, _ = cv2.findContours(imgThresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidatos = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        aspect_ratio = w / float(h)
        area = w * h

        # Descartar encabezado (15% superior — nombre, logo, jornada)
        if y < (alto_total * 0.15):
            continue

        if 1.0 < aspect_ratio < 2.5 and 50 < area < 4000:
            candidatos.append({'c': c, 'w': w, 'h': h, 'x': x, 'y': y})

    img_debug = img_warped.copy()
    ovalos_validos = []

    if not candidatos:
        return imgThresh, img_debug, ovalos_validos

    # Filtro de mediana ±35%
    anchos = [cand['w'] for cand in candidatos]
    altos = [cand['h'] for cand in candidatos]
    mediana_w = np.median(anchos)
    mediana_h = np.median(altos)

    for cand in candidatos:
        w, h = cand['w'], cand['h']
        if (mediana_w * 0.65 < w < mediana_w * 1.35) and \
           (mediana_h * 0.65 < h < mediana_h * 1.35):
            ovalos_validos.append(cand['c'])
            cv2.rectangle(img_debug,
                          (cand['x'], cand['y']),
                          (cand['x'] + w, cand['y'] + h),
                          (0, 255, 0), 2)

    return imgThresh, img_debug, ovalos_validos


def agrupar_y_evaluar_ovalos(burbujas_contours, imgThresh):
    """
    1. Agrupa burbujas por columnas y luego por filas.
    2. Dinámica: cada fila puede tener 4 u 8 opciones.
    """
    if not burbujas_contours:
        return []

    burbujas_data = []
    for c in burbujas_contours:
        x, y, w, h = cv2.boundingRect(c)
        burbujas_data.append({
            'c': c, 'x': x, 'y': y, 'w': w, 'h': h,
            'cX': x + w // 2, 'cY': y + h // 2
        })

    # Agrupar en columnas de izquierda a derecha
    burbujas_data = sorted(burbujas_data, key=lambda b: b['cX'])
    tolerancia_x = burbujas_data[0]['w'] * 3

    columnas = []
    col_actual = [burbujas_data[0]]
    for b in burbujas_data[1:]:
        if (b['cX'] - col_actual[-1]['cX']) < tolerancia_x:
            col_actual.append(b)
        else:
            columnas.append(col_actual)
            col_actual = [b]
    columnas.append(col_actual)

    respuestas = []

    for columna in columnas:
        columna = sorted(columna, key=lambda b: b['cY'])
        tolerancia_y = columna[0]['h'] * 0.70

        filas = []
        fila_actual = [columna[0]]
        for b in columna[1:]:
            if abs(b['cY'] - fila_actual[-1]['cY']) < tolerancia_y:
                fila_actual.append(b)
            else:
                filas.append(fila_actual)
                fila_actual = [b]
        filas.append(fila_actual)

        # Encontrar los centros X ideales basándonos en filas de 4 elementos
        filas_completas = [f for f in filas if len(f) == 4]
        if filas_completas:
            for f in filas_completas:
                f.sort(key=lambda b: b['cX'])
            centros_esperados = [
                np.median([f[0]['cX'] for f in filas_completas]),
                np.median([f[1]['cX'] for f in filas_completas]),
                np.median([f[2]['cX'] for f in filas_completas]),
                np.median([f[3]['cX'] for f in filas_completas])
            ]
        else:
            # Fallback en caso de que ninguna fila esté completa
            cXs = [b['cX'] for b in columna]
            min_x, max_x = min(cXs), max(cXs)
            sp = (max_x - min_x) / 3 if max_x > min_x else 1
            centros_esperados = [min_x, min_x + sp, min_x + 2*sp, max_x]

        for fila in filas:
            if len(fila) < 2:
                continue

            opciones_detectadas = []
            for b in fila:
                # Asignar a A, B, C, o D buscando el centro esperado más cercano
                distancias = [abs(b['cX'] - cx) for cx in centros_esperados]
                idx_opcion = distancias.index(min(distancias))

                # Evaluar llenado del óvalo
                x, y, w, h = b['x'], b['y'], b['w'], b['h']
                roi = imgThresh[y:y + h, x:x + w]
                total = w * h
                ratio = cv2.countNonZero(roi) / total if total > 0 else 0
                opciones_detectadas.append((idx_opcion, ratio))

            # Umbral dinámico: vacío ~23%, marcado >= 40% (ajustado para el escáner)
            umbral_marcado = 0.40
            marcados = [idx for idx, ratio in opciones_detectadas if ratio >= umbral_marcado]

            letras = ['A', 'B', 'C', 'D']
            if len(marcados) == 0:
                respuestas.append('Z')
            elif len(marcados) > 1:
                respuestas.append('Z')
            else:
                idx = marcados[0]
                respuestas.append(letras[idx] if idx < len(letras) else '?')

    return respuestas


def stackImages(imgArray, scale, lables=[]):
    rows = len(imgArray)
    cols = len(imgArray[0])
    rowsAvailable = isinstance(imgArray[0], list)
    width = imgArray[0][0].shape[1]
    height = imgArray[0][0].shape[0]
    scaled_w = int(width * scale)
    scaled_h = int(height * scale)

    if rowsAvailable:
        for x in range(0, rows):
            for y in range(0, cols):
                imgArray[x][y] = cv2.resize(imgArray[x][y], (scaled_w, scaled_h))
                if len(imgArray[x][y].shape) == 2:
                    imgArray[x][y] = cv2.cvtColor(imgArray[x][y], cv2.COLOR_GRAY2BGR)
        hor = [np.hstack(imgArray[x]) for x in range(rows)]
        ver = np.vstack(hor)
    else:
        for x in range(0, rows):
            imgArray[x] = cv2.resize(imgArray[x], (scaled_w, scaled_h))
            if len(imgArray[x].shape) == 2:
                imgArray[x] = cv2.cvtColor(imgArray[x], cv2.COLOR_GRAY2BGR)
        ver = np.hstack(imgArray)

    return ver
