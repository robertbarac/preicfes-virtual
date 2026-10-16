from django.test import RequestFactory
from django.contrib.auth import get_user_model
from evaluaciones.views.simulacros import SimulacroListView

User = get_user_model()
u = User.objects.filter(is_superuser=False).first()
rf = RequestFactory()
req = rf.get(/evaluaciones/simulacros/)
req.user = u
view = SimulacroListView()
view.setup(req)
try:
    resp = view.dispatch(req)
    print(STATUS
