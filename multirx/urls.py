from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from app import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- Public / auth ------------------------------------------------------
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # --- Shared -------------------------------------------------------------
    path('profile/', views.profile_view, name='profile'),
    path('profile/picture/change/', views.profile_picture_change, name='profile_picture_change'),
    path('profile/picture/update/', views.profile_picture_update, name='profile_picture_update'),

    path('patients/', views.search_view, name='search'),
    path('patients/export/', views.export_excel, name='export_excel'),
    path('patient/<int:patient_id>/', views.patient_profile_view, name='patient_profile'),
    path('patient/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
    path('analysis/', views.analysis_view, name='analysis'),

    # --- Administrator ------------------------------------------------------
    path('manage/', views.admin_dashboard, name='admin_dashboard'),
    path('manage/accounts/', views.admin_accounts, name='admin_accounts'),
    path('manage/accounts/new/', views.admin_account_create, name='admin_account_create'),
    path('manage/accounts/<int:account_id>/', views.admin_account_edit, name='admin_account_edit'),
    path('manage/accounts/<int:account_id>/password/', views.admin_account_password, name='admin_account_password'),
    path('manage/accounts/<int:account_id>/toggle/', views.admin_account_toggle, name='admin_account_toggle'),
    path('manage/appointments/', views.admin_appointments, name='admin_appointments'),

    # --- Receptionist -------------------------------------------------------
    path('reception/', views.reception_dashboard, name='reception_dashboard'),
    path('reception/new-patient/', views.reception_new_patient, name='reception_new_patient'),
    path('reception/patient/<int:patient_id>/edit/', views.reception_edit_patient, name='reception_edit_patient'),
    path('reception/appointments/', views.reception_appointments, name='reception_appointments'),
    path('reception/appointments/queue/<int:patient_id>/', views.reception_queue_patient, name='reception_queue_patient'),
    path('reception/appointments/<int:appointment_id>/cancel/', views.reception_cancel_appointment, name='reception_cancel_appointment'),
    path('reception/send-next/', views.reception_send_next, name='reception_send_next'),
    path('reception/calls/dismiss/', views.reception_dismiss_calls, name='reception_dismiss_calls'),
    path('reception/api/queue-state/', views.reception_queue_state, name='reception_queue_state'),

    # --- Doctor -------------------------------------------------------------
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/appointments/', views.doctor_appointments, name='doctor_appointments'),
    path('doctor/next-patient/', views.doctor_next_patient, name='doctor_next_patient'),
    path('doctor/api/queue-state/', views.doctor_queue_state, name='doctor_queue_state'),

    # --- Prescriptions ------------------------------------------------------
    path('prescribe/', views.prescribe_picker, name='prescribe'),
    path('prescribe/<int:patient_id>/', views.prescribe_with_patient, name='prescribe_with_patient'),
    path('prescription/<int:prescription_id>/pdf/', views.prescription_pdf, name='prescription_pdf'),

    # --- Autocomplete -------------------------------------------------------
    path('autocomplete/problem/', views.problem_autocomplete, name='problem_autocomplete'),
    path('autocomplete/report/', views.report_autocomplete, name='report_autocomplete'),
    path('autocomplete/medicine/', views.medicine_autocomplete, name='medicine_autocomplete'),
    path('autocomplete/examination/', views.examination_autocomplete, name='examination_autocomplete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
