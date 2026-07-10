from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import DoctorProfileUpdateForm, DoctorRegistrationForm, DoctorLoginForm, PatientForm
from .models import *
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import CSS, HTML
from django.db.models import Q, Count, Max
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

# views.py
def register_view(request):
    if request.method == 'POST':
        form = DoctorRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = DoctorRegistrationForm()
    return render(request, 'app/register.html', {'form': form})

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect

def login_view(request):
    if request.method == 'POST':
        form = DoctorLoginForm(request.POST)
        if form.is_valid():
            doctor_id = form.cleaned_data['doctor_id']
            password = form.cleaned_data['password']
            user = authenticate(request, doctor_id=doctor_id, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, 'Login successful!')
                return redirect('profile')
            else:
                # Add error to the form's non_field_errors
                form.add_error(None, "Invalid Doctor ID or password")
        # If form is invalid, it will automatically show field errors
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


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Patient, Prescription, Problem, Examination, Report, ReportImage, Medicine
from .forms import PatientForm

@login_required
def prescribe_view(request):
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        if patient_form.is_valid():
            try:
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
                problems = [desc.strip() for desc in request.POST.getlist('problems') if desc.strip()]
                for desc in problems:
                    Problem.objects.create(prescription=prescription, description=desc)

                # Save examinations
                exam_names = request.POST.getlist('examination_names')
                exam_results = request.POST.getlist('examination_results')
                for i in range(len(exam_names)):
                    name = exam_names[i].strip() if i < len(exam_names) else ""
                    if name:
                        result = exam_results[i].strip() if i < len(exam_results) else ""
                        Examination.objects.create(
                            prescription=prescription,
                            name=name,
                            description=result if result else ""
                        )

                # Save reports
                report_names = request.POST.getlist('report_names')
                report_results = request.POST.getlist('report_results')
                for i in range(len(report_names)):
                    name = report_names[i].strip() if i < len(report_names) else ""
                    if name:
                        result = report_results[i].strip() if i < len(report_results) else ""
                        Report.objects.create(
                            prescription=prescription,
                            name=name,
                            result=result if result else ""
                        )

                # Save report images
                for image in request.FILES.getlist('report_images'):
                    ReportImage.objects.create(prescription=prescription, image=image)

                # Get medicine data with new duration fields
                med_names = request.POST.getlist('medicine_names')
                strengths = request.POST.getlist('medicine_strengths')
                frequencies = request.POST.getlist('medicine_frequencies')
                remarks = request.POST.getlist('medicine_remarks')
                days_numbers = request.POST.getlist('medicine_days_number')
                days_units = request.POST.getlist('medicine_days_unit')

                def safe_get(lst, i, default=""):
                    return lst[i] if i < len(lst) else default

                for i in range(len(med_names)):
                    name = safe_get(med_names, i).strip()
                    if not name:
                        continue

                    strength = safe_get(strengths, i).strip()
                    freq = safe_get(frequencies, i).strip()
                    remark = safe_get(remarks, i).strip()
                    number = safe_get(days_numbers, i, "")  # may be missing if disabled
                    unit = safe_get(days_units, i, "din")

                    # Convert to days
                    if unit == "colbe":
                        days = 0
                    else:
                        try:
                            num = int(number) if str(number).strip() else 1
                        except (ValueError, TypeError):
                            num = 1

                        if unit == "din":
                            days = num
                        elif unit == "soptaho":
                            days = num * 7
                        elif unit == "mash":
                            days = num * 30
                        elif unit == "bosor":
                            days = num * 365
                        else:
                            days = num

                    Medicine.objects.create(
                        prescription=prescription,
                        name=name,
                        strength=strength,
                        frequency=freq,
                        remark=remark,
                        days=days
                    )
                
                # Determine which button was clicked
                action = request.POST.get('action', 'save_and_download')
                
                if action == 'save_and_download':
                    return redirect('prescription_pdf', prescription_id=prescription.id)
                elif action == 'next':
                    return redirect('research_data', prescription_id=prescription.id)
                else:  # 'save'
                    messages.success(request, "Prescription saved successfully!")
                    return redirect('patient_profile', patient_id=patient.id)
            
            except Exception as e:
                patient_form.add_error(None, f"An error occurred: {str(e)}")
                return render(request, 'app/prescribe.html', {'form': patient_form})
    
    # For GET request
    form = PatientForm()
    return render(request, 'app/prescribe.html', {'form': form})

