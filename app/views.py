import json
import os
from calendar import month_name
from functools import wraps

import openpyxl
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.db.models.functions import ExtractMonth, ExtractYear, TruncDay
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from weasyprint import CSS, HTML

from .forms import (
    AccountPasswordForm,
    AppointmentForm,
    ClinicalResearchDataForm,
    LoginForm,
    ManagedAccountForm,
    PatientAssignmentForm,
    PatientForm,
    ProfilePictureForm,
    ProfileUpdateForm,
)
from .models import (
    ROLE_ADMIN,
    ROLE_CHOICES,
    ROLE_DOCTOR,
    ROLE_RECEPTIONIST,
    Appointment,
    ClinicalResearchData,
    Doctor,
    Examination,
    Medicine,
    MedicineMaster,
    Patient,
    PatientCall,
    Prescription,
    Problem,
    Report,
    ReportImage,
)


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------

def role_home_url(user):
    """Landing page for a signed-in user, based on their role."""
    if not user.is_authenticated:
        return 'login'
    if user.is_admin:
        return 'admin_dashboard'
    if user.is_receptionist:
        return 'reception_dashboard'
    return 'doctor_dashboard'


def doctor_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_doctor:
            messages.error(request, "That section is only available to doctors.")
            return redirect(role_home_url(request.user))
        return view_func(request, *args, **kwargs)
    return _wrapped


def receptionist_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_receptionist:
            messages.error(request, "That section is only available to receptionists.")
            return redirect(role_home_url(request.user))
        return view_func(request, *args, **kwargs)
    return _wrapped


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_admin:
            messages.error(request, "That section is only available to administrators.")
            return redirect(role_home_url(request.user))
        return view_func(request, *args, **kwargs)
    return _wrapped


def patients_for(user):
    """Administrators and receptionists work with every patient of the clinic;
    a doctor only sees the patients registered under them."""
    if user.is_doctor:
        return Patient.objects.filter(doctor=user)
    return Patient.objects.all()


def prescriptions_for(user):
    return Prescription.objects.filter(patient__in=patients_for(user))


def _serial_label(value):
    return f"{value:02d}"


# ---------------------------------------------------------------------------
# Public / auth
# ---------------------------------------------------------------------------

