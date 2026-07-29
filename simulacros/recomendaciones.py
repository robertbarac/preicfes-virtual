"""
recomendaciones.py
==================
Módulo para generar análisis y recomendaciones dinámicas por alumno
en función de sus puntajes por componente ICFES (escala 0-100).

Niveles:
  0  – 39  → Muy bajo  (área crítica severa)
  40 – 54  → Bajo      (área crítica)
  55 – 69  → Medio
  70 – 84  → Medio-Alto
  85 – 100 → Alto / Muy alto
"""

# ---------------------------------------------------------------------------
# Configuración de áreas
# ---------------------------------------------------------------------------

AREAS_CONFIG = {
    'matematicas': {
        'nombre': 'Matemáticas',
        'emoji': '🔢',
        'fortalezas': {
            'muy_bajo': [
                'Reconoce algunas operaciones básicas',
            ],
            'bajo': [
                'Maneja operaciones aritméticas elementales',
                'Comprende enunciados de problemas simples',
            ],
            'medio': [
                'Manejo básico de operaciones',
                'Comprensión de problemas sencillos',
                'Nociones de álgebra elemental',
            ],
            'medio_alto': [
                'Buen manejo algebraico',
                'Resolución correcta de problemas aplicados',
                'Comprensión de funciones básicas',
            ],
            'alto': [
                'Sólida comprensión analítica',
                'Alto rendimiento en resolución de problemas',
                'Dominio de álgebra, funciones y estadística',
            ],
        },
        'recomendaciones': {
            'muy_bajo': [
                'Repasar operaciones básicas y fracciones desde cero',
                'Usar videos introductorios (Khan Academy, YouTube)',
                'Practicar 30 min diarios con ejercicios graduales',
                'Reforzar temas: números, porcentajes, razones',
            ],
            'bajo': [
                'Reforzar resolución de problemas aplicados',
                'Practicar temas de: Álgebra, Funciones, Estadística básica',
                'Realizar simulacros cronometrados',
                'Identificar el tipo de error recurrente (conceptual vs. operativo)',
            ],
            'medio': [
                'Afianzar álgebra y funciones',
                'Practicar problemas de razonamiento lógico',
                'Resolver bancos de preguntas tipo ICFES',
                'Trabajar estadística y probabilidad',
            ],
            'medio_alto': [
                'Profundizar en geometría analítica y trigonometría',
                'Resolver problemas de mayor complejidad',
                'Repasar errores en simulacros anteriores',
            ],
            'alto': [
                'Mantener el nivel con práctica semanal constante',
                'Explorar temas avanzados como series y combinatoria',
                'Apoyar a compañeros como estrategia de afianzamiento',
            ],
        },
    },
    'lectura': {
        'nombre': 'Lectura Crítica',
        'emoji': '📖',
        'fortalezas': {
            'muy_bajo': [
                'Comprende textos muy cortos y directos',
            ],
            'bajo': [
                'Identificación de información explícita',
                'Lectura literal básica',
            ],
            'medio': [
                'Comprensión de textos narrativos',
                'Identificación de ideas principales',
                'Inferencia básica',
            ],
            'medio_alto': [
                'Buena comprensión lectora',
                'Capacidad de análisis de texto',
                'Reconocimiento de estructura argumentativa',
            ],
            'alto': [
                'Excelente comprensión lectora',
                'Alta capacidad de análisis e inferencia',
                'Dominio de textos argumentativos y filosóficos',
            ],
        },
        'recomendaciones': {
            'muy_bajo': [
                'Leer textos cortos diariamente (noticias, cuentos)',
                'Practicar el subrayado de ideas principales',
                'Responder preguntas literales sobre lo leído',
                'Trabajar con material de lectura graduada',
            ],
            'bajo': [
                'Leer textos variados: editoriales, artículos de opinión',
                'Practicar preguntas de inferencia y significado',
                'Identificar la intención del autor en cada texto',
                'Resolver 10 preguntas tipo ICFES por día',
            ],
            'medio': [
                'Leer textos argumentativos y filosóficos',
                'Practicar análisis de estructura textual',
                'Identificar falacias y argumentos en editoriales',
                'Realizar ensayos cortos para fortalecer interpretación',
            ],
            'medio_alto': [
                'Enfocarse en preguntas de análisis profundo',
                'Revisar errores en preguntas de tipo inferencial',
                'Usar Lectura Crítica para apoyar otras áreas (interpretación de enunciados)',
            ],
            'alto': [
                'Mantener el nivel con textos académicos y filosóficos',
                'Servir de apoyo para interpretar preguntas en otras áreas',
                'Explorar ensayos literarios y crítica cultural',
            ],
        },
    },
    'sociales': {
        'nombre': 'Ciencias Sociales y Ciudadanas',
        'emoji': '🌎',
        'fortalezas': {
            'muy_bajo': [
                'Reconoce conceptos históricos básicos',
            ],
            'bajo': [
                'Conocimiento general de historia nacional',
                'Nociones básicas de geografía',
            ],
            'medio': [
                'Comprensión general de contextos históricos y sociales',
                'Manejo básico de conceptos constitucionales',
            ],
            'medio_alto': [
                'Buen análisis de fenómenos sociales y políticos',
                'Comprensión de estructuras de gobierno',
                'Interpretación de gráficas y mapas',
            ],
            'alto': [
                'Excelente análisis crítico social y político',
                'Sólido dominio de historia, geografía y constitución',
                'Alta capacidad argumentativa en contextos ciudadanos',
            ],
        },
        'recomendaciones': {
            'muy_bajo': [
                'Repasar historia de Colombia desde la colonia',
                'Estudiar los derechos fundamentales de la Constitución',
                'Ver documentales históricos como material de apoyo',
                'Leer resúmenes de los periodos históricos clave',
            ],
            'bajo': [
                'Profundizar en análisis crítico de fenómenos sociales',
                'Interpretar gráficas, mapas y tablas históricas',
                'Practicar preguntas tipo ICFES enfocadas en argumentación',
                'Estudiar la Constitución Política de Colombia',
            ],
            'medio': [
                'Afianzar interpretación de fuentes históricas primarias',
                'Estudiar competencias ciudadanas y convivencia',
                'Resolver preguntas de análisis de coyuntura política',
            ],
            'medio_alto': [
                'Profundizar en economía básica y relaciones internacionales',
                'Practicar preguntas de análisis de causalidad histórica',
                'Reforzar cartografía y geografía económica',
            ],
            'alto': [
                'Mantener con lectura de actualidad y geopolítica',
                'Explorar temas de filosofía política',
                'Apoyar a compañeros en análisis de contextos sociales',
            ],
        },
    },
    'naturales': {
        'nombre': 'Ciencias Naturales',
        'emoji': '🔬',
        'fortalezas': {
            'muy_bajo': [
                'Reconoce seres vivos y conceptos básicos de la naturaleza',
            ],
            'bajo': [
                'Conocimiento elemental de biología',
                'Nociones básicas de materia y energía',
            ],
            'medio': [
                'Comprensión básica de sistemas biológicos',
                'Conocimiento de reacciones químicas simples',
                'Manejo de conceptos físicos elementales',
            ],
            'medio_alto': [
                'Buen manejo de conceptos biológicos y químicos',
                'Interpretación correcta de situaciones experimentales',
                'Comprensión de leyes físicas fundamentales',
            ],
            'alto': [
                'Excelente dominio de biología, química y física',
                'Alta capacidad de análisis experimental',
                'Comprensión profunda de fenómenos naturales',
            ],
        },
        'recomendaciones': {
            'muy_bajo': [
                'Comenzar con biología básica: célula, ecosistemas',
                'Ver videos explicativos (CrashCourse, Khan Academy)',
                'Estudiar con mapas conceptuales para cada tema',
                'Reforzar: célula, clasificación de seres vivos, materia',
            ],
            'bajo': [
                'Reforzar temas clave: Biología (células, genética), '
                'Química (reacciones básicas), Física (conceptos fundamentales)',
                'Usar videos explicativos y ejercicios prácticos tipo ICFES',
                'Estudiar con enfoque en comprensión, no memorización',
            ],
            'medio': [
                'Profundizar en genética y evolución',
                'Practicar problemas de química con ecuaciones',
                'Estudiar cinemática y dinámica básica en física',
                'Resolver preguntas de interpretación experimental',
            ],
            'medio_alto': [
                'Afianzar termodinámica y electromagnetismo',
                'Estudiar metabolismo y fisiología humana',
                'Practicar análisis de gráficas experimentales',
            ],
            'alto': [
                'Mantener con lectura de artículos científicos divulgativos',
                'Explorar temas de bioquímica y física moderna',
                'Profundizar en la interpretación de datos experimentales complejos',
            ],
        },
    },
    'ingles': {
        'nombre': 'Inglés',
        'emoji': '🇬🇧',
        'fortalezas': {
            'muy_bajo': [
                'Reconoce palabras básicas en inglés',
            ],
            'bajo': [
                'Comprensión de vocabulario frecuente',
                'Lectura básica con apoyo del contexto',
            ],
            'medio': [
                'Comprensión básica de textos cortos',
                'Manejo de vocabulario general',
            ],
            'medio_alto': [
                'Buena comprensión lectora en inglés',
                'Manejo adecuado de vocabulario académico',
                'Identificación de idea principal en textos',
            ],
            'alto': [
                'Excelente comprensión lectora en inglés',
                'Dominio de vocabulario académico y técnico',
                'Alta capacidad de inferencia en textos en inglés',
            ],
        },
        'recomendaciones': {
            'muy_bajo': [
                'Iniciar con vocabulario básico (Duolingo, flashcards)',
                'Practicar estructuras de oraciones simples',
                'Ver series o videos con subtítulos en inglés',
                'Memorizar 10 palabras nuevas por día',
            ],
            'bajo': [
                'Mejorar vocabulario académico con listas temáticas',
                'Practicar comprensión de lectura en contexto',
                'Realizar pruebas tipo ICFES de inglés',
                'Leer textos cortos en inglés diariamente',
            ],
            'medio': [
                'Leer artículos cortos en inglés sin diccionario',
                'Practicar inferencia de significado por contexto',
                'Resolver bancos de preguntas de comprensión lectora',
                'Revisar conectores lógicos (however, therefore, although…)',
            ],
            'medio_alto': [
                'Leer textos académicos en inglés regularmente',
                'Enfocarse en preguntas de propósito del autor',
                'Reforzar vocabulario técnico en áreas de interés',
            ],
            'alto': [
                'Mantener con lectura de artículos en inglés semanalmente',
                'Explorar textos de nivel B2–C1',
                'Usar el inglés como ventaja en preguntas de interpretación',
            ],
        },
    },
}

