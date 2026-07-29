#!/usr/bin/env python3
"""
procesar_simulacro.py — Pipeline OMR por tiras verticales.

Uso:
    python3 procesar_simulacro.py S1 imagenes_muestra/SCAN0008_page-0031.jpg
    python3 procesar_simulacro.py S2 imagenes_muestra/SCAN0008_page-0032.jpg
"""
import cv2
import numpy as np
import os
import sys

# ================================================================
# CONSTANTES DE CORTE — Ajustar si los recortes no caen bien
# Imagen estándar: 1275 x 1650 px
# ================================================================

# === CONFIGURACIÓN S1 ===
# Ajustes exactos por columna (X_INI: donde empiezan los círculos, X_FIN: donde terminan)
# Y_INI: Dónde empiezan verticalmente (debajo de los textos), Y_FIN: Dónde terminan en el fondo
S1_CONF = {
    # Columna 1 (Preguntas 1-30)
    'c1_y_ini': 270, 'c1_y_fin': 1430,
    'c1_x_ini': 140, 'c1_x_fin': 350,
    
    # Columna 2 (Preguntas 31-60)
    'c2_y_ini': 270, 'c2_y_fin': 1430,
    'c2_x_ini': 430, 'c2_x_fin': 630,
    
    # Columna 3 (Preguntas 61-90)
    'c3_y_ini': 270, 'c3_y_fin': 1420,
    'c3_x_ini': 720, 'c3_x_fin': 920,
    
    # Columna 4 (Preguntas 91-120)
    'c4_y_ini': 270, 'c4_y_fin': 1430,
    'c4_x_ini': 1010, 'c4_x_fin': 1230
}

# === CONFIGURACIÓN S2 ===
# Control ABSOLUTO por tira. 
# y_ini: dónde empieza el corte (header), y_fin: dónde termina el corte (footer)
# x_ini: margen izquierdo, x_fin: margen derecho
S2_CONF = {
    # Tira 1 (P1-48, 4 opciones)
    'c1_y_ini': 210, 'c1_y_fin': 1580,
    'c1_x_ini': 120, 'c1_x_fin': 320,
    
    # Tira 2a (P49-79, 4 opciones)
    'c2a_y_ini': 200, 'c2a_y_fin': 1220,
    'c2a_x_ini': 370, 'c2a_x_fin': 560,
    
    # Tira 2b (P80-96, 8 opciones) -> Su propio header para saltar textos intermedios
    'c2b_y_ini': 1220, 'c2b_y_fin': 1520,
    'c2b_x_ini': 385,  'c2b_x_fin': 760, 
    
    # Tira 3 (P97-134, 8 opciones)
    'c3_y_ini': 220, 'c3_y_fin': 1550,
    'c3_x_ini': 830, 'c3_x_fin': 1200, 
}

# === CONFIGURACIÓN SD (Simulacro Diagnóstico - 90 Preguntas, 1 sola hoja, 3 columnas) ===
SD_CONF = {
    # Columna 1 (P1-30, 4 opciones)
    'c1_y_ini': 270, 'c1_y_fin': 1430,
    'c1_x_ini': 140, 'c1_x_fin': 350,
    
    # Columna 2 (P31-60, 4 opciones)
    'c2_y_ini': 270, 'c2_y_fin': 1430,
    'c2_x_ini': 430, 'c2_x_fin': 630,
    
    # Columna 3a (P61-72, 4 opciones)
    'c3a_y_ini': 270, 'c3a_y_fin': 750,
    'c3a_x_ini': 720, 'c3a_x_fin': 930,

    # Columna 3b (P73-90, 8 opciones)
    'c3b_y_ini': 750, 'c3b_y_fin': 1430,
    'c3b_x_ini': 720, 'c3b_x_fin': 1200,
}

# Umbral de relleno para considerar un círculo como marcado
# Al evaluar solo el "adentro" del círculo, un valor más bajo detecta marcas tenues
UMBRAL_MARCADO = 0.25