def home_view(request):
    if request.user.is_authenticated:
        return redirect(role_home_url(request.user))
    return render(request, 'app/home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect(role_home_url(request.user))

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login_id = form.cleaned_data['doctor_id']
            password = form.cleaned_data['password']
            user = authenticate(request, doctor_id=login_id, password=password)

            if user is not None:
                login(request, user)
                messages.success(
                    request,
                    f"Signed in as {user.display_name} ({user.role_label})."
                )
                return redirect(role_home_url(user))
            form.add_error(None, "Invalid login ID or password.")
    else:
        form = LoginForm()

    return render(request, 'app/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard_redirect(request):
    return redirect(role_home_url(request.user))


# ---------------------------------------------------------------------------
# Profile (shared by both roles)
# ---------------------------------------------------------------------------

@login_required
def profile_view(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            if 'profile_picture' in request.FILES and user.profile_picture:
                user.profile_picture.delete(save=False)
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile')
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileUpdateForm(instance=user)

    today = timezone.localdate()
    if user.is_doctor:
        stats = {
            'patients': Patient.objects.filter(doctor=user).count(),
            'prescriptions': Prescription.objects.filter(patient__doctor=user).count(),
            'today_appointments': Appointment.objects.filter(doctor=user, date=today).count(),
        }
    elif user.is_admin:
        stats = {
            'accounts': Doctor.objects.count(),
            'patients': Patient.objects.count(),
            'prescriptions': Prescription.objects.count(),
        }
    else:
        stats = {
            'patients': Patient.objects.filter(registered_by=user).count(),
            'appointments': Appointment.objects.filter(created_by=user).count(),
            'today_appointments': Appointment.objects.filter(
                created_by=user, date=today).count(),
        }

    return render(request, 'app/profile.html', {
        'form': form,
        'doctor': user,
        'account': user,
        'stats': stats,
    })


@login_required
def profile_picture_change(request):
    return render(request, 'app/profile_pic_change.html', {'form': ProfilePictureForm()})


@login_required
def profile_picture_update(request):
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            if request.user.profile_picture:
                old_file = request.user.profile_picture.path
                if os.path.exists(old_file):
                    os.remove(old_file)
            form.save()
            messages.success(request, "Profile picture updated successfully.")
            return redirect('profile')
        messages.error(request, "Please choose a valid image.")
        return render(request, 'app/profile_pic_change.html', {'form': form})
    return redirect('profile_picture_change')


# ---------------------------------------------------------------------------
# Receptionist system
# ---------------------------------------------------------------------------

@receptionist_required
def reception_dashboard(request):
    today = timezone.localdate()
    todays = Appointment.objects.filter(date=today).select_related('patient', 'doctor')

    context = {
        'today': today,
        'total_patients': Patient.objects.count(),
        'registered_today': Patient.objects.filter(created_at__date=today).count(),
        'waiting_count': todays.filter(status=Appointment.STATUS_WAITING).count(),
        'in_consultation': todays.filter(status=Appointment.STATUS_IN_CONSULTATION)
                                 .order_by('doctor_id', 'serial'),
        'completed_count': todays.filter(status=Appointment.STATUS_COMPLETED).count(),
        'next_up': todays.filter(status=Appointment.STATUS_WAITING).order_by('serial')[:5],
        'recent_patients': Patient.objects.select_related('doctor')
                                          .order_by('-created_at')[:6],
        'doctors': Doctor.objects.doctors().order_by('first_name', 'doctor_id'),
        'pending_calls': PatientCall.objects.filter(acknowledged=False)
                                            .select_related('doctor').count(),
    }
    return render(request, 'app/reception/dashboard.html', context)


@receptionist_required
def reception_new_patient(request):
    """Register a patient: demographics + the full Additional Patient Record,
    with an optional "add to today's queue" step in one submit."""
    available_doctors = Doctor.objects.doctors().exists()

    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        assignment_form = PatientAssignmentForm(request.POST)
        research_form = ClinicalResearchDataForm(request.POST)

        if patient_form.is_valid() and assignment_form.is_valid() and research_form.is_valid():
            with transaction.atomic():
                patient = patient_form.save(commit=False)
                patient.doctor = assignment_form.cleaned_data['doctor']
                patient.registered_by = request.user
                patient.save()

                research = research_form.save(commit=False)
                research.patient = patient
                research.save()

                appointment = None
                if request.POST.get('add_to_queue') == '1':
                    appointment = _create_appointment(
                        patient=patient,
                        doctor=patient.doctor,
                        created_by=request.user,
                        note=request.POST.get('queue_note', '').strip(),
                    )

            if appointment:
                messages.success(
                    request,
                    f"{patient.name} registered and queued as serial "
                    f"#{_serial_label(appointment.serial)} for {appointment.doctor.display_name}."
                )
                return redirect('reception_appointments')

            messages.success(request, f"{patient.name} registered successfully.")
            return redirect('patient_profile', patient_id=patient.id)

        messages.error(request, "Please correct the highlighted fields.")
    else:
        patient_form = PatientForm()
        assignment_form = PatientAssignmentForm()
        research_form = ClinicalResearchDataForm()

    return render(request, 'app/reception/new_patient.html', {
        'patient_form': patient_form,
        'assignment_form': assignment_form,
        'form': research_form,
        'available_doctors': available_doctors,
    })


@receptionist_required
def reception_edit_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    research_instance = getattr(patient, 'research_data', None)

    if request.method == 'POST':
        patient_form = PatientForm(request.POST, instance=patient)
        assignment_form = PatientAssignmentForm(request.POST)
        research_form = ClinicalResearchDataForm(request.POST, instance=research_instance)

        if patient_form.is_valid() and assignment_form.is_valid() and research_form.is_valid():
            with transaction.atomic():
                patient = patient_form.save(commit=False)
                patient.doctor = assignment_form.cleaned_data['doctor']
                patient.save()

                research = research_form.save(commit=False)
                research.patient = patient
                research.save()

            messages.success(request, f"{patient.name}'s record updated.")
            return redirect('patient_profile', patient_id=patient.id)

        messages.error(request, "Please correct the highlighted fields.")
    else:
        patient_form = PatientForm(instance=patient)
        assignment_form = PatientAssignmentForm(initial={'doctor': patient.doctor})
        research_form = ClinicalResearchDataForm(instance=research_instance)

    return render(request, 'app/reception/new_patient.html', {
        'patient_form': patient_form,
        'assignment_form': assignment_form,
        'form': research_form,
        'patient': patient,
        'editing': True,
        'available_doctors': True,
    })


def _create_appointment(patient, doctor, created_by, note=''):
    """Append a patient to a doctor's queue for today, retrying on the rare
    race where two receptionists claim the same serial."""
    today = timezone.localdate()
    for _ in range(5):
        serial = Appointment.next_serial(doctor, today)
        try:
            with transaction.atomic():
                return Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    created_by=created_by,
                    date=today,
                    serial=serial,
                    note=note,
                )
        except IntegrityError:
            # Another desk claimed this serial a moment ago - take the next one.
            continue
    raise RuntimeError("Could not allocate an appointment serial.")


@receptionist_required
def reception_appointments(request):
    today = timezone.localdate()

    doctor_filter = request.GET.get('doctor', '').strip()
    appointments = (Appointment.objects
                    .filter(date=today)
                    .select_related('patient', 'doctor')
                    .order_by('serial'))
    if doctor_filter.isdigit():
        appointments = appointments.filter(doctor_id=int(doctor_filter))

    doctors = Doctor.objects.doctors().order_by('first_name', 'doctor_id')

    doctor_boards = []
    for doctor in doctors:
        if doctor_filter.isdigit() and doctor.id != int(doctor_filter):
            continue
        day = [a for a in appointments if a.doctor_id == doctor.id]
        doctor_boards.append({
            'doctor': doctor,
            'current': next((a for a in day if a.status == Appointment.STATUS_IN_CONSULTATION), None),
            'waiting': [a for a in day if a.status == Appointment.STATUS_WAITING],
            'completed': [a for a in day if a.status == Appointment.STATUS_COMPLETED],
            'cancelled': [a for a in day if a.status == Appointment.STATUS_CANCELLED],
            'pending_call': PatientCall.objects.filter(doctor=doctor, acknowledged=False).exists(),
        })

    add_form = AppointmentForm()

    return render(request, 'app/reception/appointments.html', {
        'today': today,
        'doctor_boards': doctor_boards,
        'doctors': doctors,
        'doctor_filter': doctor_filter,
        'add_form': add_form,
        'searchable_patients': Patient.objects.select_related('doctor').order_by('-created_at')[:200],
    })


@receptionist_required
@require_POST
def reception_queue_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id)
    form = AppointmentForm(request.POST, initial_doctor=patient.doctor)

    if not form.is_valid():
        messages.error(request, "Select a doctor to place this patient with.")
        return redirect(request.POST.get('next') or 'reception_appointments')

    doctor = form.cleaned_data['doctor']
    today = timezone.localdate()

    existing = Appointment.objects.filter(
        patient=patient, date=today,
        status__in=[Appointment.STATUS_WAITING, Appointment.STATUS_IN_CONSULTATION],
    ).first()
    if existing:
        messages.warning(
            request,
            f"{patient.name} is already in today's queue as serial "
            f"#{_serial_label(existing.serial)}."
        )
        return redirect('reception_appointments')

    appointment = _create_appointment(
        patient=patient, doctor=doctor,
        created_by=request.user, note=form.cleaned_data['note'],
    )
    messages.success(
        request,
        f"{patient.name} added to {doctor.display_name}'s queue as serial "
        f"#{_serial_label(appointment.serial)}."
    )
    return redirect('reception_appointments')


@receptionist_required
@require_POST
def reception_send_next(request):
    """Send the next waiting patient in to a doctor and silence the bell."""
    doctor_id = request.POST.get('doctor_id')
    doctor = get_object_or_404(Doctor, id=doctor_id, role='doctor')
    today = timezone.localdate()

    with transaction.atomic():
        busy = Appointment.objects.filter(
            doctor=doctor, date=today, status=Appointment.STATUS_IN_CONSULTATION
        ).first()
        if busy:
            messages.warning(
                request,
                f"{doctor.display_name} is still with serial #{_serial_label(busy.serial)} "
                f"({busy.patient.name})."
            )
            return redirect('reception_appointments')

        nxt = (Appointment.objects
               .filter(doctor=doctor, date=today, status=Appointment.STATUS_WAITING)
               .order_by('serial')
               .first())

        # Acknowledging the calls stops the bell either way.
        for call in PatientCall.objects.filter(doctor=doctor, acknowledged=False):
            call.acknowledge(request.user)

        if not nxt:
            messages.info(request, f"No patients are waiting for {doctor.display_name}.")
            return redirect('reception_appointments')

        nxt.status = Appointment.STATUS_IN_CONSULTATION
        nxt.called_at = timezone.now()
        nxt.save(update_fields=['status', 'called_at'])

    messages.success(
        request,
        f"Serial #{_serial_label(nxt.serial)} ({nxt.patient.name}) sent in to "
        f"{doctor.display_name}."
    )
    return redirect('reception_appointments')


@receptionist_required
@require_POST
def reception_cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    appointment.status = Appointment.STATUS_CANCELLED
    appointment.save(update_fields=['status'])
    messages.success(
        request,
        f"Serial #{_serial_label(appointment.serial)} ({appointment.patient.name}) cancelled."
    )
    return redirect('reception_appointments')


@receptionist_required
@require_POST
def reception_dismiss_calls(request):
    doctor_id = request.POST.get('doctor_id')
    calls = PatientCall.objects.filter(acknowledged=False)
    if doctor_id:
        calls = calls.filter(doctor_id=doctor_id)
    for call in calls:
        call.acknowledge(request.user)
    return JsonResponse({'ok': True})


@receptionist_required
@require_GET
def reception_queue_state(request):
    """Polled by the reception screens: tells the browser when a doctor has
    rung for the next patient, and keeps the board numbers live."""
    today = timezone.localdate()
    calls = (PatientCall.objects
             .filter(acknowledged=False)
             .select_related('doctor', 'finished_appointment__patient'))

    payload_calls = []
    for call in calls:
        finished = call.finished_appointment
        payload_calls.append({
            'id': call.id,
            'doctor_id': call.doctor_id,
            'doctor': call.doctor.display_name,
            'created_at': timezone.localtime(call.created_at).strftime('%I:%M %p'),
            'finished_patient': finished.patient.name if finished else None,
            'finished_serial': _serial_label(finished.serial) if finished else None,
            'waiting': Appointment.objects.filter(
                doctor_id=call.doctor_id, date=today,
                status=Appointment.STATUS_WAITING).count(),
        })

    board = []
    for doctor in Doctor.objects.doctors():
        day = Appointment.objects.filter(doctor=doctor, date=today)
        current = day.filter(status=Appointment.STATUS_IN_CONSULTATION).select_related('patient').first()
        board.append({
            'doctor_id': doctor.id,
            'waiting': day.filter(status=Appointment.STATUS_WAITING).count(),
            'completed': day.filter(status=Appointment.STATUS_COMPLETED).count(),
            'current': {
                'serial': _serial_label(current.serial),
                'patient': current.patient.name,
            } if current else None,
        })

    return JsonResponse({'calls': payload_calls, 'board': board})


# ---------------------------------------------------------------------------
# Doctor system
# ---------------------------------------------------------------------------

@doctor_required
def doctor_dashboard(request):
    today = timezone.localdate()
    day = Appointment.objects.filter(doctor=request.user, date=today).select_related('patient')

    context = {
        'today': today,
        'current': day.filter(status=Appointment.STATUS_IN_CONSULTATION).first(),
        'waiting': day.filter(status=Appointment.STATUS_WAITING).order_by('serial')[:5],
        'waiting_count': day.filter(status=Appointment.STATUS_WAITING).count(),
        'completed_count': day.filter(status=Appointment.STATUS_COMPLETED).count(),
        'total_patients': Patient.objects.filter(doctor=request.user).count(),
        'total_prescriptions': Prescription.objects.filter(patient__doctor=request.user).count(),
        'recent_prescriptions': (Prescription.objects
                                 .filter(patient__doctor=request.user)
                                 .select_related('patient')
                                 .order_by('-created_at')[:6]),
        'call_pending': PatientCall.objects.filter(doctor=request.user, acknowledged=False).exists(),
    }
    return render(request, 'app/doctor/dashboard.html', context)


@doctor_required
def doctor_appointments(request):
    today = timezone.localdate()
    day = (Appointment.objects
           .filter(doctor=request.user, date=today)
           .select_related('patient')
           .order_by('serial'))

    context = {
        'today': today,
        'current': day.filter(status=Appointment.STATUS_IN_CONSULTATION).first(),
        'waiting': day.filter(status=Appointment.STATUS_WAITING),
        'completed': day.filter(status=Appointment.STATUS_COMPLETED).order_by('-completed_at'),
        'cancelled': day.filter(status=Appointment.STATUS_CANCELLED),
        'call_pending': PatientCall.objects.filter(doctor=request.user, acknowledged=False).exists(),
    }
    return render(request, 'app/doctor/appointments.html', context)


def _call_next_patient(doctor):
    """Finish the doctor's current consultation and ring the reception desk."""
    today = timezone.localdate()
    with transaction.atomic():
        current = Appointment.objects.filter(
            doctor=doctor, date=today, status=Appointment.STATUS_IN_CONSULTATION
        ).first()
        if current:
            current.status = Appointment.STATUS_COMPLETED
            current.completed_at = timezone.now()
            current.save(update_fields=['status', 'completed_at'])

        # Collapse any un-answered ring into one, so reception sees a single alert.
        PatientCall.objects.filter(doctor=doctor, acknowledged=False).delete()
        PatientCall.objects.create(doctor=doctor, finished_appointment=current)
    return current


@doctor_required
@require_POST
def doctor_next_patient(request):
    finished = _call_next_patient(request.user)
    waiting = Appointment.objects.filter(
        doctor=request.user, date=timezone.localdate(),
        status=Appointment.STATUS_WAITING,
    ).count()

    if finished:
        messages.success(
            request,
            f"Serial #{_serial_label(finished.serial)} ({finished.patient.name}) completed. "
            f"Reception has been notified."
        )
    else:
        messages.success(request, "Reception has been notified to send the next patient.")

    if not waiting:
        messages.info(request, "No patients are waiting right now.")
    return redirect('doctor_appointments')


@doctor_required
@require_GET
def doctor_queue_state(request):
    today = timezone.localdate()
    day = Appointment.objects.filter(doctor=request.user, date=today)
    current = day.filter(status=Appointment.STATUS_IN_CONSULTATION).select_related('patient').first()
    waiting = day.filter(status=Appointment.STATUS_WAITING).select_related('patient').order_by('serial')

    return JsonResponse({
        'current': {
            'id': current.id,
            'serial': _serial_label(current.serial),
            'patient': current.patient.name,
            'patient_id': current.patient_id,
            'age': current.patient.age,
            'gender': current.patient.gender,
        } if current else None,
        'waiting_count': waiting.count(),
        'waiting': [
            {'serial': _serial_label(a.serial), 'patient': a.patient.name}
            for a in waiting[:10]
        ],
        'call_pending': PatientCall.objects.filter(
            doctor=request.user, acknowledged=False).exists(),
    })


# ---------------------------------------------------------------------------
# Prescriptions (doctor only)
# ---------------------------------------------------------------------------

@doctor_required
def prescribe_picker(request):
    """The doctor prescribes for a registered patient; this page lists today's
    queue plus a search box so a patient can always be found."""
    today = timezone.localdate()
    query = request.GET.get('q', '').strip()

    patients = Patient.objects.filter(doctor=request.user)
    if query:
        patients = patients.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    patients = patients.order_by('-created_at')[:20]

    day = (Appointment.objects
           .filter(doctor=request.user, date=today)
           .exclude(status=Appointment.STATUS_CANCELLED)
           .select_related('patient')
           .order_by('serial'))

    return render(request, 'app/doctor/prescribe_picker.html', {
        'current': day.filter(status=Appointment.STATUS_IN_CONSULTATION).first(),
        'waiting': day.filter(status=Appointment.STATUS_WAITING),
        'patients': patients,
        'query': query,
    })


def _duration_to_days(number, unit):
    if unit == "colbe":
        return 0
    try:
        num = int(number) if str(number).strip() else 1
    except (ValueError, TypeError):
        num = 1
    return {
        "din": num,
        "soptaho": num * 7,
        "mash": num * 30,
        "bosor": num * 365,
    }.get(unit, num)


def _save_prescription_details(request, prescription):
    """Persist the problems / examinations / reports / images / medicines that
    the doctor filled in on the prescription form."""

    for desc in request.POST.getlist('problems'):
        if desc.strip():
            Problem.objects.create(prescription=prescription, description=desc.strip())

    exam_names = request.POST.getlist('examination_names')
    exam_results = request.POST.getlist('examination_results')
    for i, raw_name in enumerate(exam_names):
        name = raw_name.strip()
        if not name:
            continue
        result = exam_results[i].strip() if i < len(exam_results) else ""
        Examination.objects.create(prescription=prescription, name=name, description=result)

    report_names = request.POST.getlist('report_names')
    report_results = request.POST.getlist('report_results')
    for i, raw_name in enumerate(report_names):
        name = raw_name.strip()
        if not name:
            continue
        result = report_results[i].strip() if i < len(report_results) else ""
        Report.objects.create(prescription=prescription, name=name, result=result)

    for image in request.FILES.getlist('report_images'):
        ReportImage.objects.create(prescription=prescription, image=image)

    med_names = request.POST.getlist('medicine_names')
    strengths = request.POST.getlist('medicine_strengths')
    frequencies = request.POST.getlist('medicine_frequencies')
    remarks = request.POST.getlist('medicine_remarks')
    days_numbers = request.POST.getlist('medicine_days_number')
    days_units = request.POST.getlist('medicine_days_unit')

    def at(lst, i, default=""):
        return lst[i] if i < len(lst) else default

    for i, raw_name in enumerate(med_names):
        name = raw_name.strip()
        if not name:
            continue
        Medicine.objects.create(
            prescription=prescription,
            name=name,
            strength=at(strengths, i).strip(),
            frequency=at(frequencies, i).strip(),
            remark=at(remarks, i).strip(),
            days=_duration_to_days(at(days_numbers, i, ""), at(days_units, i, "din")),
        )


@doctor_required
def prescribe_with_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)
    today = timezone.localdate()
    appointment = Appointment.objects.filter(
        patient=patient, doctor=request.user, date=today,
        status__in=[Appointment.STATUS_IN_CONSULTATION, Appointment.STATUS_WAITING],
    ).order_by('status').first()

    if request.method == 'POST':
        with transaction.atomic():
            prescription = Prescription.objects.create(patient=patient, doctor=request.user)
            _save_prescription_details(request, prescription)

            if appointment and appointment.prescription_id is None:
                appointment.prescription = prescription
                appointment.save(update_fields=['prescription'])

        action = request.POST.get('action', 'save_and_download')

        if action == 'save_and_next':
            finished = _call_next_patient(request.user)
            if finished:
                messages.success(
                    request,
                    f"Prescription saved. Serial #{_serial_label(finished.serial)} completed — "
                    f"reception has been notified."
                )
            else:
                messages.success(request, "Prescription saved. Reception has been notified.")
            return redirect('doctor_appointments')

        if action == 'save_and_download':
            return redirect('prescription_pdf', prescription_id=prescription.id)

        messages.success(request, "Prescription saved successfully.")
        return redirect('patient_profile', patient_id=patient.id)

    last_prescription = patient.prescriptions.order_by('-created_at').first()
    last_prescription_data = None
    if last_prescription:
        last_prescription_data = {
            'problems': [p.description for p in last_prescription.problems.all()],
            'examinations': [
                {'name': e.name, 'result': e.description or ''}
                for e in last_prescription.examinations.all()
            ],
            'reports': [
                {'name': r.name, 'result': r.result or ''}
                for r in last_prescription.reports.all()
            ],
            'medicines': [
                {
                    'name': m.name, 'strength': m.strength,
                    'frequency': m.frequency, 'remark': m.remark, 'days': m.days,
                }
                for m in last_prescription.medicines.all()
            ],
        }

    return render(request, 'app/prescribe.html', {
        'patient': patient,
        'appointment': appointment,
        'research_data': getattr(patient, 'research_data', None),
        'last_prescription': last_prescription,
        'last_prescription_data': last_prescription_data,
        'prescription_count': patient.prescriptions.count(),
    })


