from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .forms import DoctorProfileUpdateForm, DoctorRegistrationForm, DoctorLoginForm, PatientForm
from .models import *
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
import openpyxl
import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import datetime
from django.shortcuts import get_object_or_404
from django.contrib import messages
import plotly.graph_objects as go
import plotly.io as pio          
from django.core.paginator import Paginator
from calendar import month_name
from django.db.models.functions import ExtractYear, ExtractMonth
from django.contrib.auth import get_user
from django.db.models.functions import TruncDay 
from django.db.models.functions import Lower
from django.db.models import F, Value, IntegerField

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
            form.save()  
            return redirect('profile')
    else:
        form = DoctorProfileUpdateForm(instance=doctor)
    return render(request, 'app/profile.html', {'form': form, 'doctor': doctor})

@login_required
def prescribe_view(request):
    if request.method == 'POST':
        patient_form = PatientForm(request.POST)
        if patient_form.is_valid():
            patient = patient_form.save(commit=False)
            patient.doctor = request.user
            patient.save()

            for prob in request.POST.getlist('problems'):
                if prob.strip():
                    Problem.objects.create(patient=patient, description=prob)

            for exam in request.POST.getlist('examinations'):
                if exam.strip():
                    Examination.objects.create(patient=patient, description=exam)

            names = request.POST.getlist('report_names')
            results = request.POST.getlist('report_results')
            for name, result in zip(names, results):
                if name.strip() and result.strip():
                    Report.objects.create(patient=patient, name=name, result=result)

            for img in request.FILES.getlist('report_images'):
                ReportImage.objects.create(patient=patient, image=img)

            med_names = request.POST.getlist('medicine_names')
            med_days = request.POST.getlist('medicine_days')
            med_strengths = request.POST.getlist('medicine_strengths')
            med_frequencies = request.POST.getlist('medicine_frequencies')
            med_remarks = request.POST.getlist('medicine_remarks')

            for name, days, strength, freq, remark in zip(med_names, med_days, med_strengths, med_frequencies, med_remarks):
                if name.strip() and strength.strip():
                    Medicine.objects.create(
                        patient=patient,
                        name=name,
                        strength=strength,
                        frequency=freq,
                        remark=remark,
                        days=int(days)
                    )

            return redirect('prescription_pdf', patient_id=patient.id)
    else:
        patient_form = PatientForm()
    return render(request, 'app/prescribe.html', {'form': patient_form})

@login_required
def prescription_pdf(request, patient_id):
    """
    Generate a PDF for one patient’s prescription with
    date/time and auto‑formatted prescription number.
    """
    patient = get_object_or_404(Patient, id=patient_id, doctor=request.user)

    # --- timestamp & prescription number ---
    now  = datetime.now()
    year = now.year
    sequence = f"{patient.id:05d}"
    prescription_no = f"RX-{year}-{sequence}"

    # --- context for template ---
    context = {
        'patient':          patient,
        'doctor':           request.user,
        'date':             now.strftime("%d %b %Y"),  
        'time':             now.strftime("%I:%M %p"),
        'year':             year,
        'prescription_id':  sequence,
        'prescription_no':  prescription_no,  
    }

    html = render_to_string('app/prescription_pdf.html', context)

    # base_url lets WeasyPrint fetch remote imgs / CSS
    pdf_file = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

    filename = f"prescription_{patient.name}_{prescription_no}.pdf"
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    return response

@login_required
def search_view(request):
    query = request.GET.get('q', '').strip()

    # ── Count every patient that belongs to the doctor ─────────────
    total_count = Patient.objects.filter(doctor=request.user).count()

    # ── Base queryset with prefetches ───────────────────────────────
    patient_qs = (
        Patient.objects
        .filter(doctor=request.user)
        .prefetch_related('images', 'reports', 'problems',
                          'examinations', 'medicines')
    )

    # ── Filter for search terms ─────────────────────────────────────
    if query:
        patient_qs = patient_qs.filter(
            Q(name__icontains=query) |
            Q(age__icontains=query) |
            Q(address__icontains=query) |
            Q(problems__description__icontains=query) |
            Q(examinations__description__icontains=query) |
            Q(reports__name__icontains=query) |
            Q(reports__result__icontains=query) |
            Q(medicines__name__icontains=query) |
            Q(medicines__strength__icontains=query) |
            Q(medicines__frequency__icontains=query) |
            Q(medicines__remark__icontains=query)
        ).distinct()

    # ── Pagination (5 per page) ─────────────────────────────────────
    paginator   = Paginator(patient_qs, 5)
    page_number = request.GET.get("page")
    page_obj    = paginator.get_page(page_number)

    # Number of rows that matched the current search:
    search_count = paginator.count        # same as patient_qs.count()

    context = {
        "results":      page_obj,         # iterable in template
        "page_obj":     page_obj,         # pagination helpers
        "total_count":  total_count,      # every patient you own
        "search_count": search_count,     # rows after filtering
        "query":        query,
    }
    return render(request, "app/search.html", context)

