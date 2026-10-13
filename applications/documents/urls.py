from django.urls import path

from applications.documents import views

app_name = "documents"
urlpatterns = [
    path("", views.mes_documents, name="mes_documents"),
    path("<int:pk>/apercu/", views.apercu_document, name="apercu"),
    path("<int:pk>/telecharger/", views.telecharger_document, name="telecharger"),
]