@login_required
def prescription_pdf(request, prescription_id):
    prescription = get_object_or_404(
        prescriptions_for(request.user)
        .select_related('patient', 'doctor')
        .prefetch_related('problems', 'examinations', 'reports', 'medicines'),
        id=prescription_id,
    )

    now = timezone.localtime(prescription.created_at)
    doctor = prescription.doctor or prescription.patient.doctor

    context = {
        'prescription': prescription,
        'patient': prescription.patient,
        'doctor': doctor,
        'date': now.strftime('%d-%m-%Y'),
        'time': now.strftime('%I:%M %p'),
        'year': now.year,
        'patient_id_formatted': f"P{prescription.patient.id}",
        'prescription_id_formatted': f"Pres{prescription.id}",
        'problems': prescription.problems.all(),
        'examinations': prescription.examinations.all(),
        'reports': prescription.reports.all(),
        'medicines': prescription.medicines.all(),
    }

    html_string = render_to_string('app/prescription_pdf.html', context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri(), encoding='utf-8')

    pdf_file = html.write_pdf(
        stylesheets=[
            CSS(string='''
                @font-face {
                    font-family: 'Tiro Bangla';
                    src: url('/static/fonts/TiroBangla-Regular.ttf') format('truetype');
                }
                body {
                    font-family: 'Tiro Bangla', Arial, sans-serif;
                }
            ''')
        ]
    )

    filename = f"prescription_{prescription.patient.name}_P{prescription.patient.id}_Pres{prescription.id}.pdf"
    filename = filename.replace(" ", "_").replace("/", "-")

    disposition = 'inline' if request.GET.get('view') == '1' else 'attachment'
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# Patient records / search / analysis (shared)
# ---------------------------------------------------------------------------