# ================================================================

# Tamaño de salida estándar al que se normalizará SIEMPRE la hoja
NORM_W = 1275
NORM_H = 1650


def _ordenar_esquinas(pts):
    """
    Dado un array (4,2) de puntos, retorna [top-left, top-right, bottom-right, bottom-left].
    """
    pts = pts.reshape(4, 2).astype(np.float32)
    s   = pts.sum(axis=1)
    d   = np.diff(pts, axis=1)
    return np.array([
        pts[np.argmin(s)],   # top-left     (menor x+y)
        pts[np.argmin(d)],   # top-right    (menor x-y)
        pts[np.argmax(s)],   # bottom-right (mayor x+y)
        pts[np.argmax(d)],   # bottom-left  (mayor x-y)
    ], dtype=np.float32)


def normalizar_hoja(img, debug_dir=None, base=None):
    """
    Detecta los 4 vértices de la hoja escaneada y aplica warpPerspective
    para producir SIEMPRE una imagen de NORM_W × NORM_H píxeles.

    Si no puede detectar la hoja (fondo sin contraste, imagen muy ruidosa),
    cae en un simple recorte centrado con deskew para no romper el flujo.

    Parámetros de debug opcionales:
      debug_dir — carpeta donde guardar imagen diagnóstica
      base      — prefijo del nombre de archivo
    """
    h_img, w_img = img.shape[:2]

    # 1. Convertir a escala de grises y suavizar
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)

    # 2. Umbralización adaptativa para separar hoja del fondo
    #    El fondo del escáner suele ser negro/gris oscuro; la hoja es blanca.
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. Operaciones morfológicas para cerrar pequeños huecos
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # 4. Encontrar contornos y quedarnos con el más grande (la hoja)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _fallback_deskew(img)

    hoja_cnt = max(contours, key=cv2.contourArea)

    # La hoja debe ocupar al menos el 40 % de la imagen
    if cv2.contourArea(hoja_cnt) < 0.40 * w_img * h_img:
        return _fallback_deskew(img)

    # 5. Aproximar a polígono cuadrilátero
    peri  = cv2.arcLength(hoja_cnt, True)
    approx = cv2.approxPolyDP(hoja_cnt, 0.02 * peri, True)

    if len(approx) == 4:
        esquinas = _ordenar_esquinas(approx)
    else:
        # Si no sale exactamente 4 puntos, usamos el bounding rect
        x, y, w, h = cv2.boundingRect(hoja_cnt)
        esquinas = np.array([
            [x,     y    ],
            [x + w, y    ],
            [x + w, y + h],
            [x,     y + h],
        ], dtype=np.float32)

    # 6. Destino: los 4 vértices del tamaño estándar
    dst = np.array([
        [0,      0     ],
        [NORM_W, 0     ],
        [NORM_W, NORM_H],
        [0,      NORM_H],
    ], dtype=np.float32)

    # 7. Perspectiva y warp
    M   = cv2.getPerspectiveTransform(esquinas, dst)
    out = cv2.warpPerspective(img, M, (NORM_W, NORM_H),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)

    # 8. Debug opcional: guardar imagen con esquinas marcadas
    if debug_dir and base:
        diag = img.copy()
        for pt in esquinas.astype(int):
            cv2.circle(diag, tuple(pt), 12, (0, 0, 255), -1)
        cv2.polylines(diag, [esquinas.astype(int)], True, (0, 255, 0), 3)
        cv2.imwrite(os.path.join(debug_dir, f"{base}_normalizacion.jpg"), diag)

    return out