@login_required
def prescribe_with_patient(request, patient_id):
    patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)
    
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        if patient_form.is_valid():
            try:
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
                exam_names = request.POST.getlist('examination_names')
                exam_results = request.POST.getlist('examination_results')
                for i in range(len(exam_names)):
                    name = exam_names[i].strip() if i < len(exam_names) else ""
                    if name:
                        result = exam_results[i].strip() if i < len(exam_results) else ""
                        Examination.objects.create(
                            prescription=prescription,
                            name=name,
                            description=result if result else ""
                        )

                # Save reports
                report_names = request.POST.getlist('report_names')
                report_results = request.POST.getlist('report_results')
                for i in range(len(report_names)):
                    name = report_names[i].strip() if i < len(report_names) else ""
                    if name:
                        result = report_results[i].strip() if i < len(report_results) else ""
                        Report.objects.create(
                            prescription=prescription,
                            name=name,
                            result=result if result else ""
                        )

                # Save report images
                for image in request.FILES.getlist('report_images'):
                    ReportImage.objects.create(prescription=prescription, image=image)

                # Get medicine data with new duration fields
                med_names = request.POST.getlist('medicine_names')
                strengths = request.POST.getlist('medicine_strengths')
                frequencies = request.POST.getlist('medicine_frequencies')
                remarks = request.POST.getlist('medicine_remarks')
                days_numbers = request.POST.getlist('medicine_days_number')
                days_units = request.POST.getlist('medicine_days_unit')

                def safe_get(lst, i, default=""):
                    return lst[i] if i < len(lst) else default

                for i in range(len(med_names)):
                    name = safe_get(med_names, i).strip()
                    if not name:
                        continue

                    strength = safe_get(strengths, i).strip()
                    freq = safe_get(frequencies, i).strip()
                    remark = safe_get(remarks, i).strip()
                    number = safe_get(days_numbers, i, "")  # may be missing if disabled
                    unit = safe_get(days_units, i, "din")

                    # Convert to days
                    if unit == "colbe":
                        days = 0
                    else:
                        try:
                            num = int(number) if str(number).strip() else 1
                        except (ValueError, TypeError):
                            num = 1

                        if unit == "din":
                            days = num
                        elif unit == "soptaho":
                            days = num * 7
                        elif unit == "mash":
                            days = num * 30
                        elif unit == "bosor":
                            days = num * 365
                        else:
                            days = num

                    Medicine.objects.create(
                        prescription=prescription,
                        name=name,
                        strength=strength,
                        frequency=freq,
                        remark=remark,
                        days=days
                    )
                
                # Determine which button was clicked
                action = request.POST.get('action', 'save_and_download')
                
                if action == 'save_and_download':
                    return redirect('prescription_pdf', prescription_id=prescription.id)
                elif action == 'next':
                    return redirect('research_data', prescription_id=prescription.id)
                else:  # 'save'
                    messages.success(request, "Prescription saved successfully!")
                    return redirect('patient_profile', patient_id=patient.id)
            
            except Exception as e:
                patient_form.add_error(None, f"An error occurred: {str(e)}")
                return render(request, 'app/prescribe.html', {'form': patient_form, 'patient': patient})
    
    # For GET request
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
        'last_prescription': last_prescription
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


from .models import ClinicalResearchData
from .forms import ClinicalResearchDataForm