# ---------------------------------------------------------------------------
# Funciones de clasificación
# ---------------------------------------------------------------------------

def clasificar_nivel(puntaje: float) -> dict:
    """
    Clasifica un puntaje (0-100) en un nivel descriptivo.
    Retorna dict con: clave, etiqueta, es_critica, es_fortaleza.
    """
    if puntaje < 40:
        return {
            'clave': 'muy_bajo' if puntaje < 40 else 'bajo',
            'etiqueta': 'Muy bajo (Área crítica)' if puntaje < 40 else 'Bajo (Área crítica)',
            'es_critica': True,
            'es_fortaleza': False,
        }
    elif puntaje < 55:
        return {
            'clave': 'bajo',
            'etiqueta': 'Bajo (Área crítica)',
            'es_critica': True,
            'es_fortaleza': False,
        }
    elif puntaje < 70:
        return {
            'clave': 'medio',
            'etiqueta': 'Medio',
            'es_critica': False,
            'es_fortaleza': False,
        }
    elif puntaje < 85:
        return {
            'clave': 'medio_alto',
            'etiqueta': 'Medio – Alto',
            'es_critica': False,
            'es_fortaleza': False,
        }
    else:
        return {
            'clave': 'alto',
            'etiqueta': 'Alto' if puntaje < 95 else 'Muy alto (Fortaleza principal)',
            'es_critica': False,
            'es_fortaleza': True,
        }


