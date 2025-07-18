from django.contrib import admin
from django.urls import path
from app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),

    # Authenticated users
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('prescribe/', views.prescribe_view, name='prescribe'),
    path('prescription/<int:patient_id>/pdf/', views.prescription_pdf, name='prescription_pdf'),
    path('search/', views.search_view, name='search'),
    path('search/export/', views.export_excel, name='export_excel'),
    path('analysis/', views.analysis_view, name='analysis'),
    path('patient/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
    path('api/medicines/', views.medicine_autocomplete, name='medicine_autocomplete'),

    path("api/problem-meds/", views.problem_to_medicine, name="problem_meds"),

]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