RESEARCH_COMORBID_FIELDS = {
    'diabetes': 'research_data__comorbid_diabetes',
    'hypertension': 'research_data__comorbid_hypertension',
    'heart_failure': 'research_data__comorbid_heart_failure',
    'ischemic_heart_disease': 'research_data__comorbid_ischemic_heart_disease',
    'peripheral_artery_disease': 'research_data__comorbid_peripheral_artery_disease',
    'stroke': 'research_data__comorbid_stroke',
}

RESEARCH_MEDICATION_FIELDS = {
    'med_esa': 'research_data__med_esa',
    'med_iron': 'research_data__med_iron',
    'med_phosphate_binders': 'research_data__med_phosphate_binders',
    'med_vitamin_d': 'research_data__med_vitamin_d',
    'med_calcimimetics': 'research_data__med_calcimimetics',
    'med_ace_arb': 'research_data__med_ace_arb',
    'med_diuretics': 'research_data__med_diuretics',
    'med_statins': 'research_data__med_statins',
    'med_immunosuppressives': 'research_data__med_immunosuppressives',
}


def apply_research_filters(patient_qs, request):
    """Apply optional patient/demographic + Education/Clinical/KRT/Medication
    filters (from GET params) to a Patient queryset."""

    # --- Demographics (on the Patient model itself) --------------------------
    gender = request.GET.get('gender', '').strip()
    if gender:
        patient_qs = patient_qs.filter(gender=gender)

    age_min = request.GET.get('age_min', '').strip()
    if age_min.isdigit():
        patient_qs = patient_qs.filter(age__gte=int(age_min))

    age_max = request.GET.get('age_max', '').strip()
    if age_max.isdigit():
        patient_qs = patient_qs.filter(age__lte=int(age_max))

    registered_from = request.GET.get('registered_from', '').strip()
    if registered_from:
        patient_qs = patient_qs.filter(created_at__date__gte=registered_from)

    registered_to = request.GET.get('registered_to', '').strip()
    if registered_to:
        patient_qs = patient_qs.filter(created_at__date__lte=registered_to)

    # --- Education / Social ---------------------------------------------------
    education_level = request.GET.get('education_level', '').strip()
    if education_level:
        patient_qs = patient_qs.filter(research_data__education_level=education_level)

    employment_status = request.GET.get('employment_status', '').strip()
    if employment_status:
        patient_qs = patient_qs.filter(research_data__employment_status=employment_status)

    smoking_status = request.GET.get('smoking_status', '').strip()
    if smoking_status:
        patient_qs = patient_qs.filter(research_data__smoking_status=smoking_status)

    # --- Clinical history -------------------------------------------------------
    diagnosis = request.GET.get('diagnosis', '').strip()
    if diagnosis:
        patient_qs = patient_qs.filter(research_data__diagnosis__icontains=diagnosis)

    for param, field_lookup in RESEARCH_COMORBID_FIELDS.items():
        if request.GET.get(param) == '1':
            patient_qs = patient_qs.filter(**{field_lookup: True})

    # --- KRT ---------------------------------------------------------------
    krt_modality = request.GET.get('krt_modality', '').strip()
    if krt_modality:
        patient_qs = patient_qs.filter(research_data__krt_modality=krt_modality)

    vascular_access_type = request.GET.get('vascular_access_type', '').strip()
    if vascular_access_type:
        patient_qs = patient_qs.filter(research_data__vascular_access_type=vascular_access_type)

    krt_initiation_from = request.GET.get('krt_initiation_from', '').strip()
    if krt_initiation_from:
        patient_qs = patient_qs.filter(research_data__krt_initiation_date__gte=krt_initiation_from)

    krt_initiation_to = request.GET.get('krt_initiation_to', '').strip()
    if krt_initiation_to:
        patient_qs = patient_qs.filter(research_data__krt_initiation_date__lte=krt_initiation_to)

    # --- Medication data ---------------------------------------------------
    for param, field_lookup in RESEARCH_MEDICATION_FIELDS.items():
        if request.GET.get(param) == '1':
            patient_qs = patient_qs.filter(**{field_lookup: True})

    return patient_qs.distinct()


