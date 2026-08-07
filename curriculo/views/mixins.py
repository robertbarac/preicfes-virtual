from django.contrib.contenttypes.models import ContentType
from curriculo.models import HistorialCambios

class HistorialMixin:
    """
    Mixin para registrar automáticamente la creación y modificación 
    de objetos en el HistorialCambios.
    """
    def get_historial_descripcion(self, form, is_creation):
        """Puede ser sobreescrito para dar mensajes más detallados"""
        if is_creation:
            return f"Creación inicial de {self.model._meta.verbose_name}"
        else:
            changed_data = form.changed_data
            if changed_data:
                return f"Se modificaron los campos: {', '.join(changed_data)}"
            return "Se actualizó el registro sin cambios aparentes"

    def register_history(self, objeto, accion, descripcion):
        if self.request.user.is_authenticated:
            content_type = ContentType.objects.get_for_model(objeto)
            HistorialCambios.objects.create(
                usuario=self.request.user,
                content_type=content_type,
                object_id=objeto.pk,
                accion=accion,
                descripcion=descripcion
            )

    def form_valid(self, form):
        is_creation = getattr(self, 'object', None) is None
        
        # Check if this is a DeleteView (usually has delete method and get_success_url)
        # In Django 4+, DeleteView form_valid deletes the object
        is_deletion = hasattr(self, 'get_success_url') and not hasattr(form, 'save')

        if is_deletion:
            objeto = self.object
            pk = objeto.pk
            descripcion = f"Eliminación de {objeto._meta.verbose_name}"
            # Record history BEFORE calling super().form_valid(form) which deletes the object
            if self.request.user.is_authenticated:
                content_type = ContentType.objects.get_for_model(objeto)
                HistorialCambios.objects.create(
                    usuario=self.request.user,
                    content_type=content_type,
                    object_id=pk,
                    accion="Eliminación",
                    descripcion=descripcion
                )
            return super().form_valid(form)
        else:
            response = super().form_valid(form)
            accion = "Creación" if is_creation else "Modificación"
            descripcion = self.get_historial_descripcion(form, is_creation)
            self.register_history(self.object, accion, descripcion)
            return response

    def post(self, request, *args, **kwargs):
        """Intercepts POST requests (like in DeleteView) to log history BEFORE deletion."""
        # For DeleteView, there is usually no form, and it exposes a 'delete' method.
        # But we intercept 'post' since DeleteView.post() calls delete()
        if hasattr(self, 'get_success_url') and hasattr(self, 'delete') and not hasattr(self, 'get_form_class'):
            self.object = self.get_object()
            if self.request.user.is_authenticated:
                content_type = ContentType.objects.get_for_model(self.object)
                descripcion = f"Eliminación de {self.object._meta.verbose_name}"
                HistorialCambios.objects.create(
                    usuario=self.request.user,
                    content_type=content_type,
                    object_id=self.object.pk,
                    accion="Eliminación",
                    descripcion=descripcion
                )
            # Proceed with the actual delete
            return super().post(request, *args, **kwargs)
        
        # If it's not a DeleteView, proceed normally
        return super().post(request, *args, **kwargs)


from django.contrib.auth.mixins import UserPassesTestMixin

class ProgramaVisibilidadMixin(UserPassesTestMixin):
    """
    Bloquea el acceso si el usuario no está inscrito en el programa
    al que pertenece el recurso solicitado, o si el Ciclo no es visible.
    Staff y superuser pasan siempre.
    """
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
            
        try:
            programa = self._resolver_programa()
            if not programa:
                return True
                
            # Verificar acceso según rol/grupo
            if user.es_docente:
                tiene_acceso = (
                    user.has_perm('evaluaciones.view_taller') or
                    user.has_perm('evaluaciones.change_taller') or
                    user.programas_docente.filter(id=programa.id).exists() or
                    user.clases.filter(materia__programas=programa).exists()
                )
            else:
                # Alumno: debe ser su programa asignado y tener suscripción activa
                from suscripciones.models import Subscription
                from django.utils import timezone
                hoy = timezone.now().date()
                suscripcion_activa = user.subscriptions.filter(active=True, end_date__gte=hoy).exists()
                tiene_acceso = (suscripcion_activa and user.programa_id == programa.id)
                
            if not tiene_acceso:
                return False
                
            ciclo = self._resolver_ciclo()
            if ciclo and not ciclo.visible:
                # Si el ciclo no está visible, solo profesores de ese programa o admins pueden entrar
                if not user.es_docente:
                    return False

            modulo = self._resolver_modulo()
            if modulo and not modulo.activo:
                # Si el módulo no está activo, solo profesores de ese programa o admins pueden entrar
                if not user.es_docente:
                    return False
                
            return True
        except Exception:
            return False

    def _resolver_programa(self):
        raise NotImplementedError("Las vistas que usen ProgramaVisibilidadMixin deben implementar _resolver_programa")

    def _resolver_ciclo(self):
        return None

    def _resolver_modulo(self):
        return None

