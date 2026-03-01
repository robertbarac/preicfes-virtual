from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from contenidos.models import Post
from contenidos.forms import PostForm
from curriculo.views.mixins import HistorialMixin
from curriculo.models import Materia, Tema

class PostListView(ListView):
    model = Post
    template_name = 'contenidos/post_list.html'
    context_object_name = 'posts'

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros opcionales
        materia_id = self.request.GET.get('materia')
        tema_id = self.request.GET.get('tema')
        
        if materia_id:
            queryset = queryset.filter(tema__materia_id=materia_id)
        if tema_id:
            queryset = queryset.filter(tema_id=tema_id)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materias'] = Materia.objects.all().order_by('nombre')
        context['temas'] = Tema.objects.all().order_by('materia__nombre', 'nombre')
        context['current_materia'] = self.request.GET.get('materia', '')
        context['current_tema'] = self.request.GET.get('tema', '')
        return context

class PostDetailView(DetailView):
    model = Post
    template_name = 'contenidos/post_detail.html'
    context_object_name = 'post'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Traemos los bloques ordenados automáticamente por la Meta ordering del modelo
        context['bloques'] = self.object.bloques.all()
        return context

class PostCreateView(HistorialMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'contenidos/post_form.html'
    
    def get_initial(self):
        initial = super().get_initial()
        modulo_id = self.request.GET.get('modulo')
        if modulo_id:
            initial['modulo'] = modulo_id
        return initial
    
    def get_success_url(self):
        return reverse_lazy('contenidos:post_list')

class PostUpdateView(HistorialMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'contenidos/post_form.html'

    def get_success_url(self):
        return reverse_lazy('contenidos:post_detail', kwargs={'pk': self.object.pk})

class PostDeleteView(DeleteView):
    model = Post
    template_name = 'contenidos/post_confirm_delete.html'
    success_url = reverse_lazy('contenidos:post_list')