def _search_patients(request):
    query = request.GET.get('q', '').strip()
    patient_qs = patients_for(request.user).select_related('doctor').order_by('-created_at')
    exact_id_match = False

    if query:
        # Check for custom ID formats in search (e.g. "P12", "Pres34").
        if query.startswith('Pres'):
            try:
                num = int(query[4:])
                candidate = patient_qs.filter(prescriptions__id=num)
                if candidate.exists():
                    patient_qs = candidate
                    exact_id_match = True
            except (ValueError, IndexError):
                pass
        elif query.upper().startswith('P'):
            try:
                num = int(query[1:])
                candidate = patient_qs.filter(id=num)
                if candidate.exists():
                    patient_qs = candidate
                    exact_id_match = True
            except (ValueError, IndexError):
                pass

        if not exact_id_match:
            patient_qs = patient_qs.filter(
                Q(name__icontains=query) |
                Q(age__icontains=query) |
                Q(phone__icontains=query) |
                Q(address__icontains=query) |
                Q(research_data__diagnosis__icontains=query) |
                Q(prescriptions__problems__description__icontains=query) |
                Q(prescriptions__examinations__description__icontains=query) |
                Q(prescriptions__reports__name__icontains=query) |
                Q(prescriptions__reports__result__icontains=query) |
                Q(prescriptions__medicines__name__icontains=query)
            ).distinct()

    # Advanced filters always apply, even on an exact ID match, so the two
    # can be combined (e.g. "P12" + "Diabetes only").
    return query, apply_research_filters(patient_qs, request)


@login_required
def search_view(request):
    query, patient_qs = _search_patients(request)

    paginator = Paginator(patient_qs, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "results": page_obj,
        "page_obj": page_obj,
        "total_count": patients_for(request.user).count(),
        "search_count": paginator.count,
        "query": query,
        "gender_choices": Patient._meta.get_field('gender').choices,
        "education_choices": ClinicalResearchData.EDUCATION_CHOICES,
        "employment_choices": ClinicalResearchData.EMPLOYMENT_CHOICES,
        "smoking_choices": ClinicalResearchData.SMOKING_CHOICES,
        "modality_choices": ClinicalResearchData.MODALITY_CHOICES,
        "vascular_access_choices": ClinicalResearchData.VASCULAR_ACCESS_CHOICES,
        "selected_filters": request.GET,
        "queue_form": AppointmentForm() if request.user.is_receptionist else None,
    }
    return render(request, "app/search.html", context)


@login_required
def export_excel(request):
    query, patients = _search_patients(request)
    return _generate_excel(patients, query)