@login_required
def research_data_view(request, prescription_id):
    prescription = get_object_or_404(
        Prescription.objects.select_related('patient'),
        id=prescription_id,
        patient__doctor=request.user
    )
    instance = getattr(prescription, 'research_data', None)

    if request.method == 'POST':
        form = ClinicalResearchDataForm(request.POST, instance=instance)
        if form.is_valid():
            research_data = form.save(commit=False)
            research_data.prescription = prescription
            research_data.save()

            action = request.POST.get('action', 'save')
            messages.success(request, "Additional patient record saved successfully!")
            if action == 'save_and_download':
                return redirect('prescription_pdf', prescription_id=prescription.id)
            return redirect('patient_profile', patient_id=prescription.patient.id)
    else:
        form = ClinicalResearchDataForm(instance=instance)

    return render(request, 'app/research_data.html', {
        'form': form,
        'prescription': prescription,
        'patient': prescription.patient,
    })


RESEARCH_COMORBID_FIELDS = {
    'diabetes': 'prescriptions__research_data__comorbid_diabetes',
    'hypertension': 'prescriptions__research_data__comorbid_hypertension',
    'heart_failure': 'prescriptions__research_data__comorbid_heart_failure',
    'ischemic_heart_disease': 'prescriptions__research_data__comorbid_ischemic_heart_disease',
    'peripheral_artery_disease': 'prescriptions__research_data__comorbid_peripheral_artery_disease',
    'stroke': 'prescriptions__research_data__comorbid_stroke',
}

