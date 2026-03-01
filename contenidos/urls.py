from django.urls import path
from .views.posts import PostListView, PostCreateView, PostDetailView, PostUpdateView, PostDeleteView
from .views.bloques import BloqueContenidoCreateView, BloqueContenidoUpdateView, BloqueContenidoDeleteView

app_name = 'contenidos'

urlpatterns = [
    # CRUD de Posts
    path('', PostListView.as_view(), name='post_list'),
    path('crear/', PostCreateView.as_view(), name='post_create'),
    path('<int:pk>/', PostDetailView.as_view(), name='post_detail'),
    path('<int:pk>/editar/', PostUpdateView.as_view(), name='post_update'),
    path('<int:pk>/eliminar/', PostDeleteView.as_view(), name='post_delete'),
    
    # CRUD de Bloques
    path('<int:post_pk>/bloque/crear/', BloqueContenidoCreateView.as_view(), name='bloque_create'),
    path('bloque/<int:pk>/editar/', BloqueContenidoUpdateView.as_view(), name='bloque_update'),
    path('bloque/<int:pk>/eliminar/', BloqueContenidoDeleteView.as_view(), name='bloque_delete'),
]