def _generate_excel(patients, query=None):
    """Helper function to generate Excel file from patient queryset"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    headers = [
        'Patient ID', 'Name', 'Age', 'Gender', 'Phone', 'Address', 'Doctor', 'Created Date',
        'Prescription IDs', 'Problems', 'Examinations', 'Reports', 'Medicines',
        # Additional Patient Record columns (never shown on the PDF)
        'Education Level', 'Monthly Income', 'Employment Status',
        'Diagnosis', 'Comorbidities', 'Smoking Status', 'BMI', 'Weight (kg)', 'Height (cm)',
        'Serum Creatinine', 'Cystatin C', 'eGFR', 'uACR', 'Protein Levels',
        'Hemoglobin', 'Ferritin', 'Calcium', 'Phosphorus', 'PTH', 'Potassium',
        'Bicarbonate', 'Serum Albumin', 'CRP', 'Total Cholesterol', 'HbA1c',
        'KRT Modality', 'KRT Initiation Date', 'Modality Change Dates', 'Transplant Date',
        'Dialysis Duration', 'Dialysis Frequency', 'Vascular Access Type',
        'Kidney Medications', 'Cardiovascular/Other Medications',
    ]
    ws.append(headers)

    column_widths = [15, 25, 8, 10, 16, 30, 22, 15, 20, 40, 40, 40, 40] + [20] * (len(headers) - 13)
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    patients = patients.select_related('doctor', 'research_data').prefetch_related(
        'prescriptions__problems', 'prescriptions__examinations',
        'prescriptions__reports', 'prescriptions__medicines',
    )

    for patient in patients:
        problems, examinations, reports, medicines, pres_ids = [], [], [], [], []

        for pres in patient.prescriptions.all():
            pres_ids.append(f"Pres{pres.id}")
            problems.extend(p.description for p in pres.problems.all())
            examinations.extend(
                f"{e.name}: {e.description}" if e.description else e.name
                for e in pres.examinations.all()
            )
            reports.extend(f"{r.name}: {r.result}" for r in pres.reports.all())
            medicines.extend(
                f"{m.name} ({m.strength}) - {m.frequency}"
                for m in pres.medicines.all()
            )

        rd = getattr(patient, 'research_data', None)

        def rd_value(attr, default=''):
            if rd is None:
                return default
            value = getattr(rd, attr, default)
            if hasattr(value, 'strftime'):
                return value.strftime('%Y-%m-%d')
            return value if value is not None else default

        ws.append([
            f"P{patient.id}",
            patient.name,
            patient.age,
            patient.gender,
            patient.phone,
            patient.address,
            patient.doctor.display_name if patient.doctor else '',
            timezone.localtime(patient.created_at).strftime('%Y-%m-%d'),
            ", ".join(pres_ids),
            "\n".join(problems),
            "\n".join(examinations),
            "\n".join(reports),
            "\n".join(medicines),
            rd_value('education_level'),
            rd_value('monthly_income'),
            rd_value('employment_status'),
            rd_value('diagnosis'),
            ", ".join(rd.comorbidities_list()) if rd else '',
            rd_value('smoking_status'),
            rd_value('bmi'),
            rd_value('weight'),
            rd_value('height'),
            rd_value('serum_creatinine'),
            rd_value('cystatin_c'),
            rd_value('egfr'),
            rd_value('uacr'),
            rd_value('protein_levels'),
            rd_value('hemoglobin'),
            rd_value('ferritin'),
            rd_value('calcium'),
            rd_value('phosphorus'),
            rd_value('pth'),
            rd_value('potassium'),
            rd_value('bicarbonate'),
            rd_value('serum_albumin'),
            rd_value('crp'),
            rd_value('total_cholesterol'),
            rd_value('hba1c'),
            rd_value('krt_modality'),
            rd_value('krt_initiation_date'),
            rd_value('modality_change_dates'),
            rd_value('transplant_date'),
            rd_value('dialysis_duration'),
            rd_value('dialysis_frequency'),
            rd_value('vascular_access_type'),
            ", ".join(rd.kidney_medications_list()) if rd else '',
            ", ".join(rd.cardiovascular_medications_list()) if rd else '',
        ])

    # Enable Excel's native column filtering (AutoFilter) across the whole range
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    filename = "patients_export.xlsx"
    if query:
        sanitized_query = "".join(c for c in query if c.isalnum())
        if sanitized_query:
            filename = f"patients_{sanitized_query}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response


@login_required
def patient_profile_view(request, patient_id):
    patient = get_object_or_404(
        patients_for(request.user).select_related('doctor', 'research_data').prefetch_related(
            'prescriptions__problems',
            'prescriptions__examinations',
            'prescriptions__reports',
            'prescriptions__medicines',
            'prescriptions__images',
        ),
        id=patient_id,
    )

    prescriptions = patient.prescriptions.all().order_by('-created_at')
    today = timezone.localdate()

    context = {
        'patient': patient,
        'patient_id_formatted': f"{patient.id:04d}",
        'prescriptions': prescriptions,
        'research_data': getattr(patient, 'research_data', None),
        'appointments': patient.appointments.select_related('doctor').order_by('-date', '-serial')[:10],
        'active_appointment': patient.appointments.filter(
            date=today,
            status__in=[Appointment.STATUS_WAITING, Appointment.STATUS_IN_CONSULTATION],
        ).first(),
        'queue_form': AppointmentForm(initial_doctor=patient.doctor) if request.user.is_receptionist else None,
    }
    return render(request, 'app/patient_profile.html', context)


@login_required
def delete_patient(request, patient_id):
    patient = get_object_or_404(patients_for(request.user), id=patient_id)
    if request.method == 'POST':
        patient.delete()
        messages.success(request, "Patient record deleted successfully.")
        return redirect('search')
    return render(request, 'app/confirm_delete.html', {'patient': patient})


@login_required
def analysis_view(request):
    now = timezone.localtime()

    try:
        sel_year = int(request.GET.get("year", now.year))
    except ValueError:
        sel_year = now.year

    month_param = request.GET.get("month", "all")
    sel_month = int(month_param) if month_param.isdigit() else None
    show_daily_view = sel_month is not None
    x_axis_title = "Day" if show_daily_view else "Month"

    scope = patients_for(request.user)
    qs = scope.filter(created_at__year=sel_year)
    if show_daily_view:
        qs = qs.filter(created_at__month=sel_month)

    # Gender distribution with fallback
    gender_data = qs.exclude(gender="").values("gender").annotate(count=Count("id"))
    gender_labels = [g["gender"] for g in gender_data] or ["No Data"]
    gender_values = [g["count"] for g in gender_data] or [1]

    # Top medicines with fallback
    med_data = (Medicine.objects.filter(prescription__patient__in=qs)
                .values("name").annotate(count=Count("id")).order_by("-count")[:10])
    medicine_labels = [m["name"] for m in med_data] or ["No Data"]
    medicine_values = [m["count"] for m in med_data] or [1]

    # Top problems with fallback
    prob_data = (Problem.objects.filter(prescription__patient__in=qs)
                 .values("description").annotate(count=Count("id")).order_by("-count")[:10])
    problem_labels = [p["description"] for p in prob_data] or ["No Data"]
    problem_counts = [p["count"] for p in prob_data] or [1]

    # Age distribution with fallback
    age_data = qs.values("age").annotate(count=Count("id")).order_by("-count")[:10]
    age_labels = [str(a["age"]) for a in age_data] or ["0"]
    age_counts = [a["count"] for a in age_data] or [1]

    # Address distribution with fallback
    addr_data = (qs.exclude(address="").values("address")
                 .annotate(count=Count("id")).order_by("-count")[:5])
    address_labels = [a["address"] for a in addr_data] or ["No Data"]
    address_counts = [a["count"] for a in addr_data] or [1]

    # Time series data with fallback
    if show_daily_view:
        day_data = (qs.annotate(d=TruncDay("created_at")).values("d")
                    .annotate(count=Count("id")).order_by("d"))
        monthly_labels = [str(d["d"].day).zfill(2) for d in day_data] or ["01"]
        monthly_counts = [d["count"] for d in day_data] or [0]
    else:
        month_data = (qs.annotate(m=ExtractMonth("created_at")).values("m")
                      .annotate(count=Count("id")).order_by("m"))
        monthly_labels = [month_name[m["m"]][:3] for m in month_data] or ["Jan"]
        monthly_counts = [m["count"] for m in month_data] or [0]

    # Additional Patient Record data scoped to the same filtered patients
    rd_qs = ClinicalResearchData.objects.filter(patient__in=qs)

    comorbidity_fields = [
        ("comorbid_diabetes", "Diabetes"),
        ("comorbid_hypertension", "Hypertension"),
        ("comorbid_heart_failure", "Heart Failure"),
        ("comorbid_ischemic_heart_disease", "Ischemic Heart Disease"),
        ("comorbid_peripheral_artery_disease", "Peripheral Artery Disease"),
        ("comorbid_stroke", "Stroke"),
    ]
    comorbidity_counts_raw = rd_qs.aggregate(
        **{field: Count("id", filter=Q(**{field: True})) for field, _ in comorbidity_fields}
    )
    comorbidity_pairs = [
        (label, comorbidity_counts_raw.get(field, 0) or 0) for field, label in comorbidity_fields
    ]
    comorbidity_pairs = [p for p in comorbidity_pairs if p[1] > 0] or [("No Data", 1)]
    comorbidity_labels = [p[0] for p in comorbidity_pairs]
    comorbidity_counts = [p[1] for p in comorbidity_pairs]

    smoking_data = rd_qs.exclude(smoking_status="").values("smoking_status").annotate(count=Count("id"))
    smoking_labels = [s["smoking_status"] for s in smoking_data] or ["No Data"]
    smoking_values = [s["count"] for s in smoking_data] or [1]

    krt_data = rd_qs.exclude(krt_modality="").values("krt_modality").annotate(count=Count("id"))
    krt_labels = [k["krt_modality"] for k in krt_data] or ["No Data"]
    krt_values = [k["count"] for k in krt_data] or [1]

    employment_data = (rd_qs.exclude(employment_status="").values("employment_status")
                       .annotate(count=Count("id")).order_by("-count"))
    employment_labels = [e["employment_status"] for e in employment_data] or ["No Data"]
    employment_counts = [e["count"] for e in employment_data] or [1]

    available_years = (scope.annotate(y=ExtractYear("created_at"))
                       .values_list("y", flat=True).distinct().order_by("-y"))
    available_months = (scope.filter(created_at__year=sel_year)
                        .annotate(m=ExtractMonth("created_at"))
                        .values_list("m", flat=True).distinct().order_by("m"))

    month_options = (
        [{"value": "all", "label": "All", "selected": not show_daily_view}] +
        [{"value": f"{m:02d}", "label": month_name[m], "selected": m == sel_month}
         for m in available_months]
    )

    context = {
        "gender_labels": json.dumps(gender_labels),
        "gender_values": json.dumps(gender_values),
        "medicine_labels": json.dumps(medicine_labels),
        "medicine_values": json.dumps(medicine_values),
        "problem_labels": json.dumps(problem_labels),
        "problem_counts": json.dumps(problem_counts),
        "age_labels": json.dumps(age_labels),
        "age_counts": json.dumps(age_counts),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_counts": json.dumps(monthly_counts),
        "address_labels": json.dumps(address_labels),
        "address_counts": json.dumps(address_counts),
        "comorbidity_labels": json.dumps(comorbidity_labels),
        "comorbidity_counts": json.dumps(comorbidity_counts),
        "smoking_labels": json.dumps(smoking_labels),
        "smoking_values": json.dumps(smoking_values),
        "krt_labels": json.dumps(krt_labels),
        "krt_values": json.dumps(krt_values),
        "employment_labels": json.dumps(employment_labels),
        "employment_counts": json.dumps(employment_counts),

        "available_years": available_years,
        "month_options": month_options,
        "selected_year": sel_year,
        "month_param": month_param,
        "x_axis_title": x_axis_title,
        "x_axis_type": "category",

        "total_in_scope": qs.count(),
        "has_data": qs.exists(),
    }

    return render(request, "app/analysis.html", context)


# ---------------------------------------------------------------------------
# Autocomplete endpoints
# ---------------------------------------------------------------------------

@login_required
@require_GET
def problem_autocomplete(request):
    query = request.GET.get('q', '').strip()
    problems = (Problem.objects
                .filter(prescription__patient__in=patients_for(request.user),
                        description__icontains=query)
                .values('description')
                .annotate(total=Count('id'))
                .order_by('-total')[:10])
    return JsonResponse([{'name': p['description'], 'count': p['total']} for p in problems], safe=False)


@login_required
@require_GET
def report_autocomplete(request):
    query = request.GET.get('q', '').strip()
    reports = (Report.objects
               .filter(prescription__patient__in=patients_for(request.user),
                       name__icontains=query)
               .values('name')
               .annotate(total=Count('id'))
               .order_by('-total')[:10])
    return JsonResponse([{'name': r['name'], 'count': r['total']} for r in reports], safe=False)


@login_required
@require_GET
def examination_autocomplete(request):
    query = request.GET.get('q', '').strip()
    examinations = (Examination.objects
                    .filter(prescription__patient__in=patients_for(request.user),
                            name__icontains=query)
                    .values('name')
                    .annotate(total=Count('id'))
                    .order_by('-total')[:10])
    return JsonResponse([{'name': e['name'], 'count': e['total']} for e in examinations], safe=False)


@login_required
@require_GET
def medicine_autocomplete(request):
    """
    Medicine Name suggestions.

    Combines two sources so the dropdown is genuinely useful:
      1. HISTORY   - medicines this doctor has personally prescribed before,
         each annotated with how many times it's been used and the most
         recent strength/frequency/remark/duration, so picking one can
         auto-fill the rest of the row.
      2. CATALOGUE - the master medicine list imported from data/Medicines.csv.

    Matching is "dynamic": the query is split into whitespace-separated
    tokens and a name only has to contain every token (in any order,
    case-insensitive) to match - e.g. "napa ext" matches "Napa Extend".
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse([], safe=False)

    tokens = [t for t in query.split() if t]
    token_filter = Q()
    for t in tokens:
        token_filter &= Q(name__icontains=t)

    def rank(name):
        lname = name.lower()
        if lname.startswith(query.lower()):
            return 0
        if tokens and lname.startswith(tokens[0].lower()):
            return 1
        return 2

    MAX_RESULTS = 15
    scope = patients_for(request.user)

    # --- 1. The doctor's own prescribing history ------------------------------
    history_qs = (
        Medicine.objects
        .filter(prescription__patient__in=scope)
        .filter(token_filter)
        .values('name')
        .annotate(total=Count('id'), last_used=Max('prescription__created_at'))
        .order_by('-total', '-last_used')[:MAX_RESULTS]
    )

    history_results = []
    seen_names_lower = set()
    for row in history_qs:
        name = row['name']
        last_entry = (
            Medicine.objects
            .filter(prescription__patient__in=scope, name=name)
            .order_by('-prescription__created_at', '-id')
            .values('strength', 'frequency', 'remark', 'days')
            .first()
        ) or {}
        history_results.append({
            'name': name,
            'source': 'history',
            'count': row['total'],
            'strength': last_entry.get('strength', ''),
            'frequency': last_entry.get('frequency', ''),
            'remark': last_entry.get('remark', ''),
            'days': last_entry.get('days'),
        })
        seen_names_lower.add(name.lower())

    history_results.sort(key=lambda r: (rank(r['name']), -r['count']))

    # --- 2. Master catalogue -------------------------------------------------
    remaining_slots = MAX_RESULTS - len(history_results)
    catalogue_results = []
    if remaining_slots > 0:
        catalogue_qs = (
            MedicineMaster.objects
            .filter(token_filter)
            .order_by('name')
            .values_list('name', flat=True)[:remaining_slots * 3]  # over-fetch, then rank+dedupe
        )
        for name in catalogue_qs:
            if name.lower() in seen_names_lower:
                continue
            catalogue_results.append({
                'name': name, 'source': 'catalog', 'count': None,
                'strength': '', 'frequency': '', 'remark': '', 'days': None,
            })
            seen_names_lower.add(name.lower())

        catalogue_results.sort(key=lambda r: (rank(r['name']), r['name'].lower()))
        catalogue_results = catalogue_results[:remaining_slots]

    return JsonResponse(history_results + catalogue_results, safe=False)