RESEARCH_MEDICATION_FIELDS = {
    'med_esa': 'prescriptions__research_data__med_esa',
    'med_iron': 'prescriptions__research_data__med_iron',
    'med_phosphate_binders': 'prescriptions__research_data__med_phosphate_binders',
    'med_vitamin_d': 'prescriptions__research_data__med_vitamin_d',
    'med_calcimimetics': 'prescriptions__research_data__med_calcimimetics',
    'med_ace_arb': 'prescriptions__research_data__med_ace_arb',
    'med_diuretics': 'prescriptions__research_data__med_diuretics',
    'med_statins': 'prescriptions__research_data__med_statins',
    'med_immunosuppressives': 'prescriptions__research_data__med_immunosuppressives',
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
        patient_qs = patient_qs.filter(prescriptions__research_data__education_level=education_level)

    employment_status = request.GET.get('employment_status', '').strip()
    if employment_status:
        patient_qs = patient_qs.filter(prescriptions__research_data__employment_status=employment_status)

    smoking_status = request.GET.get('smoking_status', '').strip()
    if smoking_status:
        patient_qs = patient_qs.filter(prescriptions__research_data__smoking_status=smoking_status)

    # --- Clinical history -------------------------------------------------------
    diagnosis = request.GET.get('diagnosis', '').strip()
    if diagnosis:
        patient_qs = patient_qs.filter(prescriptions__research_data__diagnosis__icontains=diagnosis)

    for param, field_lookup in RESEARCH_COMORBID_FIELDS.items():
        if request.GET.get(param) == '1':
            patient_qs = patient_qs.filter(**{field_lookup: True})

    # --- KRT ---------------------------------------------------------------
    krt_modality = request.GET.get('krt_modality', '').strip()
    if krt_modality:
        patient_qs = patient_qs.filter(prescriptions__research_data__krt_modality=krt_modality)

    vascular_access_type = request.GET.get('vascular_access_type', '').strip()
    if vascular_access_type:
        patient_qs = patient_qs.filter(prescriptions__research_data__vascular_access_type=vascular_access_type)

    krt_initiation_from = request.GET.get('krt_initiation_from', '').strip()
    if krt_initiation_from:
        patient_qs = patient_qs.filter(prescriptions__research_data__krt_initiation_date__gte=krt_initiation_from)

    krt_initiation_to = request.GET.get('krt_initiation_to', '').strip()
    if krt_initiation_to:
        patient_qs = patient_qs.filter(prescriptions__research_data__krt_initiation_date__lte=krt_initiation_to)

    # --- Medication data ---------------------------------------------------
    for param, field_lookup in RESEARCH_MEDICATION_FIELDS.items():
        if request.GET.get(param) == '1':
            patient_qs = patient_qs.filter(**{field_lookup: True})

    return patient_qs.distinct()


@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()
    patient_qs = Patient.objects.filter(doctor=request.user).order_by('-created_at')
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
        elif query.startswith('P'):
            try:
                num = int(query[1:])
                candidate = patient_qs.filter(id=num)
                if candidate.exists():
                    patient_qs = candidate
                    exact_id_match = True
            except (ValueError, IndexError):
                pass

        if not exact_id_match:
            # Regular text search across name/age/address and prescription data.
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

    # Advanced filters always apply, even on an exact ID match, so the two
    # can be combined (e.g. "P12" + "Diabetes only").
    patient_qs = apply_research_filters(patient_qs, request)

    paginator = Paginator(patient_qs, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "results": page_obj,
        "page_obj": page_obj,
        "total_count": Patient.objects.filter(doctor=request.user).count(),
        "search_count": paginator.count,
        "query": query,
        "gender_choices": Patient._meta.get_field('gender').choices,
        "education_choices": ClinicalResearchData.EDUCATION_CHOICES,
        "employment_choices": ClinicalResearchData.EMPLOYMENT_CHOICES,
        "smoking_choices": ClinicalResearchData.SMOKING_CHOICES,
        "modality_choices": ClinicalResearchData.MODALITY_CHOICES,
        "vascular_access_choices": ClinicalResearchData.VASCULAR_ACCESS_CHOICES,
        "selected_filters": request.GET,
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
                    patients = apply_research_filters(patients, request)
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

    patients = apply_research_filters(patients, request)
    return _generate_excel(patients, query)

def _generate_excel(patients, query=None):
    """Helper function to generate Excel file from patient queryset"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    # Column headers with formatted IDs
    headers = [
        'Patient ID', 'Name', 'Age', 'Gender', 'Address', 'Created Date',
        'Prescription IDs', 'Problems', 'Examinations', 'Reports', 'Medicines',
        # Research / registry columns (never shown on the PDF)
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

    # Set column widths
    column_widths = [15, 25, 10, 10, 30, 15, 20, 40, 40, 40, 40] + [20] * (len(headers) - 11)
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

        # Research/registry data (aggregated across all of the patient's prescriptions)
        education_levels, incomes, employment_statuses = [], [], []
        diagnoses, comorbidities, smoking_statuses = [], [], []
        bmis, weights, heights = [], [], []
        creatinines, cystatins, egfrs, uacrs, proteins = [], [], [], [], []
        hemoglobins, ferritins, calciums, phosphoruses, pths = [], [], [], [], []
        potassiums, bicarbonates, albumins, crps, cholesterols, hba1cs = [], [], [], [], [], []
        modalities, krt_dates, modality_changes, transplant_dates = [], [], [], []
        dialysis_durations, dialysis_frequencies, vascular_accesses = [], [], []
        kidney_meds, cardio_meds = [], []
        
        for pres in prescriptions:
            pres_ids.append(f"Pres{pres.id}")
            problems.extend(p.description for p in pres.problems.all())
            examinations.extend(e.description for e in pres.examinations.all())
            reports.extend(f"{r.name}: {r.result}" for r in pres.reports.all())
            medicines.extend(
                f"{m.name} ({m.strength}) - {m.frequency}" 
                for m in pres.medicines.all()
            )

            rd = getattr(pres, 'research_data', None)
            if rd:
                if rd.education_level: education_levels.append(rd.education_level)
                if rd.monthly_income: incomes.append(rd.monthly_income)
                if rd.employment_status: employment_statuses.append(rd.employment_status)
                if rd.diagnosis: diagnoses.append(rd.diagnosis)
                comorbidities.extend(rd.comorbidities_list())
                if rd.smoking_status: smoking_statuses.append(rd.smoking_status)
                if rd.bmi: bmis.append(rd.bmi)
                if rd.weight: weights.append(rd.weight)
                if rd.height: heights.append(rd.height)
                if rd.serum_creatinine: creatinines.append(rd.serum_creatinine)
                if rd.cystatin_c: cystatins.append(rd.cystatin_c)
                if rd.egfr: egfrs.append(rd.egfr)
                if rd.uacr: uacrs.append(rd.uacr)
                if rd.protein_levels: proteins.append(rd.protein_levels)
                if rd.hemoglobin: hemoglobins.append(rd.hemoglobin)
                if rd.ferritin: ferritins.append(rd.ferritin)
                if rd.calcium: calciums.append(rd.calcium)
                if rd.phosphorus: phosphoruses.append(rd.phosphorus)
                if rd.pth: pths.append(rd.pth)
                if rd.potassium: potassiums.append(rd.potassium)
                if rd.bicarbonate: bicarbonates.append(rd.bicarbonate)
                if rd.serum_albumin: albumins.append(rd.serum_albumin)
                if rd.crp: crps.append(rd.crp)
                if rd.total_cholesterol: cholesterols.append(rd.total_cholesterol)
                if rd.hba1c: hba1cs.append(rd.hba1c)
                if rd.krt_modality: modalities.append(rd.krt_modality)
                if rd.krt_initiation_date: krt_dates.append(rd.krt_initiation_date.strftime('%Y-%m-%d'))
                if rd.modality_change_dates: modality_changes.append(rd.modality_change_dates)
                if rd.transplant_date: transplant_dates.append(rd.transplant_date.strftime('%Y-%m-%d'))
                if rd.dialysis_duration: dialysis_durations.append(rd.dialysis_duration)
                if rd.dialysis_frequency: dialysis_frequencies.append(rd.dialysis_frequency)
                if rd.vascular_access_type: vascular_accesses.append(rd.vascular_access_type)
                kidney_meds.extend(rd.kidney_medications_list())
                cardio_meds.extend(rd.cardiovascular_medications_list())

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
            "\n".join(medicines),
            # Research / registry columns
            ", ".join(education_levels),
            ", ".join(incomes),
            ", ".join(employment_statuses),
            "\n".join(diagnoses),
            ", ".join(sorted(set(comorbidities))),
            ", ".join(smoking_statuses),
            ", ".join(bmis),
            ", ".join(weights),
            ", ".join(heights),
            ", ".join(creatinines),
            ", ".join(cystatins),
            ", ".join(egfrs),
            ", ".join(uacrs),
            ", ".join(proteins),
            ", ".join(hemoglobins),
            ", ".join(ferritins),
            ", ".join(calciums),
            ", ".join(phosphoruses),
            ", ".join(pths),
            ", ".join(potassiums),
            ", ".join(bicarbonates),
            ", ".join(albumins),
            ", ".join(crps),
            ", ".join(cholesterols),
            ", ".join(hba1cs),
            ", ".join(modalities),
            ", ".join(krt_dates),
            ", ".join(modality_changes),
            ", ".join(transplant_dates),
            ", ".join(dialysis_durations),
            ", ".join(dialysis_frequencies),
            ", ".join(vascular_accesses),
            ", ".join(sorted(set(kidney_meds))),
            ", ".join(sorted(set(cardio_meds))),
        ])

    # Enable Excel's native column filtering (AutoFilter) across the whole header/data range
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

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

    # Clinical research data scoped to the same filtered patients
    rd_qs = ClinicalResearchData.objects.filter(prescription__patient__in=qs)

    # Comorbidity prevalence with fallback
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

    # Smoking status distribution with fallback
    smoking_data = rd_qs.exclude(smoking_status="").values("smoking_status").annotate(count=Count("id"))
    smoking_labels = [s["smoking_status"] for s in smoking_data] or ["No Data"]
    smoking_values = [s["count"] for s in smoking_data] or [1]

    # KRT modality distribution with fallback
    krt_data = rd_qs.exclude(krt_modality="").values("krt_modality").annotate(count=Count("id"))
    krt_labels = [k["krt_modality"] for k in krt_data] or ["No Data"]
    krt_values = [k["count"] for k in krt_data] or [1]

    # Employment status distribution with fallback
    employment_data = (rd_qs.exclude(employment_status="")
                        .values("employment_status")
                        .annotate(count=Count("id"))
                        .order_by("-count"))
    employment_labels = [e["employment_status"] for e in employment_data] or ["No Data"]
    employment_counts = [e["count"] for e in employment_data] or [1]

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
        "comorbidity_labels": json.dumps(comorbidity_labels),
        "comorbidity_counts": json.dumps(comorbidity_counts),
        "smoking_labels": json.dumps(smoking_labels),
        "smoking_values": json.dumps(smoking_values),
        "krt_labels": json.dumps(krt_labels),
        "krt_values": json.dumps(krt_values),
        "employment_labels": json.dumps(employment_labels),
        "employment_counts": json.dumps(employment_counts),
        
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

@login_required
def patient_profile_view(request, patient_id):
    patient = get_object_or_404(
        Patient.objects.prefetch_related(
            'prescriptions__problems',
            'prescriptions__examinations',
            'prescriptions__reports',
            'prescriptions__medicines',
            'prescriptions__images',
            'prescriptions__research_data',
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
            'research_data': getattr(prescription, 'research_data', None),
        })
    
    # Collect all related data from all prescriptions
    all_problems = []
    all_examinations = []
    all_reports = []
    all_medicines = []
    all_images = []
    all_research_data = []
    
    for prescription in prescriptions:
        all_problems.extend(prescription.problems.all())
        all_examinations.extend(prescription.examinations.all())
        all_reports.extend(prescription.reports.all())
        all_medicines.extend(prescription.medicines.all())
        all_images.extend(prescription.images.all())
        research_data = getattr(prescription, 'research_data', None)
        if research_data is not None:
            all_research_data.append(research_data)

    # Most recent "Additional Patient Record" (education, comorbidities,
    # BMI/weight/height, labs, KRT, medications) shown in the profile section.
    latest_research_data = all_research_data[0] if all_research_data else None

    context = {
        'patient': patient,
        'patient_id_formatted': f"{patient.id:04d}",  # 4-digit patient ID
        'prescriptions': formatted_prescriptions,
        'problems': all_problems,
        'examinations': all_examinations,
        'reports': all_reports,
        'medicines': all_medicines,
        'images': all_images,
        'research_data_list': all_research_data,
        'latest_research_data': latest_research_data,
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
    Results are ranked: history first (most used, then most recent), then
    catalogue matches - and within each group, names that START WITH the
    full query outrank names that merely contain the tokens.
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

    # --- 1. Doctor's own prescribing history --------------------------------
    history_qs = (
        Medicine.objects
        .filter(prescription__patient__doctor=request.user)
        .filter(token_filter)
        .values('name')
        .annotate(
            total=Count('id'),
            last_used=Max('prescription__created_at'),
        )
        .order_by('-total', '-last_used')[:MAX_RESULTS]
    )

    history_results = []
    seen_names_lower = set()
    for row in history_qs:
        name = row['name']
        # Grab the most recently used strength/frequency/remark/days for
        # this medicine name so the frontend can auto-fill them.
        last_entry = (
            Medicine.objects
            .filter(prescription__patient__doctor=request.user, name=name)
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
                continue  # already suggested from history
            catalogue_results.append({
                'name': name,
                'source': 'catalog',
                'count': None,
                'strength': '',
                'frequency': '',
                'remark': '',
                'days': None,
            })
            seen_names_lower.add(name.lower())

        catalogue_results.sort(key=lambda r: (rank(r['name']), r['name'].lower()))
        catalogue_results = catalogue_results[:remaining_slots]

    data = history_results + catalogue_results
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