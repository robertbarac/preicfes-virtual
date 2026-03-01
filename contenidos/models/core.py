from django.db import models
from django.conf import settings
from curriculo.models import Modulo, Tema

class Post(models.Model):
    ESTADOS = (
        ('borrador', 'Borrador'),
        ('revision', 'En Revisión'),
        ('publicado', 'Publicado'),
        ('oculto', 'Oculto'),
    )
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    creador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='posts_creados')
    
    titulo = models.CharField(max_length=255)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición en el módulo o semana")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['modulo', 'orden']

    def __str__(self):
        return self.titulo

class BloqueContenido(models.Model):
    TIPOS = (
        ('texto', 'Texto/Párrafo'),
        ('imagen', 'Imagen/GIF'),
        ('youtube', 'Video de YouTube'),
        ('enlace', 'Enlace Externo'),
    )
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bloques')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    orden = models.PositiveIntegerField(default=0)
    
    # Campos dinámicos según el tipo de bloque
    contenido_texto = models.TextField(blank=True, null=True, help_text="Para bloques de texto")
    archivo_imagen = models.ImageField(upload_to='contenidos/bloques/', blank=True, null=True, help_text="Para imágenes o GIFs")
    url = models.URLField(blank=True, null=True, help_text="Para YouTube o enlaces externos")

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.post.titulo} - Bloque {self.orden} ({self.tipo})"
        
    @property
    def youtube_embed_url(self):
        """Convierte una URL normal de YouTube a su versión embebible."""
        if not self.url:
            return ""
        import re
        # Extrae el ID de 11 caracteres de URLs como watch?v=ID, youtu.be/ID, embed/ID
        regex = r"(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^\"&?\/\s]{11})"
        match = re.search(regex, self.url)
        if match:
            video_id = match.group(1)
            # Use nocookie domain to bypass strict browser/privacy blocks like Error 153
            return f"https://www.youtube-nocookie.com/embed/{video_id}"
        return self.url