@login_required
def export_excel(request):
    query = request.GET.get('q', '')
    patients = Patient.objects.filter(doctor=request.user)

    if query:
        patients = patients.filter(
            Q(name__icontains=query) |
            Q(age__icontains=query) |
            Q(address__icontains=query) |
            Q(problems__description__icontains=query) |
            Q(examinations__description__icontains=query) |
            Q(reports__name__icontains=query) |
            Q(reports__result__icontains=query) |
            Q(medicines__name__icontains=query) |
            Q(medicines__strength__icontains=query) |
            Q(medicines__frequency__icontains=query) |
            Q(medicines__remark__icontains=query)
        ).distinct()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Patients"

    # Column headers
    ws.append([
        'Name', 'Age', 'Address',
        'Problems', 'Examinations', 'Reports',
        'Medicine Names', 'Strengths', 'Frequencies', 'Remarks', 'Days'
    ])

    for patient in patients:
        problems = ", ".join(p.description for p in patient.problems.all())
        exams = ", ".join(e.description for e in patient.examinations.all())
        reports = ", ".join(f"{r.name}: {r.result}" for r in patient.reports.all())

        # Extract each medicine field into separate lists
        med_names = ", ".join(m.name for m in patient.medicines.all())
        strengths = ", ".join(m.strength for m in patient.medicines.all())
        frequencies = ", ".join(m.frequency for m in patient.medicines.all())
        remarks = ", ".join(m.remark for m in patient.medicines.all())
        days = ", ".join(str(m.days) for m in patient.medicines.all())

        ws.append([
            patient.name, patient.age, patient.address,
            problems, exams, reports,
            med_names, strengths, frequencies, remarks, days
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=search_results.xlsx'
    wb.save(response)
    return response


from django.utils import timezone
from django.db.models.functions import ExtractYear

@login_required
def analysis_view(request):
    """
    Charts for one doctor, filtered by ?year=YYYY and optional ?month=MM.
    *  month = 'all' or omitted  ->  whole‑year view   (x = Jan…Dec)
    *  month = '01' … '12'       ->  single‑month view (x = 1…31)
    """

    # ───────────────────────────────────────────────────────────
    now = timezone.now()
    try:
        sel_year = int(request.GET.get("year", now.year))
    except ValueError:
        sel_year = now.year

    month_param     = request.GET.get("month", "all")     # 'all' | '01'..'12'
    sel_month       = int(month_param) if month_param.isdigit() else None
    show_daily_view = sel_month is not None               # bool helper
    x_axis_title    = "Day" if show_daily_view else "Month"
    x_axis_type     = "category" if show_daily_view else "category"  # always categorical

    # ─── secure base queryset ─────────────────────────────────
    user = get_user(request)
    if not user.is_authenticated:
        return redirect("login")

    qs = Patient.objects.filter(doctor=user, created_at__year=sel_year)
    if show_daily_view:
        qs = qs.filter(created_at__month=sel_month)

    # ─── gender pie ───────────────────────────────────────────
    gender_data   = qs.exclude(gender="").values("gender").annotate(count=Count("id"))
    gender_labels = [g["gender"] for g in gender_data]
    gender_values = [g["count"]  for g in gender_data]

    # ─── top 10 medicines ─────────────────────────────────────
    med_qs        = Medicine.objects.filter(patient__in=qs)
    med_data      = (med_qs.values("name")
                            .annotate(count=Count("id"))
                            .order_by("-count")[:10])
    medicine_labels  = [m["name"]  for m in med_data]
    medicine_values  = [m["count"] for m in med_data]

    # ─── problems, ages, address pie (unchanged logic) ───────
    prob_data   = (Problem.objects.filter(patient__in=qs)
                               .values("description")
                               .annotate(count=Count("id"))
                               .order_by("-count")[:10])
    problem_labels      = [p["description"] for p in prob_data]
    problem_age_counts  = [p["count"]       for p in prob_data]

    age_data  = (qs.values("age")
                   .annotate(count=Count("id"))
                   .order_by("-count")[:10])
    age_labels = [a["age"]   for a in age_data]
    age_counts = [a["count"] for a in age_data]

    addr_data = (qs.exclude(address="")
                   .values("address")
                   .annotate(count=Count("id"))
                   .order_by("-count")[:5])
    address_labels = [a["address"] for a in addr_data]
    address_counts = [a["count"]   for a in addr_data]

    # ─── time‑series line  (month OR day) ─────────────────────
    if show_daily_view:
        day_data = (qs.annotate(d=TruncDay("created_at"))
                       .values("d")
                       .annotate(count=Count("id"))
                       .order_by("d"))
        monthly_labels  = [str(d["d"].day).zfill(2) for d in day_data]   # '01'…'31'
        monthly_counts  = [d["count"] for d in day_data]
    else:
        month_data = (qs.annotate(m=ExtractMonth("created_at"))
                        .values("m")
                        .annotate(count=Count("id"))
                        .order_by("m"))
        monthly_labels  = [month_name[m["m"]][:3] for m in month_data]   # 'Jan'…'Dec'
        monthly_counts  = [m["count"] for m in month_data]

    # ─── dropdown helpers ─────────────────────────────────────
    available_years = (Patient.objects.filter(doctor=user)
                       .annotate(y=ExtractYear("created_at"))
                       .values_list("y", flat=True)
                       .distinct().order_by("-y"))

    available_months = (Patient.objects.filter(doctor=user,
                                               created_at__year=sel_year)
                        .annotate(m=ExtractMonth("created_at"))
                        .values_list("m", flat=True)
                        .distinct().order_by("m"))

    month_options = (
        [{"value": "all", "label": "All", "selected": not show_daily_view}] +
        [{"value": f"{m:02d}",
          "label": month_name[m],
          "selected": m == sel_month}
         for m in available_months]
    )

    # ─── render ───────────────────────────────────────────────
    return render(
        request,
        "app/analysis.html",
        {
            "gender_labels":      json.dumps(gender_labels),
            "gender_values":      json.dumps(gender_values),
            "medicine_labels":    json.dumps(medicine_labels),
            "medicine_values":    json.dumps(medicine_values),
            "problem_labels":     json.dumps(problem_labels),
            "problem_age_counts": json.dumps(problem_age_counts),
            "age_labels":         json.dumps(age_labels),
            "age_counts":         json.dumps(age_counts),
            "monthly_labels":     json.dumps(monthly_labels),
            "monthly_counts":     json.dumps(monthly_counts),
            "address_labels":     json.dumps(address_labels),
            "address_counts":     json.dumps(address_counts),

            "available_years": available_years,
            "month_options":   month_options,
            "selected_year":   sel_year,
            "month_param":     month_param,          # keep raw value for template
            "x_axis_title":    x_axis_title,
            "x_axis_type":     x_axis_type,
        },
    )


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
    """Return medicine names + usage count for this doctor matching ?q=."""
    q = request.GET.get('q', '').strip()
    meds = (Medicine.objects
            .filter(patient__doctor=request.user, name__icontains=q)
            .values('name')
            .annotate(total=Count('id'))
            .order_by('-total')[:10])

    data = [{'name': m['name'], 'count': m['total']} for m in meds]
    return JsonResponse(data, safe=False)


@require_GET
@login_required
def problem_to_medicine(request):
    """
    ?q=headache      → JSON [{name:"Paracetamol", score:12}, …]
    Ranking = (# previous prescriptions by doctor) DESC, then alphabetic.
    """
    q = request.GET.get("q", "").lower().strip()
    if not q:
        return JsonResponse([], safe=False)

    # match keywords in master table
    kw_filter = MedicineMaster.objects.filter(
        keywords__icontains=q     # crude but fast for a demo
    ).values("id", "name")

    # nothing found → return empty
    if not kw_filter:
        return JsonResponse([], safe=False)

    # count how many times *this doctor* already used each drug
    usage = (Medicine.objects
             .filter(patient__doctor=request.user,
                     name__in=[m["name"] for m in kw_filter])
             .values("name")
             .annotate(cnt=Count("id")))

    usage_map = {u["name"]: u["cnt"] for u in usage}

    # combine & sort
    suggestions = [
        {"name": m["name"], "count": usage_map.get(m["name"], 0)}
        for m in kw_filter
    ]
    suggestions.sort(key=lambda d: (-d["count"], d["name"]))

    return JsonResponse(suggestions[:10], safe=False)
