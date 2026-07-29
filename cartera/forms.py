from django import forms
from django.shortcuts import get_object_or_404
from .models import Deuda, Cuota, AcuerdoPago
from ubicaciones.models import Departamento, Municipio
from django.core.validators import MinValueValidator

class DeudaForm(forms.ModelForm):
    class Meta:
        model = Deuda
        fields = ['alumno', 'valor_total', 'saldo_pendiente', 'estado']  # Actualizando los campos

class CuotaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date().isoformat()
        if 'fecha_pago' in self.fields:
            self.fields['fecha_pago'].widget.attrs['max'] = today

    def clean_fecha_pago(self):
        fecha_pago = self.cleaned_data.get('fecha_pago')
        if fecha_pago:
            from django.utils import timezone
            today = timezone.localtime(timezone.now()).date()
            if fecha_pago > today:
                raise forms.ValidationError("La fecha de pago no puede ser una fecha futura.")
        return fecha_pago

    class Meta:
        model = Cuota
        fields = ['deuda', 'monto', 'monto_abonado', 'fecha_vencimiento', 'fecha_pago', 'estado', 'metodo_pago']  # Incluir fecha_pago

class CuotaUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['monto'].disabled = True
        
        # Restringir fecha_pago a la fecha actual como máximo
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date().isoformat()
        if 'fecha_pago' in self.fields:
            self.fields['fecha_pago'].widget.attrs['max'] = today

    def clean_fecha_pago(self):
        fecha_pago = self.cleaned_data.get('fecha_pago')
        if fecha_pago:
            from django.utils import timezone
            today = timezone.localtime(timezone.now()).date()
            if fecha_pago > today:
                raise forms.ValidationError("La fecha de pago no puede ser una fecha futura.")
        return fecha_pago

    def clean(self):
        cleaned_data = super().clean()
        monto_abonado = cleaned_data.get('monto_abonado') or 0
        metodo_pago = cleaned_data.get('metodo_pago')
        soporte_pago = cleaned_data.get('soporte_pago')

        # Si se registra un pago por transferencia, exigir imagen de soporte de pago
        if monto_abonado > 0 and metodo_pago == 'transferencia':
            if not soporte_pago and not (self.instance and self.instance.soporte_pago):
                raise forms.ValidationError({
                    'soporte_pago': 'Para pagos por transferencia es obligatorio adjuntar la evidencia / comprobante de pago.'
                })
        return cleaned_data

    class Meta:
        model = Cuota
        fields = ['monto', 'monto_abonado', 'fecha_pago', 'estado', 'metodo_pago', 'soporte_pago']
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
            'monto_abonado': forms.NumberInput(attrs={'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
            'estado': forms.Select(attrs={'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
            'metodo_pago': forms.Select(attrs={'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
            'soporte_pago': forms.FileInput(attrs={'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'}),
        }


class AcuerdoPagoFilterForm(forms.Form):
    estado = forms.ChoiceField(
                choices=[('', 'Todos')] + list(AcuerdoPago.ESTADO_ACUERDO),
        required=False,
        label="Estado del Acuerdo",
        widget=forms.Select(attrs={'class': 'form-select mt-1 block w-full border border-gray-300 rounded-md shadow-sm'})
    )
    departamento = forms.ModelChoiceField(
        queryset=Departamento.objects.all(),
        required=False,
        label="Departamento",
        widget=forms.Select(attrs={'class': 'form-select mt-1 block w-full border border-gray-300 rounded-md shadow-sm'})
    )
    municipio = forms.ModelChoiceField(
        queryset=Municipio.objects.all(),
        required=False,
        label="Municipio",
        widget=forms.Select(attrs={'class': 'form-select mt-1 block w-full border border-gray-300 rounded-md shadow-sm'})
    )
    dias_restantes = forms.IntegerField(
        required=False,
        label="Días Restantes (<=)",
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(attrs={'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm', 'placeholder': 'Ej: 0'})
    )

class GenerarCuotasForm(forms.Form):
    monto_cuota_inicial = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=True,
        label="Monto de la Cuota Inicial",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    fecha_pago_inicial = forms.DateField(
        required=True,
        label="Fecha de Pago de la Cuota Inicial",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    metodo_pago_inicial = forms.ChoiceField(
        choices=Cuota.METODO_PAGO, # Usa la lista del modelo Cuota
        required=True,
        label="Método de Pago de la Cuota Inicial",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.utils import timezone
        today = timezone.localtime(timezone.now()).date().isoformat()
        if 'fecha_pago_inicial' in self.fields:
            self.fields['fecha_pago_inicial'].widget.attrs['max'] = today

    def clean_fecha_pago_inicial(self):
        fecha_pago_inicial = self.cleaned_data.get('fecha_pago_inicial')
        if fecha_pago_inicial:
            from django.utils import timezone
            today = timezone.localtime(timezone.now()).date()
            if fecha_pago_inicial > today:
                raise forms.ValidationError("La fecha de pago de la cuota inicial no puede ser una fecha futura.")
        return fecha_pago_inicial

class AcuerdoPagoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        cuota_pk = kwargs.pop('cuota_pk', None)
        super().__init__(*args, **kwargs)
        if cuota_pk:
            self.cuota = get_object_or_404(Cuota, pk=cuota_pk)
        else:
            # En modo de edición, la cuota se obtiene de la instancia
            if self.instance and self.instance.pk:
                self.cuota = self.instance.cuota
            else:
                self.cuota = None

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cuota:
            instance.cuota = self.cuota
        if commit:
            instance.save()
        return instance
    class Meta:
        model = AcuerdoPago
        fields = ['fecha_prometida_pago', 'nota']
        widgets = {
            'fecha_prometida_pago': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm'}
            ),
            'nota': forms.Textarea(
                attrs={'rows': 3, 'class': 'mt-1 block w-full border border-gray-300 rounded-md shadow-sm'}
            ),
        }
