from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from academico.models import Alumno
from cartera.models import Deuda, Cuota
from cartera.forms import CuotaForm, CuotaUpdateForm, GenerarCuotasForm

class CuotaValidationTests(TestCase):
    def setUp(self):
        from ubicaciones.models import Departamento, Municipio, Sede, Salon
        from academico.models import Grupo
        
        self.depto = Departamento.objects.create(nombre="Santander")
        self.muni = Municipio.objects.create(nombre="Bucaramanga", departamento=self.depto)
        self.sede = Sede.objects.create(nombre="Centro", municipio=self.muni)
        self.salon = Salon.objects.create(numero=101, capacidad_sillas=30, sede=self.sede)
        self.grupo = Grupo.objects.create(salon=self.salon, codigo="SANTBUCCEN01")

        # Create a mock Alumno
        self.alumno = Alumno.objects.create(
            nombres="Juan",
            primer_apellido="Perez",
            identificacion="123456789",
            municipio=self.muni,
            grupo_actual=self.grupo
        )
        # Create a mock Deuda
        self.deuda = Deuda.objects.create(
            alumno=self.alumno,
            valor_total=100000,
            saldo_pendiente=100000
        )

    def test_model_clean_prevents_future_fecha_pago(self):
        """Test that setting fecha_pago in the future raises a ValidationError in clean()"""
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        cuota = Cuota(
            deuda=self.deuda,
            monto=50000,
            fecha_vencimiento=timezone.localtime(timezone.now()).date(),
            fecha_pago=tomorrow
        )
        with self.assertRaises(ValidationError) as context:
            cuota.clean()
        self.assertIn('fecha_pago', context.exception.message_dict)
        self.assertEqual(
            context.exception.message_dict['fecha_pago'][0],
            'La fecha de pago no puede ser una fecha futura.'
        )

    def test_model_save_prevents_future_fecha_pago(self):
        """Test that saving a cuota with a future fecha_pago raises ValidationError"""
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        cuota = Cuota(
            deuda=self.deuda,
            monto=50000,
            fecha_vencimiento=timezone.localtime(timezone.now()).date(),
            fecha_pago=tomorrow
        )
        with self.assertRaises(ValidationError):
            cuota.save()

    def test_cuota_form_prevents_future_fecha_pago(self):
        """Test that CuotaForm raises validation error for future fecha_pago"""
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        data = {
            'deuda': self.deuda.id,
            'monto': 50000,
            'monto_abonado': 0,
            'fecha_vencimiento': timezone.localtime(timezone.now()).date().isoformat(),
            'fecha_pago': tomorrow.isoformat(),
            'estado': 'emitida',
            'metodo_pago': 'efectivo',
        }
        form = CuotaForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_pago', form.errors)
        self.assertEqual(form.errors['fecha_pago'][0], 'La fecha de pago no puede ser una fecha futura.')

    def test_cuota_update_form_prevents_future_fecha_pago(self):
        """Test that CuotaUpdateForm raises validation error for future fecha_pago"""
        cuota = Cuota.objects.create(
            deuda=self.deuda,
            monto=50000,
            fecha_vencimiento=timezone.localtime(timezone.now()).date(),
            estado='emitida'
        )
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        data = {
            'monto': 50000,
            'monto_abonado': 10000,
            'fecha_pago': tomorrow.isoformat(),
            'estado': 'pagada_parcial',
            'metodo_pago': 'efectivo',
        }
        form = CuotaUpdateForm(data=data, instance=cuota)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_pago', form.errors)
        self.assertEqual(form.errors['fecha_pago'][0], 'La fecha de pago no puede ser una fecha futura.')

    def test_generar_cuotas_form_prevents_future_fecha_pago_inicial(self):
        """Test that GenerarCuotasForm raises validation error for future fecha_pago_inicial"""
        tomorrow = timezone.localtime(timezone.now()).date() + timedelta(days=1)
        data = {
            'monto_cuota_inicial': 20000,
            'fecha_pago_inicial': tomorrow.isoformat(),
            'metodo_pago_inicial': 'efectivo',
        }
        form = GenerarCuotasForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_pago_inicial', form.errors)
        self.assertEqual(form.errors['fecha_pago_inicial'][0], 'La fecha de pago de la cuota inicial no puede ser una fecha futura.')
