from django.db import models
from django.conf import settings
from curriculo.models import Tema
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
from django.utils.html import strip_tags

# ─── Bloque de Contexto ───────────────────────────────────────────────────────

class BloqueContexto(models.Model):
    """
    Texto/imágenes de contexto compartido por varias preguntas.
    Ej: "Responda las preguntas 10-12 con base en el siguiente fragmento:"
    No se califica; solo sirve como material de lectura para el estudiante.
    """
    materia = models.ForeignKey(
        'curriculo.Materia', on_delete=models.CASCADE,
        related_name="bloques_contexto", null=True, blank=True,
        help_text="Materia a la que pertenece este contexto."
    )
    texto = models.TextField(
        blank=True,
        help_text="Contenido HTML del bloque (acepta negritas, cursivas, etc.)."
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Bloque de Contexto"
        verbose_name_plural = "Bloques de Contexto"

    def __str__(self):
        materia_nombre = self.materia.nombre if self.materia else "Sin materia"
        texto_limpio = strip_tags(self.texto or "")
        fragmento = (texto_limpio[:60] + "...") if len(texto_limpio) > 60 else texto_limpio
        if not fragmento.strip():
            fragmento = f"Bloque #{self.pk}"
        return f"[{materia_nombre}] {fragmento}"


class ImagenContexto(models.Model):
    """Imagen asociada a un BloqueContexto."""
    bloque = models.ForeignKey(
        BloqueContexto, on_delete=models.CASCADE, related_name="imagenes"
    )
    imagen = models.ImageField(upload_to="evaluaciones/contextos/")
    descripcion = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Ej: 'Figura 1'"
    )
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def save(self, *args, **kwargs):
        if self.imagen:
            img = Image.open(self.imagen)
            img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            name = os.path.splitext(self.imagen.name)[0] + ".jpg"
            self.imagen.save(name, ContentFile(buffer.read()), save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen de Bloque #{self.bloque_id}"


# ─── Pregunta ─────────────────────────────────────────────────────────────────

class Pregunta(models.Model):
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True, related_name="preguntas")
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="preguntas_creadas")
    bloque_contexto = models.ForeignKey(
        BloqueContexto, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="preguntas",
        help_text="Bloque de lectura/contexto que precede a esta pregunta (opcional)."
    )
    enunciado = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pregunta {self.id} - {self.tema}"

class ImagenPregunta(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.ImageField(upload_to="evaluaciones/preguntas/")
    descripcion = models.CharField(max_length=255, blank=True, null=True, help_text="Descripción opcional (Ej: Figura 1)")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden"]

    def save(self, *args, **kwargs):
        if self.imagen:
            img = Image.open(self.imagen)
            img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            name = os.path.splitext(self.imagen.name)[0] + ".jpg"
            self.imagen.save(name, ContentFile(buffer.read()), save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Imagen para Pregunta {self.pregunta_id}"

class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, on_delete=models.CASCADE, related_name="opciones")
    texto = models.TextField(blank=True, null=True)
    imagen = models.ImageField(upload_to="evaluaciones/opciones/", blank=True, null=True)
    es_correcta = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.imagen:
            img = Image.open(self.imagen)
            img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)
            name = os.path.splitext(self.imagen.name)[0] + ".jpg"
            self.imagen.save(name, ContentFile(buffer.read()), save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Opción de Pregunta {self.pregunta_id}"