# ---------------------------------------------------------------------------
# Administrator panel
# ---------------------------------------------------------------------------

@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    todays = Appointment.objects.filter(date=today)

    return render(request, 'app/manage/dashboard.html', {
        'today': today,
        'counts': {
            'doctors': Doctor.objects.filter(role=ROLE_DOCTOR).count(),
            'receptionists': Doctor.objects.filter(role=ROLE_RECEPTIONIST).count(),
            'admins': Doctor.objects.filter(role=ROLE_ADMIN).count(),
            'inactive': Doctor.objects.filter(is_active=False).count(),
            'patients': Patient.objects.count(),
            'prescriptions': Prescription.objects.count(),
            'records': ClinicalResearchData.objects.count(),
            'medicines': MedicineMaster.objects.count(),
        },
        'today_stats': {
            'registered': Patient.objects.filter(created_at__date=today).count(),
            'appointments': todays.count(),
            'waiting': todays.filter(status=Appointment.STATUS_WAITING).count(),
            'in_consultation': todays.filter(status=Appointment.STATUS_IN_CONSULTATION).count(),
            'completed': todays.filter(status=Appointment.STATUS_COMPLETED).count(),
            'prescriptions': Prescription.objects.filter(created_at__date=today).count(),
        },
        'doctor_rows': [
            {
                'doctor': doctor,
                'waiting': todays.filter(doctor=doctor, status=Appointment.STATUS_WAITING).count(),
                'completed': todays.filter(doctor=doctor, status=Appointment.STATUS_COMPLETED).count(),
                'current': todays.filter(doctor=doctor,
                                         status=Appointment.STATUS_IN_CONSULTATION)
                                 .select_related('patient').first(),
                'patients': Patient.objects.filter(doctor=doctor).count(),
            }
            for doctor in Doctor.objects.doctors().order_by('first_name', 'doctor_id')
        ],
        'recent_patients': Patient.objects.select_related('doctor').order_by('-created_at')[:8],
        'recent_prescriptions': (Prescription.objects.select_related('patient', 'doctor')
                                 .order_by('-created_at')[:8]),
    })


