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
