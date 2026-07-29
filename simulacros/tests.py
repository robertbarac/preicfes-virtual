from django.test import TestCase
from django.urls import reverse
from academico.models import Alumno, Grupo
from ubicaciones.models import Municipio, Departamento, Sede, Salon
from simulacros.models import SimulacroDiagnostico, ResultadoSimulacroDiagnostico
from simulacros.calculos import calificar, calcular_puntaje_icfes


class SimulacroDiagnosticoTestCase(TestCase):
    def setUp(self):
        self.sim = SimulacroDiagnostico.objects.create(
            nombre="Diagnóstico 2026-1",
            soluciones="A" * 90,
            puntos_corte={"cortes": [18, 36, 54, 72]}
        )
        dep = Departamento.objects.create(nombre="Córdoba")
        mun = Municipio.objects.create(nombre="Montería", departamento=dep)
        sede = Sede.objects.create(nombre="Central", municipio=mun)
        salon = Salon.objects.create(numero="101", sede=sede)
        self.grupo = Grupo.objects.create(codigo="GR-DIAG", salon=salon)
        self.alumno = Alumno.objects.create(
            nombres="Carlos", primer_apellido="Pérez", identificacion="909090",
            grupo_actual=self.grupo, municipio=mun
        )

    def test_componentes_por_defecto(self):
        self.assertEqual(
            self.sim.get_componentes(),
            ["matematicas", "lectura", "sociales", "naturales", "ingles"]
        )

    def test_calificacion_diagnostico_90_preguntas(self):
        resp_estudiante = "A" * 90
        cortes = [18, 36, 54, 72]
        componentes = self.sim.get_componentes()
        
        comp_results = calificar(resp_estudiante, self.sim.soluciones, cortes, componentes)
        puntajes = calcular_puntaje_icfes(comp_results)
        
        self.assertEqual(puntajes['global'], 500)
        self.assertEqual(puntajes['matematicas'], 100)
        self.assertEqual(puntajes['ingles'], 100)

    def test_resultado_diagnostico_model(self):
        res = ResultadoSimulacroDiagnostico.objects.create(
            alumno=self.alumno,
            simulacro=self.sim,
            respuestas="A" * 90,
            puntaje_global=500
        )
        self.assertEqual(res.estado, "Calificado")

    def test_urls_diagnostico(self):
        url_calificar = reverse('simulacros:grupo_calificar_diagnostico', kwargs={'grupo_id': self.grupo.id})
        url_revisar = reverse('simulacros:revisar_diagnostico')
        self.assertEqual(url_calificar, f"/simulacros/grupo/{self.grupo.id}/calificar-diagnostico/")
        self.assertEqual(url_revisar, "/simulacros/revisar-diagnostico/")

