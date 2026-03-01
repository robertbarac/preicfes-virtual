from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, UpdateView, DeleteView
from ..models import BloqueContenido, Post
from ..forms import BloqueContenidoForm
from curriculo.views.mixins import HistorialMixin

class BloqueContenidoCreateView(HistorialMixin, CreateView):
    model = BloqueContenido
    form_class = BloqueContenidoForm
    template_name = 'contenidos/bloque_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post'] = get_object_or_404(Post, pk=self.kwargs['post_pk'])
        return context

    def form_valid(self, form):
        post = get_object_or_404(Post, pk=self.kwargs['post_pk'])
        form.instance.post = post
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contenidos:post_detail', kwargs={'pk': self.kwargs['post_pk']})

class BloqueContenidoUpdateView(HistorialMixin, UpdateView):
    model = BloqueContenido
    form_class = BloqueContenidoForm
    template_name = 'contenidos/bloque_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post'] = self.object.post
        return context

    def get_success_url(self):
        return reverse('contenidos:post_detail', kwargs={'pk': self.object.post.pk})

class BloqueContenidoDeleteView(HistorialMixin, DeleteView):
    model = BloqueContenido
    template_name = 'contenidos/bloque_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['post'] = self.object.post
        return context

    def get_success_url(self):
        return reverse('contenidos:post_detail', kwargs={'pk': self.object.post.pk})