def _nivel_clave(puntaje: float) -> str:
    """Retorna solo la clave del nivel para indexar en diccionarios."""
    if puntaje < 40:
        return 'muy_bajo'
    elif puntaje < 55:
        return 'bajo'
    elif puntaje < 70:
        return 'medio'
    elif puntaje < 85:
        return 'medio_alto'
    else:
        return 'alto'


# ---------------------------------------------------------------------------
# Generadores de contenido
# ---------------------------------------------------------------------------

def generar_analisis_global(puntajes: dict) -> str:
    """
    Genera el párrafo de análisis general del estudiante.
    puntajes: {'matematicas': X, 'lectura': X, 'sociales': X, 'naturales': X, 'ingles': X}
    """
    areas = {k: v for k, v in puntajes.items() if k != 'global'}
    if not areas:
        return "No hay datos suficientes para generar un análisis."

    ordenadas = sorted(areas.items(), key=lambda x: x[1], reverse=True)
    mejor_area, mejor_puntaje = ordenadas[0]
    peor_area, peor_puntaje = ordenadas[-1]

    nombre_mejor = AREAS_CONFIG.get(mejor_area, {}).get('nombre', mejor_area)
    nombre_peor = AREAS_CONFIG.get(peor_area, {}).get('nombre', peor_area)

    nivel_mejor = clasificar_nivel(mejor_puntaje)
    nivel_peor = clasificar_nivel(peor_puntaje)

    # Identificar áreas críticas
    criticas = [
        AREAS_CONFIG.get(a, {}).get('nombre', a)
        for a, p in areas.items()
        if clasificar_nivel(p)['es_critica']
    ]

    # Identificar fortalezas
    fortalezas = [
        AREAS_CONFIG.get(a, {}).get('nombre', a)
        for a, p in areas.items()
        if clasificar_nivel(p)['es_fortaleza']
    ]

    partes = []

    if fortalezas:
        lista_f = ' y '.join(fortalezas)
        partes.append(
            f"El estudiante presenta un rendimiento destacado en {lista_f}, "
            f"lo cual representa una ventaja competitiva importante."
        )
    elif nivel_mejor['clave'] in ('medio_alto', 'alto'):
        partes.append(
            f"El área con mejor desempeño es {nombre_mejor} con un puntaje de "
            f"{int(mejor_puntaje)}, mostrando buen nivel relativo."
        )
    else:
        partes.append(
            f"El perfil general muestra oportunidades de mejora en todas las áreas, "
            f"con {nombre_mejor} como el componente más sólido actualmente."
        )

    if criticas:
        lista_c = ' y '.join(criticas)
        partes.append(
            f"Sin embargo, existen oportunidades claras de mejora en {lista_c}, "
            f"que están afectando el puntaje global y requieren atención prioritaria."
        )
    elif nivel_peor['clave'] == 'medio':
        partes.append(
            f"El área con mayor margen de mejora es {nombre_peor} ({int(peor_puntaje)} puntos), "
            f"aunque el perfil general es equilibrado."
        )

    return ' '.join(partes)


