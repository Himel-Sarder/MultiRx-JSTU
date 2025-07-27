from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import DoctorProfileUpdateForm, DoctorRegistrationForm, DoctorLoginForm, PatientForm
from .models import *
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import CSS, HTML
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth, ExtractYear, ExtractMonth, TruncDay
import openpyxl
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from calendar import month_name
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.template.loader import get_template
from django.utils import timezone

def home_view(request):
    return render(request, 'app/home.html')

def register_view(request):
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = DoctorRegistrationForm()
    return render(request, 'app/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = DoctorLoginForm(request.POST)
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'app/login.html', {'form': form, 'error': 'Invalid credentials'})
    else:
        form = DoctorLoginForm()
    return render(request, 'app/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def profile_view(request):
    doctor = request.user
    if request.method == 'POST':
        form = DoctorProfileUpdateForm(request.POST, request.FILES, instance=doctor)
        if form.is_valid():
            # Handle file upload
            if 'profile_picture' in request.FILES:
                # Delete old picture if it exists
                if doctor.profile_picture:
                    doctor.profile_picture.delete()
                doctor.profile_picture = request.FILES['profile_picture']
            elif form.cleaned_data.get('profile_picture-clear'):
                # Handle profile picture clear
                if doctor.profile_picture:
                    doctor.profile_picture.delete()
                    doctor.profile_picture = None
            
            # Save all other fields
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = DoctorProfileUpdateForm(instance=doctor)
    
    return render(request, 'app/profile.html', {
        'form': form,
        'doctor': doctor
    })


@login_required
def prescribe_view(request):
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        if patient_form.is_valid():
            # Create new patient
            patient = Patient.objects.create(
                doctor=request.user,
                name=patient_form.cleaned_data['name'],
                age=patient_form.cleaned_data['age'],
                address=patient_form.cleaned_data['address'],
                gender=patient_form.cleaned_data['gender']
            )
            
            # Create prescription
            prescription = Prescription.objects.create(patient=patient)
            
            # Save problems
            for desc in request.POST.getlist('problems'):
                if desc.strip():
                    Problem.objects.create(prescription=prescription, description=desc.strip())

            # Save examinations
            for desc in request.POST.getlist('examinations'):
                if desc.strip():
                    Examination.objects.create(prescription=prescription, description=desc.strip())

            # Save reports
            names = request.POST.getlist('report_names')
            results = request.POST.getlist('report_results')
            for name, result in zip(names, results):
                if name.strip() and result.strip():
                    Report.objects.create(prescription=prescription, name=name.strip(), result=result.strip())

            # Save report images
            for image in request.FILES.getlist('report_images'):
                ReportImage.objects.create(prescription=prescription, image=image)

            # Save medicines
            med_names = request.POST.getlist('medicine_names')
            strengths = request.POST.getlist('medicine_strengths')
            frequencies = request.POST.getlist('medicine_frequencies')
            remarks = request.POST.getlist('medicine_remarks')
            days = request.POST.getlist('medicine_days')

            for i in range(len(med_names)):
                name = med_names[i].strip()
                if name:
                    Medicine.objects.create(
                        prescription=prescription,
                        name=name,
                        strength=strengths[i].strip(),
                        frequency=frequencies[i].strip(),
                        remark=remarks[i].strip(),
                        days=int(days[i]) if days[i] else 0
                    )

            return redirect('prescription_pdf', prescription_id=prescription.id)
    
    # For GET request
    form = PatientForm()
    return render(request, 'app/prescribe.html', {'form': form})

@login_required
def prescribe_with_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)
    
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        if patient_form.is_valid():
            # Update patient info
            patient.name = patient_form.cleaned_data['name']
            patient.age = patient_form.cleaned_data['age']
            patient.address = patient_form.cleaned_data['address']
            patient.gender = patient_form.cleaned_data['gender']
            patient.save()

            # Create new prescription
            prescription = Prescription.objects.create(patient=patient)
            
            # Save problems
            for desc in request.POST.getlist('problems'):
                if desc.strip():
                    Problem.objects.create(prescription=prescription, description=desc.strip())

            # Save examinations
            for desc in request.POST.getlist('examinations'):
                if desc.strip():
                    Examination.objects.create(prescription=prescription, description=desc.strip())

            # Save reports
            names = request.POST.getlist('report_names')
            results = request.POST.getlist('report_results')
            for name, result in zip(names, results):
                if name.strip() and result.strip():
                    Report.objects.create(prescription=prescription, name=name.strip(), result=result.strip())

            # Save report images
            for image in request.FILES.getlist('report_images'):
                ReportImage.objects.create(prescription=prescription, image=image)

            # Save medicines
            med_names = request.POST.getlist('medicine_names')
            strengths = request.POST.getlist('medicine_strengths')
            frequencies = request.POST.getlist('medicine_frequencies')
            remarks = request.POST.getlist('medicine_remarks')
            days = request.POST.getlist('medicine_days')

            for i in range(len(med_names)):
                name = med_names[i].strip()
                if name:
                    Medicine.objects.create(
                        prescription=prescription,
                        name=name,
                        strength=strengths[i].strip(),
                        frequency=frequencies[i].strip(),
                        remark=remarks[i].strip(),
                        days=int(days[i]) if days[i] else 0
                    )

            return redirect('prescription_pdf', prescription_id=prescription.id)
    
    # For GET request - pre-populate with last prescription data if exists
    last_prescription = patient.prescriptions.last()
    initial_data = {
        'name': patient.name,
        'age': patient.age,
        'address': patient.address,
        'gender': patient.gender
    }
    
    form = PatientForm(initial=initial_data)
    
    context = {
        'form': form,
        'patient': patient,
        'last_prescription': last_prescription  # Pass last prescription to template
    }
    return render(request, 'app/prescribe.html', context)

