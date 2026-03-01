from django import forms
from .models import Post, BloqueContenido

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['titulo', 'modulo', 'tema', 'estado', 'orden']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
            'modulo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'tema': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'estado': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
        }

class BloqueContenidoForm(forms.ModelForm):
    class Meta:
        model = BloqueContenido
        fields = ['tipo', 'orden', 'contenido_texto', 'archivo_imagen', 'url']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'orden': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'contenido_texto': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none', 'rows': 5}),
            'archivo_imagen': forms.ClearableFileInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded outline-none'}),
            'url': forms.URLInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:border-indigo-500 outline-none'}),
        }