def generar_recomendaciones_area(area: str, puntaje: float) -> dict:
    """
    Genera el bloque de recomendaciones para un área específica.
    Retorna dict con: nombre, emoji, puntaje, nivel, fortalezas, recomendaciones, es_critica, es_fortaleza.
    """
    config = AREAS_CONFIG.get(area, {})
    nivel_info = clasificar_nivel(puntaje)
    clave = _nivel_clave(puntaje)

    return {
        'area': area,
        'nombre': config.get('nombre', area.capitalize()),
        'emoji': config.get('emoji', '•'),
        'puntaje': puntaje,
        'nivel': nivel_info['etiqueta'],
        'es_critica': nivel_info['es_critica'],
        'es_fortaleza': nivel_info['es_fortaleza'],
        'fortalezas': config.get('fortalezas', {}).get(clave, []),
        'recomendaciones': config.get('recomendaciones', {}).get(clave, []),
    }


def generar_plan_tiempo(puntajes: dict) -> list:
    """
    Genera el plan de distribución de tiempo de estudio
    basado en el perfil de puntajes del alumno.
    """
    areas = {k: v for k, v in puntajes.items() if k != 'global'}
    if not areas:
        return []

    criticas = [
        AREAS_CONFIG.get(a, {}).get('nombre', a)
        for a, p in areas.items()
        if clasificar_nivel(p)['es_critica']
    ]
    fortalezas = [
        AREAS_CONFIG.get(a, {}).get('nombre', a)
        for a, p in areas.items()
        if clasificar_nivel(p)['es_fortaleza']
    ]
    medias = [
        AREAS_CONFIG.get(a, {}).get('nombre', a)
        for a, p in areas.items()
        if not clasificar_nivel(p)['es_critica'] and not clasificar_nivel(p)['es_fortaleza']
    ]

    plan = []

    if criticas:
        pct_criticas = 40 if len(fortalezas) > 0 else 50
        plan.append(f"{pct_criticas}% en áreas críticas: {', '.join(criticas)}")
    if medias:
        pct_medias = 30
        plan.append(f"{pct_medias}% en áreas intermedias: {', '.join(medias)}")
    if fortalezas:
        pct_fuertes = 30 if criticas else 50
        plan.append(f"{pct_fuertes}% en fortalezas: {', '.join(fortalezas)} (mantener y optimizar)")
    if not criticas and not fortalezas:
        plan.append("Distribuir el estudio equitativamente entre todas las áreas")
        plan.append("Enfocarse en alcanzar el siguiente nivel en cada componente")

    return plan