def _fallback_deskew(img):
    """
    Fallback: corrección de ángulo leve con HoughLines cuando no se detecta
    el contorno de la hoja. Devuelve la imagen lo más centrada posible en NORM_W×NORM_H.
    """
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    angle = 0.0
    if lines is not None:
        angles = []
        for rho, theta in lines[:, 0]:
            a = (theta * 180 / np.pi) - 90
            if abs(a) < 10:
                angles.append(a)
        if angles:
            angle = float(np.median(angles))

    h, w = img.shape[:2]
    if abs(angle) >= 0.3:
        M   = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)

    # Redimensionar al tamaño estándar para que las coordenadas sigan funcionando
    return cv2.resize(img, (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)


def hacer_tiras(img, modo, user=None):
    """
    Detecta los 4 grandes rectángulos que envuelven a cada columna de opciones.
    Devuelve la imagen recortada. Si la detección dinámica falla, utiliza las
    coordenadas fijas (S1_CONF, S2_CONF) como fallback robusto.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold adaptativo para resaltar trazos negros (como los rectángulos) sobre fondo blanco
    imgThresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 10
    )
    
    # Unir líneas rotas por el escáner o deterioro
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    imgThresh_closed = cv2.morphologyEx(imgThresh, cv2.MORPH_CLOSE, kernel)
    
    # Encontrar contornos
    contours, _ = cv2.findContours(imgThresh_closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    
    candidatos = []
    
    for c in contours:
        area = cv2.contourArea(c)
        if 50000 < area < 500000:
            x, y, w, h = cv2.boundingRect(c)
            ar = w / float(h)
            if 0.05 < ar < 1.5:  # Ampliado a 1.5 porque la caja 2b (8 opciones) es casi cuadrada
                # Extent asegura que la figura sea rectangular (llena el 80% de su bounding box)
                extent = area / float(w * h)
                if extent > 0.80:
                    cx, cy = x + w // 2, y + h // 2
                    # Evitar duplicados si hay contornos anidados
                    duplicado = False
                    for cand in candidatos:
                        # Si están muy cerca (ej. contorno interno y externo del grosor de la línea)
                        dist = ((cand['cx'] - cx)**2 + (cand['cy'] - cy)**2)**0.5
                        if dist < 30:
                            duplicado = True
                            break
                    if not duplicado:
                        candidatos.append({
                            'x': x, 'y': y, 'w': w, 'h': h,
                            'cx': cx, 'cy': cy, 'area': area
                        })

    # Ordenar candidatos de izquierda a derecha, y de arriba a abajo si están apilados (ej. 2a y 2b)
    import functools
    def cmp_rects(r1, r2):
        if abs(r1['x'] - r2['x']) > 100:
            return r1['x'] - r2['x']
        return r1['y'] - r2['y']
    candidatos = sorted(candidatos, key=functools.cmp_to_key(cmp_rects))

    # Eliminar duplicados superpuestos (IoU > 0.5) conservando el de mayor área
    def iou(a, b):
        """Intersection over Union entre dos bounding boxes."""
        x1 = max(a['x'], b['x'])
        y1 = max(a['y'], b['y'])
        x2 = min(a['x'] + a['w'], b['x'] + b['w'])
        y2 = min(a['y'] + a['h'], b['y'] + b['h'])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0
        area_a = a['w'] * a['h']
        area_b = b['w'] * b['h']
        return inter / float(area_a + area_b - inter)

    filtrados = []
    for cand in candidatos:
        es_duplicado = False
        for i, f in enumerate(filtrados):
            if iou(cand, f) > 0.5:
                # Si se superponen mucho, quedarse con el de mayor área
                if cand['area'] > f['area']:
                    filtrados[i] = cand
                es_duplicado = True
                break
        if not es_duplicado:
            filtrados.append(cand)
    candidatos = filtrados

    # ======== REFINAR BORDES: usar la imagen original (sin MORPH_CLOSE) ========
    # MORPH_CLOSE infla los contornos. Ahora buscamos las líneas reales del rectángulo
    # impreso en imgThresh (sin inflar) para ajustar los bordes con precisión.
    for cand in candidatos:
        x, y, w, h = cand['x'], cand['y'], cand['w'], cand['h']
        # Recortar la región de la imagen original (sin MORPH_CLOSE)
        region = imgThresh[y:y+h, x:x+w]
        
        # --- Refinar bordes verticales (TOP y BOTTOM) ---
        # Proyección horizontal: suma de píxeles blancos por fila
        # Una línea horizontal del borde cruza casi todo el ancho → fill alto
        h_proj = np.sum(region, axis=1) / 255.0
        fill_h = h_proj / region.shape[1]
        # El borde impreso llena >50% del ancho (las burbujas solo ~30%)
        border_rows = np.where(fill_h > 0.50)[0]
        if len(border_rows) >= 2:
            new_top = border_rows[0]
            new_bottom = border_rows[-1]
            if new_bottom - new_top > h * 0.7:  # Sanity check
                cand['y'] = y + new_top
                cand['h'] = new_bottom - new_top
        
        # --- Refinar bordes horizontales (LEFT y RIGHT) ---
        # Proyección vertical: suma de píxeles blancos por columna
        # Una línea vertical del borde cruza casi toda la altura → fill alto
        v_proj = np.sum(region, axis=0) / 255.0
        fill_v = v_proj / region.shape[0]
        border_cols = np.where(fill_v > 0.50)[0]
        if len(border_cols) >= 2:
            new_left = border_cols[0]
            new_right = border_cols[-1]
            if new_right - new_left > w * 0.7:
                cand['x'] = x + new_left
                cand['w'] = new_right - new_left
        
        # Recalcular centro
        cand['cx'] = cand['x'] + cand['w'] // 2
        cand['cy'] = cand['y'] + cand['h'] // 2

    # Re-ordenar después de refinar
    candidatos = sorted(candidatos, key=functools.cmp_to_key(cmp_rects))

    esperados = 3 if modo == 'SD' else 4
    username_str = getattr(user, 'username', None) or (str(user) if user and str(user) else 'Nadie')
    print(f"  📐 Rectángulos detectados por usuario [{username_str}]: {len(candidatos)} (esperados: {esperados})")
    for i, r in enumerate(candidatos):
        print(f"     #{i+1}: x={r['x']}, y={r['y']}, w={r['w']}, h={r['h']}, area={r['area']}")

    tiras_out = []

    # ======== FALLBACK A COORDENADAS FIJAS SI NO ENCONTRÓ LOS RECTÁNGULOS ESPERADOS ========
    if len(candidatos) < esperados:
        print(f"⚠️ ADVERTENCIA: Solo se encontraron {len(candidatos)} rectángulos dinámicos.")
        print(f"✅ Usando coordenadas de fallback para {modo} en su lugar.")
        
        if modo == 'S1':
            keys = ['c1', 'c2', 'c3', 'c4']
            conf = S1_CONF
        elif modo == 'SD':
            keys = ['c1', 'c2', 'c3a', 'c3b']
            conf = SD_CONF
        else:
            keys = ['c1', 'c2a', 'c2b', 'c3']
            conf = S2_CONF
            
        for k in keys:
            y_ini, y_fin = conf[f'{k}_y_ini'], conf[f'{k}_y_fin']
            x_ini, x_fin = conf[f'{k}_x_ini'], conf[f'{k}_x_fin']
            tira = img[y_ini:y_fin, x_ini:x_fin]
            tiras_out.append(tira)
    else:
        # Quedarse con la cantidad de rectángulos esperados
        if len(candidatos) > esperados:
            candidatos = candidatos[:esperados]

        for rect in candidatos:
            x, y, w, h = rect['x'], rect['y'], rect['w'], rect['h']
            
            # Recorte directo 2D (sin deformar, la hoja ya está recta)
            pad = 12
            y1 = max(0, y - pad)
            y2 = min(img.shape[0], y + h + pad)
            x1 = max(0, x - pad)
            x2 = min(img.shape[1], x + w + pad)
            
            tira = img[y1:y2, x1:x2]
            tiras_out.append(tira)

        if modo == 'SD':
            # Para SD (3 rectángulos), el tercer rectángulo contiene P61-72 (4 opciones) y P73-90 (8 opciones)
            tira_c3 = tiras_out[2]
            h_c3, w_c3 = tira_c3.shape[:2]
            tira_c3a = tira_c3[:int(h_c3 * 0.42), :int(w_c3 * 0.55)]
            tira_c3b = tira_c3[int(h_c3 * 0.38):, :]
            tiras_out = [tiras_out[0], tiras_out[1], tira_c3a, tira_c3b]

    # Retornar con las configuraciones según el modo
    if modo == 'S1':
        return [
            (tiras_out[0], 4, 'S1_C1_P1-30'),
            (tiras_out[1], 4, 'S1_C2_P31-60'),
            (tiras_out[2], 4, 'S1_C3_P61-90'),
            (tiras_out[3], 4, 'S1_C4_P91-120'),
        ]
    elif modo == 'S2':
        return [
            (tiras_out[0], 4, 'S2_C1_P1-48'),
            (tiras_out[1], 4, 'S2_C2a_P49-79'),
            (tiras_out[2], 8, 'S2_C2b_P80-96'),
            (tiras_out[3], 8, 'S2_C3_P97-134'),
        ]
    elif modo == 'SD':
        return [
            (tiras_out[0], 4, 'SD_C1_P1-30'),
            (tiras_out[1], 4, 'SD_C2_P31-60'),
            (tiras_out[2], 4, 'SD_C3a_P61-72'),
            (tiras_out[3], 8, 'SD_C3b_P73-90'),
        ]

    raise ValueError(f"Modo desconocido: '{modo}'. Usa 'S1', 'S2' o 'SD'.")


def encontrar_circulos_en_tira(tira, n_opciones=4):
    """
    Detecta contornos de círculos en una tira ya recortada.
    Retorna: (imgThresh, lista_de_contornos, imagen_debug)
    """
    gray = cv2.cvtColor(tira, cv2.COLOR_BGR2GRAY)
    imgThresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 10
    )
    # Usamos RETR_LIST para que el marco exterior del rectángulo no oculte los círculos
    contours, _ = cv2.findContours(imgThresh, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # Para círculos, el aspect ratio debe estar cerca de 1.0
    ar_min = 0.75
    ar_max = 1.35

    candidatos = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h == 0:
            continue
        ar   = w / float(h)
        area = w * h
        # Filtramos por proporciones de círculo y un área razonable
        if ar_min < ar < ar_max and 40 < area < 4500:
            cx, cy = x + w//2, y + h//2
            es_duplicado = False
            for cand in candidatos:
                if abs(cand['cx'] - cx) < 8 and abs(cand['cy'] - cy) < 8:
                    es_duplicado = True
                    # Al usar RETR_LIST, el mismo círculo se detecta por dentro y por fuera de su línea.
                    # Nos quedamos con el contorno de mayor área (el borde exterior).
                    if area > cand['area']:
                        cand['c'] = c
                        cand['w'], cand['h'] = w, h
                        cand['x'], cand['y'] = x, y
                        cand['area'] = area
                    break
            if not es_duplicado:
                candidatos.append({'c': c, 'w': w, 'h': h, 'x': x, 'y': y, 'cx': cx, 'cy': cy, 'area': area})

    img_debug = tira.copy()
    if not candidatos:
        return imgThresh, [], img_debug

    mw = np.median([c['w'] for c in candidatos])
    mh = np.median([c['h'] for c in candidatos])
    
    # Tolerancia para tamaños de círculos
    max_w_factor = 1.5
    max_h_factor = 1.5

    validos = []
    for c in candidatos:
        if (mw * 0.65 < c['w'] < mw * max_w_factor) and (mh * 0.65 < c['h'] < mh * max_h_factor):
            validos.append(c['c'])
            cv2.rectangle(img_debug,
                          (c['x'], c['y']),
                          (c['x'] + c['w'], c['y'] + c['h']),
                          (0, 200, 0), 2)

    return imgThresh, validos, img_debug


def evaluar_tira(contours, imgThresh, n_opciones):
    """
    Dado el conjunto de círculos detectados en UNA tira vertical de una sola
    columna de preguntas, determina la letra marcada en cada fila.
    """
    LETRAS = {4: ['A', 'B', 'C', 'D'], 8: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']}
    letras = LETRAS[n_opciones]

    if not contours:
        return []

    burbujas = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        burbujas.append({'x': x, 'y': y, 'w': w, 'h': h,
                         'cX': x + w // 2, 'cY': y + h // 2})

    # Agrupar en filas por coordenada Y
    burbujas = sorted(burbujas, key=lambda b: b['cY'])
    tol_y = burbujas[0]['h'] * 0.70
    filas, fila = [], [burbujas[0]]
    for b in burbujas[1:]:
        if abs(b['cY'] - fila[-1]['cY']) < tol_y:
            fila.append(b)
        else:
            filas.append(fila)
            fila = [b]
    filas.append(fila)

    # Centros X esperados para cada opción
    filas_ok = [f for f in filas if len(f) == n_opciones]
    if filas_ok:
        for f in filas_ok:
            f.sort(key=lambda b: b['cX'])
        centros = [np.median([f[i]['cX'] for f in filas_ok]) for i in range(n_opciones)]
    else:
        xs = [b['cX'] for b in burbujas]
        mn, mx = min(xs), max(xs)
        sp = (mx - mn) / (n_opciones - 1) if mx > mn else 1
        centros = [mn + sp * i for i in range(n_opciones)]

    # Evaluar cada fila
    respuestas = []
    for fila in filas:
        if len(fila) < 2:
            continue
        opciones = []
        for b in fila:
            idx = min(range(n_opciones), key=lambda i: abs(b['cX'] - centros[i]))
            
            # Recortamos el borde (15%) para evaluar SOLO el interior del círculo
            # Esto evita que la línea negra del propio círculo sume píxeles oscuros
            m_x = int(b['w'] * 0.15)
            m_y = int(b['h'] * 0.15)
            roi = imgThresh[b['y']+m_y : b['y']+b['h']-m_y, b['x']+m_x : b['x']+b['w']-m_x]
            
            if roi.size > 0:
                ratio = cv2.countNonZero(roi) / roi.size
            else:
                ratio = 0
            opciones.append((idx, ratio))

        # Ordenar opciones de la más oscura a la más clara
        opciones.sort(key=lambda x: x[1], reverse=True)
        mejor_idx, mejor_ratio = opciones[0]
        segundo_ratio = opciones[1][1] if len(opciones) > 1 else 0

        # Criterio de marcado:
        # 1. La opción más oscura debe superar el UMBRAL_MARCADO mínimo.
        # 2. Debe ser significativamente más oscura que la segunda opción (+10%).
        if mejor_ratio >= UMBRAL_MARCADO:
            if (mejor_ratio > segundo_ratio + 0.10):
                respuestas.append(letras[mejor_idx] if mejor_idx < len(letras) else '?')
            else:
                # Si hay dos muy parecidas de oscuras, es una doble marca
                respuestas.append('Z')
        else:
            # Si ninguna supera el umbral, está en blanco
            respuestas.append('Z')

    return respuestas


def procesar_imagen(image_path, modo, debug=False, user=None):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"No se pudo cargar la imagen: {image_path}")

    if debug:
        print(f"  Imagen cargada: {img.shape[1]}x{img.shape[0]}px")
        # Relativo al archivo .py, sin importar desde dónde se corra
        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cv_prototypes", "tiras")
        os.makedirs(debug_dir, exist_ok=True)
        base = os.path.basename(image_path).replace('.jpg', '').replace('.png', '')
    else:
        debug_dir = None
        base = None

    # Normalizar perspectiva: detecta la hoja y la estira a NORM_W × NORM_H siempre
    img = normalizar_hoja(img, debug_dir=debug_dir, base=base)
    if debug:
        print(f"  Hoja normalizada a {img.shape[1]}x{img.shape[0]}px")

    tiras = hacer_tiras(img, modo, user=user)

    secuencia = []
    for num, (tira_img, n_opciones, etiqueta) in enumerate(tiras, start=1):
        imgThresh, circulos, debug_img = encontrar_circulos_en_tira(tira_img, n_opciones)
        respuestas = evaluar_tira(circulos, imgThresh, n_opciones)
        secuencia.extend(respuestas)

        if debug:
            # Guardar el recorte limpio (para verificar que los cortes son correctos)
            nombre_corte = f"{base}_corte{num}.jpg"
            cv2.imwrite(os.path.join(debug_dir, nombre_corte), tira_img)

            # Guardar el recorte con los círculos detectados marcados en verde
            nombre_deteccion = f"{base}_corte{num}_deteccion.jpg"
            cv2.imwrite(os.path.join(debug_dir, nombre_deteccion), debug_img)

            print(f"  [{etiqueta}] {len(circulos)} círculos → {len(respuestas)} respuestas: {''.join(respuestas)}")
            print(f"    Guardado: {nombre_corte}  |  {nombre_deteccion}")

    return secuencia


# Longitudes exactas esperadas por tira
LONGITUDES_ESPERADAS = {
    'S1': {'C1': 30, 'C2': 30, 'C3': 30, 'C4': 30},
    'S2': {'C1': 45, 'C2a': 34, 'C2b': 10, 'C3': 45},
    'SD': {'C1': 30, 'C2': 30, 'C3a': 12, 'C3b': 18},
}

ETIQUETAS_S1 = ['C1', 'C2', 'C3', 'C4']
ETIQUETAS_S2 = ['C1', 'C2a', 'C2b', 'C3']
ETIQUETAS_SD = ['C1', 'C2', 'C3a', 'C3b']


def extraer_tiras_individuales(path_s1, path_s2, user=None):
    """
    Procesa las dos imágenes de un alumno y devuelve las secuencias
    desglosadas por tira (sin concatenar), junto con el estado de cada una.

    Retorna:
        dict con estructura:
        {
            's1': [
                {'etiqueta': 'C1', 'secuencia': 'ABCD...', 'esperado': 30, 'ok': True},
                ...
            ],
            's2': [
                {'etiqueta': 'C1', 'secuencia': 'ABCD...', 'esperado': 48, 'ok': True},
                ...
            ],
            'error': None  # o string con descripción del error si falló el OMR
        }
    """
    resultado = {'s1': [], 's2': [], 'error': None}

    try:
        img_s1 = cv2.imread(path_s1)
        if img_s1 is None:
            raise ValueError(f"No se pudo cargar: {path_s1}")
        img_s1 = normalizar_hoja(img_s1)
        tiras_s1 = hacer_tiras(img_s1, 'S1', user=user)

        for i, (tira_img, n_opciones, _etq) in enumerate(tiras_s1):
            imgThresh, circulos, _ = encontrar_circulos_en_tira(tira_img, n_opciones)
            respuestas = evaluar_tira(circulos, imgThresh, n_opciones)
            etiqueta = ETIQUETAS_S1[i]
            esperado = LONGITUDES_ESPERADAS['S1'][etiqueta]
            seq = ''.join(respuestas)
            resultado['s1'].append({
                'etiqueta': etiqueta,
                'secuencia': seq,
                'esperado': esperado,
                'ok': len(seq) == esperado,
            })
    except Exception as e:
        resultado['error'] = f"S1: {e}"

    try:
        img_s2 = cv2.imread(path_s2)
        if img_s2 is None:
            raise ValueError(f"No se pudo cargar: {path_s2}")
        img_s2 = normalizar_hoja(img_s2)
        tiras_s2 = hacer_tiras(img_s2, 'S2', user=user)

        for i, (tira_img, n_opciones, _etq) in enumerate(tiras_s2):
            imgThresh, circulos, _ = encontrar_circulos_en_tira(tira_img, n_opciones)
            respuestas = evaluar_tira(circulos, imgThresh, n_opciones)
            etiqueta = ETIQUETAS_S2[i]
            esperado = LONGITUDES_ESPERADAS['S2'][etiqueta]
            seq = ''.join(respuestas)
            resultado['s2'].append({
                'etiqueta': etiqueta,
                'secuencia': seq,
                'esperado': esperado,
                'ok': len(seq) == esperado,
            })
    except Exception as e:
        err_prev = resultado.get('error') or ''
        resultado['error'] = (err_prev + ' | ' if err_prev else '') + f"S2: {e}"

    return resultado


def extraer_tiras_diagnostico(path_imagen, user=None):
    """
    Procesa la única imagen de un alumno para el Simulacro Diagnóstico (90 preguntas)
    y devuelve las secuencias por tira (C1, C2, C3a, C3b).
    """
    resultado = {'sd': [], 'error': None}

    try:
        img_sd = cv2.imread(path_imagen)
        if img_sd is None:
            raise ValueError(f"No se pudo cargar la imagen: {path_imagen}")
        img_sd = normalizar_hoja(img_sd)
        tiras_sd = hacer_tiras(img_sd, 'SD', user=user)

        for i, (tira_img, n_opciones, _etq) in enumerate(tiras_sd):
            imgThresh, circulos, _ = encontrar_circulos_en_tira(tira_img, n_opciones)
            respuestas = evaluar_tira(circulos, imgThresh, n_opciones)
            etiqueta = ETIQUETAS_SD[i]
            esperado = LONGITUDES_ESPERADAS['SD'][etiqueta]
            seq = ''.join(respuestas)
            resultado['sd'].append({
                'etiqueta': etiqueta,
                'secuencia': seq,
                'esperado': esperado,
                'ok': len(seq) == esperado,
            })
    except Exception as e:
        resultado['error'] = f"SD: {e}"

    return resultado





if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 procesar_simulacro.py <S1|S2> <imagen.jpg>")
        sys.exit(1)

    modo   = sys.argv[1].upper()
    imagen = sys.argv[2]

    if modo not in ('S1', 'S2'):
        print("Error: modo debe ser S1 o S2")
        sys.exit(1)

    TOTAL = {'S1': 120, 'S2': 134}

    print(f"\n{'='*60}")
    print(f"  MODO: {modo}  |  Imagen: {imagen}")
    print(f"{'='*60}")

    try:
        seq = procesar_imagen(imagen, modo, debug=True)
        total_esperado = TOTAL[modo]
        print(f"\n{'='*60}")
        print(f"SECUENCIA FINAL ({len(seq)} / {total_esperado} esperadas):")
        print(''.join(seq))
        print('='*60)
        if len(seq) != total_esperado:
            print(f"\n⚠️  Diferencia de {abs(len(seq) - total_esperado)} preguntas.")
            print("   → Ajusta HEADER_PX, COL_X1, COL_X2, MARGIN_LEFT o MARGIN_RIGHT")
            print("     y vuelve a correr hasta que el conteo sea correcto.")
        else:
            print("\n✅ Conteo exacto. Revisa la secuencia para verificar precisión.")
        print(f"\nDebug de tiras en: {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cv_prototypes', 'tiras')}/")
    except Exception as e:
        import traceback
        traceback.print_exc()