@admin_required
def admin_accounts(request):
    role_filter = request.GET.get('role', '').strip()
    query = request.GET.get('q', '').strip()

    accounts = Doctor.objects.all()
    if role_filter in dict(ROLE_CHOICES):
        accounts = accounts.filter(role=role_filter)
    if query:
        accounts = accounts.filter(
            Q(doctor_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    return render(request, 'app/manage/accounts.html', {
        'accounts': accounts.order_by('role', 'doctor_id'),
        'role_choices': ROLE_CHOICES,
        'role_filter': role_filter,
        'query': query,
        'totals': {
            'all': Doctor.objects.count(),
            'doctor': Doctor.objects.filter(role=ROLE_DOCTOR).count(),
            'receptionist': Doctor.objects.filter(role=ROLE_RECEPTIONIST).count(),
            'admin': Doctor.objects.filter(role=ROLE_ADMIN).count(),
        },
    })


@admin_required
def admin_account_create(request):
    if request.method == 'POST':
        form = ManagedAccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(
                request,
                f"Created {account.role_label.lower()} account {account.doctor_id}."
            )
            return redirect('admin_accounts')
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ManagedAccountForm()

    return render(request, 'app/manage/account_form.html', {'form': form, 'creating': True})


@admin_required
def admin_account_edit(request, account_id):
    account = get_object_or_404(Doctor, id=account_id)

    if request.method == 'POST':
        form = ManagedAccountForm(request.POST, instance=account)
        if form.is_valid():
            if account == request.user and not form.cleaned_data.get('is_active', True):
                form.add_error('is_active', "You cannot deactivate your own account.")
            elif account == request.user and form.cleaned_data.get('role') != ROLE_ADMIN:
                form.add_error('role', "You cannot remove your own administrator role.")
            else:
                account = form.save()
                messages.success(request, f"Updated {account.doctor_id}.")
                return redirect('admin_accounts')
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ManagedAccountForm(instance=account)

    return render(request, 'app/manage/account_form.html', {
        'form': form,
        'account': account,
        'creating': False,
        'password_form': AccountPasswordForm(),
        'is_self': account == request.user,
    })


@admin_required
@require_POST
def admin_account_password(request, account_id):
    account = get_object_or_404(Doctor, id=account_id)
    form = AccountPasswordForm(request.POST)
    if form.is_valid():
        account.set_password(form.cleaned_data['password1'])
        account.save(update_fields=['password'])
        if account == request.user:
            update_session_auth_hash(request, account)
        messages.success(request, f"Password updated for {account.doctor_id}.")
    else:
        messages.error(request, form.errors.as_text().replace('*', '').strip())
    return redirect('admin_account_edit', account_id=account.id)


@admin_required
@require_POST
def admin_account_toggle(request, account_id):
    account = get_object_or_404(Doctor, id=account_id)
    if account == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('admin_accounts')

    account.is_active = not account.is_active
    account.save(update_fields=['is_active'])
    state = "reactivated" if account.is_active else "deactivated"
    messages.success(request, f"{account.doctor_id} {state}.")
    return redirect('admin_accounts')


@admin_required
def admin_appointments(request):
    """Every doctor's queue for any chosen day, read-only."""
    raw_date = request.GET.get('date', '').strip()
    day = parse_date(raw_date) or timezone.localdate()

    appointments = (Appointment.objects.filter(date=day)
                    .select_related('patient', 'doctor', 'created_by')
                    .order_by('doctor__first_name', 'serial'))

    status_filter = request.GET.get('status', '').strip()
    if status_filter in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status_filter)

    return render(request, 'app/manage/appointments.html', {
        'day': day,
        'appointments': appointments,
        'status_choices': Appointment.STATUS_CHOICES,
        'status_filter': status_filter,
        'summary': {
            'total': Appointment.objects.filter(date=day).count(),
            'waiting': Appointment.objects.filter(date=day, status=Appointment.STATUS_WAITING).count(),
            'completed': Appointment.objects.filter(date=day, status=Appointment.STATUS_COMPLETED).count(),
            'cancelled': Appointment.objects.filter(date=day, status=Appointment.STATUS_CANCELLED).count(),
        },
    })