def generar_recomendaciones_generales(puntajes: dict) -> list:
    """
    Genera lista de recomendaciones generales aplicables a todos.
    """
    areas = {k: v for k, v in puntajes.items() if k != 'global'}
    puntaje_global = puntajes.get('global', 0)

    recomendaciones = []

    criticas = [k for k, v in areas.items() if clasificar_nivel(v)['es_critica']]
    fortalezas = [k for k, v in areas.items() if clasificar_nivel(v)['es_fortaleza']]

    if criticas:
        nombres = [AREAS_CONFIG.get(a, {}).get('nombre', a) for a in criticas]
        recomendaciones.append(f"Priorizar refuerzo en {' y '.join(nombres)}")

    if fortalezas:
        nombres = [AREAS_CONFIG.get(a, {}).get('nombre', a) for a in fortalezas]
        recomendaciones.append(f"Mantener y potenciar {' y '.join(nombres)} como ventaja competitiva")

    recomendaciones.append("Realizar simulacros cronometrados al menos una vez por semana")
    recomendaciones.append("Revisar los errores de cada simulacro antes del siguiente")

    if puntaje_global < 200:
        recomendaciones.append("Buscar apoyo de un tutor o grupo de estudio para refuerzo intensivo")
    elif puntaje_global >= 350:
        recomendaciones.append("Considerar técnicas de examen: gestión del tiempo y revisión de respuestas")

    recomendaciones.append("Mantener hábitos de sueño y alimentación adecuados en la semana del examen")

    return recomendaciones


def generar_reporte_completo(puntajes: dict) -> dict:
    """
    Función principal. Genera toda la información de análisis y recomendaciones.

    puntajes: {'matematicas': X, 'lectura': X, 'sociales': X, 'naturales': X, 'ingles': X, 'global': X}

    Retorna dict con:
      - analisis_global: str
      - areas: list[dict]  (ordenadas de mayor a menor puntaje)
      - plan_tiempo: list[str]
      - recomendaciones_generales: list[str]
    """
    areas_puntajes = {k: v for k, v in puntajes.items() if k != 'global'}

    # Orden: primero críticas (de peor a mejor), luego medias, luego fortalezas
    def orden_area(item):
        a, p = item
        nivel = clasificar_nivel(p)
        if nivel['es_critica']:
            return (0, p)
        elif nivel['es_fortaleza']:
            return (2, p)
        else:
            return (1, p)

    areas_ordenadas = sorted(areas_puntajes.items(), key=orden_area)

    return {
        'analisis_global': generar_analisis_global(puntajes),
        'areas': [generar_recomendaciones_area(a, p) for a, p in areas_ordenadas],
        'plan_tiempo': generar_plan_tiempo(puntajes),
        'recomendaciones_generales': generar_recomendaciones_generales(puntajes),
    }
