from django.contrib import admin
from django.urls import path
from app import views
from django.conf import settings
from django.conf.urls.static import static
from app.views import examination_autocomplete, problem_autocomplete, report_autocomplete, medicine_autocomplete

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),

    # Authenticated users
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    
    # Prescription URLs
    path('prescribe/', views.prescribe_view, name='prescribe'),  # New prescription
    path('prescribe/<int:patient_id>/', views.prescribe_with_patient, name='prescribe_with_patient'),
    path('prescription/<int:prescription_id>/pdf/', views.prescription_pdf, name='prescription_pdf'),
    
    # Patient URLs
    path('search/', views.search_view, name='search'),
    path('search/export/', views.export_excel, name='export_excel'),
    path('patient/<int:patient_id>/', views.patient_profile_view, name='patient_profile'),
    path('patient/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
    
    # Analysis
    path('analysis/', views.analysis_view, name='analysis'),
    
    # API
    path('api/medicines/', views.medicine_autocomplete, name='medicine_autocomplete'),

    # Auto Complete
    path('autocomplete/problem/', problem_autocomplete, name='problem_autocomplete'),
    path('autocomplete/report/', report_autocomplete, name='report_autocomplete'),
    path('autocomplete/medicine/', medicine_autocomplete, name='medicine_autocomplete'),
    path('autocomplete/examination/', examination_autocomplete, name='examination_autocomplete'),

    path('profile/picture/change/', views.profile_picture_change, name='profile_picture_change'),
    path('profile/picture/update/', views.profile_picture_update, name='profile_picture_update'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)