@login_required
def prescription_pdf(request, prescription_id):
    prescription = get_object_or_404(
        Prescription.objects.select_related('patient')
                          .prefetch_related('problems', 'examinations', 'reports', 'medicines'),
        id=prescription_id,
        patient__doctor=request.user
    )
    
    now = timezone.now()
    
    context = {
        'prescription': prescription,
        'patient': prescription.patient,
        'doctor': request.user,
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
    
    # Generate PDF with Bengali font support
    html = HTML(
        string=html_string,
        base_url=request.build_absolute_uri(),
        encoding='utf-8'
    )
    
    # Configure font settings
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

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    patient_qs = Patient.objects.filter(doctor=request.user).order_by('-created_at')

    if query:
        # Check for custom ID formats in search
        if query.startswith('P') or query.startswith('Pres'):
            try:
                if query.startswith('Pres'):
                    num = int(query[4:])
                    # Search only by prescription ID
                    patient_qs = patient_qs.filter(prescriptions__id=num)
                    # Return early if we found an exact match
                    if patient_qs.exists():
                        paginator = Paginator(patient_qs, 5)
                        page_obj = paginator.get_page(1)
                        context = {
                            "results": page_obj,
                            "page_obj": page_obj,
                            "total_count": Patient.objects.filter(doctor=request.user).count(),
                            "search_count": paginator.count,
                            "query": query,
                        }
                        return render(request, "app/search.html", context)
                else:
                    num = int(query[1:])
                    # Search only by patient ID
                    patient_qs = patient_qs.filter(id=num)
                    # Return early if we found an exact match
                    if patient_qs.exists():
                        paginator = Paginator(patient_qs, 5)
                        page_obj = paginator.get_page(1)
                        context = {
                            "results": page_obj,
                            "page_obj": page_obj,
                            "total_count": Patient.objects.filter(doctor=request.user).count(),
                            "search_count": paginator.count,
                            "query": query,
                        }
                        return render(request, "app/search.html", context)
            except (ValueError, IndexError):
                # If conversion fails, continue with regular search
                pass
        
        # Regular search (only reached if no exact ID match was found)
        patient_qs = patient_qs.filter(
            Q(name__icontains=query) |
            Q(age__icontains=query) |
            Q(address__icontains=query) |
            Q(prescriptions__problems__description__icontains=query) |
            Q(prescriptions__examinations__description__icontains=query) |
            Q(prescriptions__reports__name__icontains=query) |
            Q(prescriptions__reports__result__icontains=query) |
            Q(prescriptions__medicines__name__icontains=query)
        ).distinct()

    paginator = Paginator(patient_qs, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "results": page_obj,
        "page_obj": page_obj,
        "total_count": Patient.objects.filter(doctor=request.user).count(),
        "search_count": paginator.count,
        "query": query,
    }
    return render(request, "app/search.html", context)

@login_required
def export_excel(request):
    query = request.GET.get('q', '').strip()
    patients = Patient.objects.filter(doctor=request.user).order_by('-created_at')

    if query:
        # Handle formatted ID searches (P1, Pres1, etc.)
        if query.startswith('P'):
            try:
                if query.startswith('Pres'):
                    # Search by prescription ID (Pres1, Pres2, etc.)
                    pres_id = int(query[4:])
                    patients = patients.filter(prescriptions__id=pres_id)
                else:
                    # Search by patient ID (P1, P2, etc.)
                    patient_id = int(query[1:])
                    patients = patients.filter(id=patient_id)
                
                # If we found exact ID matches, use those results
                if patients.exists():
                    return _generate_excel(patients, query)
            except (ValueError, IndexError):
                # If ID conversion fails, continue with regular search
                pass
        
        # Regular text search
        patients = patients.filter(
            Q(name__icontains=query) |
            Q(age__icontains=query) |
            Q(address__icontains=query) |
            Q(prescriptions__problems__description__icontains=query) |
            Q(prescriptions__examinations__description__icontains=query) |
            Q(prescriptions__reports__name__icontains=query) |
            Q(prescriptions__reports__result__icontains=query) |
            Q(prescriptions__medicines__name__icontains=query)
        ).distinct()

    return _generate_excel(patients, query)

def _generate_excel(patients, query=None):
    """Helper function to generate Excel file from patient queryset"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    # Column headers with formatted IDs
    headers = [
        'Patient ID', 'Name', 'Age', 'Gender', 'Address', 'Created Date',
        'Prescription IDs', 'Problems', 'Examinations', 'Reports', 'Medicines'
    ]
    ws.append(headers)

    # Set column widths
    column_widths = [15, 25, 10, 10, 30, 15, 20, 40, 40, 40, 40]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    for patient in patients:
        prescriptions = patient.prescriptions.all()
        
        # Collect data
        problems = []
        examinations = []
        reports = []
        medicines = []
        pres_ids = []
        
        for pres in prescriptions:
            pres_ids.append(f"Pres{pres.id}")
            problems.extend(p.description for p in pres.problems.all())
            examinations.extend(e.description for e in pres.examinations.all())
            reports.extend(f"{r.name}: {r.result}" for r in pres.reports.all())
            medicines.extend(
                f"{m.name} ({m.strength}) - {m.frequency}" 
                for m in pres.medicines.all()
            )

        # Add formatted data to worksheet
        ws.append([
            f"P{patient.id}",  # Formatted patient ID
            patient.name,
            patient.age,
            patient.gender,
            patient.address,
            patient.created_at.strftime('%Y-%m-%d'),
            ", ".join(pres_ids),  # Comma-separated prescription IDs
            "\n".join(problems),
            "\n".join(examinations),
            "\n".join(reports),
            "\n".join(medicines)
        ])

    # Create filename
    filename = "patients_export.xlsx"
    if query:
        sanitized_query = "".join(c for c in query if c.isalnum())
        filename = f"patients_{sanitized_query}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    wb.save(response)
    return response

@login_required
def analysis_view(request):
    now = timezone.now()
    
    # Get filters with defaults
    try:
        sel_year = int(request.GET.get("year", now.year))
    except ValueError:
        sel_year = now.year
    
    month_param = request.GET.get("month", "all")
    sel_month = int(month_param) if month_param.isdigit() else None
    show_daily_view = sel_month is not None
    x_axis_title = "Day" if show_daily_view else "Month"
    x_axis_type = "category"  # Explicitly set axis type

    # Base queryset with optimizations
    qs = Patient.objects.filter(doctor=request.user, created_at__year=sel_year)
    if show_daily_view:
        qs = qs.filter(created_at__month=sel_month)

    # Gender distribution with fallback
    gender_data = qs.exclude(gender="").values("gender").annotate(count=Count("id"))
    gender_labels = [g["gender"] for g in gender_data] or ["No Data"]
    gender_values = [g["count"] for g in gender_data] or [1]  # Fallback value for chart

    # Top medicines with fallback
    med_data = (Medicine.objects.filter(prescription__patient__in=qs)
                .values("name")
                .annotate(count=Count("id"))
                .order_by("-count")[:10])
    medicine_labels = [m["name"] for m in med_data] or ["No Data"]
    medicine_values = [m["count"] for m in med_data] or [1]

    # Top problems with fallback
    prob_data = (Problem.objects.filter(prescription__patient__in=qs)
                 .values("description")
                 .annotate(count=Count("id"))
                 .order_by("-count")[:10])
    problem_labels = [p["description"] for p in prob_data] or ["No Data"]
    problem_counts = [p["count"] for p in prob_data] or [1]

    # Age distribution with fallback
    age_data = (qs.values("age")
                .annotate(count=Count("id"))
                .order_by("-count")[:10])
    age_labels = [str(a["age"]) for a in age_data] or ["0"]  # Ensure strings for JSON
    age_counts = [a["count"] for a in age_data] or [1]

    # Address distribution with fallback
    addr_data = (qs.exclude(address="")
                 .values("address")
                 .annotate(count=Count("id"))
                 .order_by("-count")[:5])
    address_labels = [a["address"] for a in addr_data] or ["No Data"]
    address_counts = [a["count"] for a in addr_data] or [1]

    # Time series data with fallback
    if show_daily_view:
        day_data = (qs.annotate(d=TruncDay("created_at"))
                     .values("d")
                     .annotate(count=Count("id"))
                     .order_by("d"))
        monthly_labels = [str(d["d"].day).zfill(2) for d in day_data] or ["01"]
        monthly_counts = [d["count"] for d in day_data] or [0]
    else:
        month_data = (qs.annotate(m=ExtractMonth("created_at"))
                      .values("m")
                      .annotate(count=Count("id"))
                      .order_by("m"))
        monthly_labels = [month_name[m["m"]][:3] for m in month_data] or ["Jan"]
        monthly_counts = [m["count"] for m in month_data] or [0]

    # Available years and months
    available_years = (Patient.objects.filter(doctor=request.user)
                       .annotate(y=ExtractYear("created_at"))
                       .values_list("y", flat=True)
                       .distinct()
                       .order_by("-y"))

    available_months = (Patient.objects.filter(doctor=request.user,
                                              created_at__year=sel_year)
                        .annotate(m=ExtractMonth("created_at"))
                        .values_list("m", flat=True)
                        .distinct()
                        .order_by("m"))

    month_options = (
        [{"value": "all", "label": "All", "selected": not show_daily_view}] +
        [{"value": f"{m:02d}",
          "label": month_name[m],
          "selected": m == sel_month}
         for m in available_months]
    )

    context = {
        # Chart data
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
        
        # Filter options
        "available_years": available_years,
        "month_options": month_options,
        "selected_year": sel_year,
        "month_param": month_param,
        "x_axis_title": x_axis_title,
        "x_axis_type": x_axis_type,
        
        # Debug flags
        "has_data": qs.exists(),
    }

    return render(request, "app/analysis.html", context)


@login_required
def delete_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)
    if request.method == 'POST':
        patient.delete()
        messages.success(request, "Patient record deleted successfully.")
        return redirect('search')
    return render(request, 'app/confirm_delete.html', {'patient': patient})

@require_GET
@login_required
def medicine_autocomplete(request):
    q = request.GET.get('q', '').strip()
    meds = (Medicine.objects
            .filter(prescription__patient__doctor=request.user, name__icontains=q)
            .values('name')
            .annotate(total=Count('id'))
            .order_by('-total')[:10])

    data = [{'name': m['name'], 'count': m['total']} for m in meds]
    return JsonResponse(data, safe=False)

@login_required
def patient_profile_view(request, patient_id):
    patient = get_object_or_404(
        Patient.objects.prefetch_related(
            'prescriptions__problems',
            'prescriptions__examinations',
            'prescriptions__reports',
            'prescriptions__medicines',
            'prescriptions__images'
        ),
        id=patient_id,
        doctor=request.user
    )
    
    # Get all prescriptions for the patient ordered by creation date (newest first)
    prescriptions = patient.prescriptions.all().order_by('-created_at')
    
    # Prepare prescriptions data with formatted IDs
    formatted_prescriptions = []
    for prescription in prescriptions:
        formatted_prescriptions.append({
            'id': prescription.id,
            'id_formatted': f"{prescription.id:04d}",  # 4-digit format with leading zeros
            'created_at': prescription.created_at,
            'problems': prescription.problems.all(),
            'examinations': prescription.examinations.all(),
            'reports': prescription.reports.all(),
            'medicines': prescription.medicines.all(),
            'images': prescription.images.all(),
        })
    
    # Collect all related data from all prescriptions
    all_problems = []
    all_examinations = []
    all_reports = []
    all_medicines = []
    all_images = []
    
    for prescription in prescriptions:
        all_problems.extend(prescription.problems.all())
        all_examinations.extend(prescription.examinations.all())
        all_reports.extend(prescription.reports.all())
        all_medicines.extend(prescription.medicines.all())
        all_images.extend(prescription.images.all())
    
    context = {
        'patient': patient,
        'patient_id_formatted': f"{patient.id:04d}",  # 4-digit patient ID
        'prescriptions': formatted_prescriptions,
        'problems': all_problems,
        'examinations': all_examinations,
        'reports': all_reports,
        'medicines': all_medicines,
        'images': all_images,
    }
    
    return render(request, 'app/patient_profile.html', context)


from django.http import JsonResponse
from django.db.models import Count

@login_required
@require_GET
def problem_autocomplete(request):
    query = request.GET.get('q', '').strip()
    problems = (Problem.objects
                .filter(prescription__patient__doctor=request.user, 
                        description__icontains=query)
                .values('description')
                .annotate(total=Count('id'))
                .order_by('-total')[:10])
    data = [{'name': p['description'], 'count': p['total']} for p in problems]
    return JsonResponse(data, safe=False)

@login_required
@require_GET
def report_autocomplete(request):
    query = request.GET.get('q', '').strip()
    reports = (Report.objects
              .filter(prescription__patient__doctor=request.user, 
                      name__icontains=query)
              .values('name')
              .annotate(total=Count('id'))
              .order_by('-total')[:10])
    data = [{'name': r['name'], 'count': r['total']} for r in reports]
    return JsonResponse(data, safe=False)

@login_required
@require_GET
def medicine_autocomplete(request):
    query = request.GET.get('q', '').strip()
    meds = (Medicine.objects
            .filter(prescription__patient__doctor=request.user, 
                    name__icontains=query)
            .values('name')
            .annotate(total=Count('id'))
            .order_by('-total')[:10])
    data = [{'name': m['name'], 'count': m['total']} for m in meds]
    return JsonResponse(data, safe=False)

@login_required
@require_GET
def examination_autocomplete(request):
    query = request.GET.get('q', '').strip()
    examinations = (Examination.objects
                   .filter(prescription__patient__doctor=request.user, 
                           description__icontains=query)
                   .values('description')
                   .annotate(total=Count('id'))
                   .order_by('-total')[:10])
    data = [{'name': e['description'], 'count': e['total']} for e in examinations]
    return JsonResponse(data, safe=False)

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ProfilePictureForm

@login_required
def profile_picture_change(request):
    # Just render the form page
    form = ProfilePictureForm()
    return render(request, 'app/profile_pic_change.html', {'form': form})

# views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
import os
from django.conf import settings

@login_required
def profile_picture_update(request):
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            # Delete old picture if exists
            if request.user.profile_picture:
                old_file = request.user.profile_picture.path
                if os.path.exists(old_file):
                    os.remove(old_file)
            
            # Save the form (which includes the new picture)
            form.save()
            messages.success(request, "Profile picture updated successfully!")
            return redirect('profile')
    else:
        form = ProfilePictureForm(instance=request.user)
    
    return render(request, 'app/profile_pic_change.html', {'form': form})