<div align="center">

# MultiRx

### A Django-based Digital Prescription & CKD Clinical Registry Platform

Built and maintained by developers of **JSTU** (Jatiya Sheikh Hasina Textile Engineering College... *Dept. of CSE*)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](Dockerfile)

</div>

---
<img width="1763" height="2107" alt="image" src="https://github.com/user-attachments/assets/2f09433d-655b-49d5-91b1-a10cc3c8e6cc" />
---
## Table of Contents

- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [System Architecture](#-system-architecture)
- [Database Schema (ERD)](#-database-schema-erd)
- [Application Flow](#-application-flow)
  - [Prescription Creation Flow](#prescription-creation-flow)
  - [Authentication Flow](#authentication-flow)
  - [Analytics Data Flow](#analytics-data-flow)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
  - [Local Setup (Python/venv)](#local-setup-pythonvenv)
  - [Docker Setup](#docker-setup)
- [Environment Variables](#-environment-variables)
- [URL / Route Map](#-url--route-map)
- [Deployment](#-deployment)
- [Screens & Modules Overview](#-screens--modules-overview)
- [Contributing](#-contributing)
- [License](#-license)
- [Contact](#-contact)

---

## About the Project

**MultiRx** is a full-stack web application built with **Django** that helps doctors digitize the entire
prescription workflow — from registering a patient, writing a structured prescription (problems,
examinations, reports, medicines), generating a printable **PDF prescription**, to maintaining a
dedicated **CKD (Chronic Kidney Disease) clinical research registry** and visual **analytics dashboard**.

It was designed for a single-doctor/clinic use case where each **Doctor** account manages their own
patients, prescriptions, and research data, with medicine name autocompletion powered by a bulk-imported
medicine master catalogue.

---

## Key Features

| Module | Description |
|---|---|
| **Custom Doctor Auth** | Custom `Doctor` user model (`doctor_id` based login, no username) with restricted, whitelisted registration (`doctor_id` must start with `HF`) |
| **Patient Management** | Create, search, view profile & delete patients, scoped per-doctor |
| **Structured Prescriptions** | Add multiple **Problems**, **Examinations**, **Reports** (+ uploaded report images), and **Medicines** per prescription |
| **PDF Prescription Generator** | Auto-generates a print-ready, hospital-letterhead-styled prescription PDF using **WeasyPrint**, with Bangla font support |
| **Clinical Research Registry** | A dedicated post-prescription form capturing CKD-specific data: comorbidities, KRT modality, labs (eGFR, uACR, HbA1c, etc.), medications, socio-economic data — kept **out** of the printed PDF, used only for registry/analytics |
| **Analytics Dashboard** | Interactive Plotly charts: gender split, age distribution, address distribution, top medicines, top problems, monthly trend, comorbidity prevalence, smoking status, KRT modality, employment status — filterable by year/month |
| **Smart Search & Filters** | Search patients with advanced research-data filters (diagnosis, comorbidities, KRT modality, smoking, etc.) |
| **Excel Export** | Export filtered patient/prescription data to `.xlsx` via `openpyxl` |
| **Autocomplete APIs** | AJAX autocomplete endpoints for Problems, Examinations, Reports, and Medicines (backed by a `MedicineMaster` catalogue imported from CSV) |
| **Profile Management** | Doctor profile picture upload/change |
| **Docker & Render Ready** | Ships with a `Dockerfile`, `entrypoint.sh`, and `render.yaml` for one-click containerized deployment |

---

## Tech Stack

- **Backend:** Django 5 (Python 3.11)
- **Database:** SQLite (dev) / PostgreSQL via `dj-database-url` (production)
- **PDF Generation:** WeasyPrint + custom Bangla (`TiroBangla`, `NotoSansBengali`) fonts
- **Frontend:** Django Templates + Tailwind CSS (CDN) + Font Awesome
- **Charts:** Plotly.js
- **Static Files:** WhiteNoise
- **Data Export:** openpyxl (Excel)
- **App Server:** Gunicorn
- **Containerization:** Docker

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Client (Browser)"]
        UI["Doctor's Browser<br/>Tailwind UI + Plotly.js"]
    end

    subgraph Server["Django Application (multirx project)"]
        URLS["urls.py<br/>Routing Layer"]
        VIEWS["app/views.py<br/>Business Logic"]
        FORMS["app/forms.py<br/>Validation"]
        MODELS["app/models.py<br/>ORM Models"]
        TEMPLATES["app/templates/app/*.html<br/>Django Template Engine"]
        PDFGEN["WeasyPrint Engine<br/>prescription_pdf.html → PDF"]
        EXPORT["openpyxl<br/>Excel Export"]
    end

    subgraph Data["Persistence"]
        DB[("PostgreSQL / SQLite<br/>db")]
        MEDIA["Media Storage<br/>profile_pics/, report_images/"]
        STATIC["Static Files<br/>(WhiteNoise)"]
    end

    UI -- "HTTP Request" --> URLS
    URLS --> VIEWS
    VIEWS --> FORMS
    VIEWS --> MODELS
    MODELS <--> DB
    VIEWS --> TEMPLATES
    TEMPLATES -- "rendered HTML" --> UI
    VIEWS --> PDFGEN
    PDFGEN -- "PDF response" --> UI
    VIEWS --> EXPORT
    EXPORT -- ".xlsx response" --> UI
    VIEWS <--> MEDIA
    STATIC --> UI

    style Client fill:#e6fffa,stroke:#0a9c7d
    style Server fill:#f0fdfa,stroke:#0a9c7d
    style Data fill:#fff7ed,stroke:#c2410c
```

---

## Database Schema (ERD)

The schema is centered on a **Doctor → Patient → Prescription** hierarchy. Each `Prescription` fans out
into `Problem`, `Examination`, `Report`, `ReportImage`, `Medicine` (all printed on the PDF), and
optionally **one** `ClinicalResearchData` record (internal registry data only). A standalone
`MedicineMaster` table powers autocomplete and is not relationally tied to prescriptions.

```mermaid
erDiagram
    DOCTOR ||--o{ PATIENT : "treats"
    PATIENT ||--o{ PRESCRIPTION : "has"
    PRESCRIPTION ||--o{ PROBLEM : "lists"
    PRESCRIPTION ||--o{ EXAMINATION : "records"
    PRESCRIPTION ||--o{ REPORT : "orders"
    PRESCRIPTION ||--o{ REPORTIMAGE : "attaches"
    PRESCRIPTION ||--o{ MEDICINE : "prescribes"
    PRESCRIPTION ||--o| CLINICALRESEARCHDATA : "extends with"

    DOCTOR {
        int id PK
        string doctor_id UK "login ID, e.g. HF0001"
        string password
        string first_name
        string last_name
        string email
        string specialization
        text bio
        image profile_picture
        bool is_staff
        bool is_superuser
    }

    PATIENT {
        int id PK
        int doctor_id FK
        string name
        int age
        string gender "Male / Female"
        string address
        datetime created_at
    }

    PRESCRIPTION {
        int id PK
        int patient_id FK
        datetime created_at
    }

    PROBLEM {
        int id PK
        int prescription_id FK
        string description
    }

    EXAMINATION {
        int id PK
        int prescription_id FK
        string name
        string description
    }

    REPORT {
        int id PK
        int prescription_id FK
        string name
        string result
    }

    REPORTIMAGE {
        int id PK
        int prescription_id FK
        image image
    }

    MEDICINE {
        int id PK
        int prescription_id FK
        string name
        string strength "e.g. 500mg"
        string frequency "e.g. 1+1+1"
        string remark "e.g. After Eat"
        int days
    }

    MEDICINEMASTER {
        int id PK
        string name UK "indexed catalogue name"
        text uses_raw
    }

    CLINICALRESEARCHDATA {
        int id PK
        int prescription_id FK "OneToOne"
        string education_level
        string monthly_income
        string employment_status
        string diagnosis
        bool comorbid_diabetes
        bool comorbid_hypertension
        bool comorbid_heart_failure
        bool comorbid_ischemic_heart_disease
        bool comorbid_peripheral_artery_disease
        bool comorbid_stroke
        string smoking_status
        string bmi "auto-computed"
        string weight
        string height
        string serum_creatinine
        string cystatin_c
        string egfr
        string uacr
        string protein_levels
        string hemoglobin
        string ferritin
        string calcium
        string phosphorus
        string pth
        string potassium
        string bicarbonate
        string serum_albumin
        string crp
        string total_cholesterol
        string hba1c
        string krt_modality
        date krt_initiation_date
        string modality_change_dates
        date transplant_date
        string dialysis_duration
        string dialysis_frequency
        string vascular_access_type
        bool med_esa
        bool med_iron
        bool med_phosphate_binders
        bool med_vitamin_d
        bool med_calcimimetics
        bool med_ace_arb
        bool med_diuretics
        bool med_statins
        bool med_immunosuppressives
        datetime created_at
        datetime updated_at
    }
```

> **Note:** `MEDICINEMASTER` is intentionally disconnected from `MEDICINE` in the schema — it's a
> read-only reference catalogue (imported via `manage.py import_medicines` from `data/Medicines.csv`)
> used purely to power the medicine-name autocomplete field, not a foreign key relationship.

---

## Application Flow

### Prescription Creation Flow

```mermaid
sequenceDiagram
    actor Dr as Doctor
    participant UI as Prescribe Page
    participant View as prescribe_view()
    participant DB as Database
    participant RD as Research Data Page
    participant PDF as prescription_pdf()
    participant Weasy as WeasyPrint

    Dr->>UI: Search/select or create Patient
    UI->>View: POST patient + problems + exams + reports + medicines
    View->>DB: Create Patient (if new)
    View->>DB: Create Prescription
    View->>DB: Bulk create Problem/Examination/Report/ReportImage/Medicine
    DB-->>View: Saved records
    View-->>Dr: Redirect to Research Data form
    Dr->>RD: Fill CKD registry data (labs, comorbidities, KRT, meds)
    RD->>DB: Create/Update ClinicalResearchData (OneToOne)
    Dr->>PDF: Click "Generate PDF"
    PDF->>DB: Fetch Prescription + related sets (prefetch_related)
    PDF->>Weasy: render_to_string(prescription_pdf.html) → HTML.write_pdf()
    Weasy-->>Dr: Download prescription.pdf
```

### Authentication Flow

```mermaid
flowchart LR
    A["Visitor lands on Login page"] --> B{"doctor_id + password"}
    B -- "valid, HF-prefixed & registered" --> C["authenticate() via DoctorManager"]
    C --> D["Django session created"]
    D --> E["Redirect to Home (dashboard)"]
    B -- "invalid" --> F["Show form errors"]

    G["New Doctor Registration"] --> H{"doctor_id starts with 'HF'<br/>and length == 6?"}
    H -- "No" --> I["Reject: private website"]
    H -- "Yes, unique" --> J["Create Doctor account"]
    J --> A
```

### Analytics Data Flow

```mermaid
flowchart TB
    A["Analysis Dashboard Request<br/>+ optional year/month filters"] --> B["analysis_view()"]
    B --> C["Patient queryset<br/>filtered by doctor + year/month"]
    C --> D1["Gender distribution"]
    C --> D2["Age distribution"]
    C --> D3["Address distribution"]
    C --> D4["Monthly / daily trend"]
    C --> E["ClinicalResearchData queryset<br/>(joined via prescription__patient__in)"]
    E --> F1["Comorbidity prevalence"]
    E --> F2["Smoking status"]
    E --> F3["KRT modality"]
    E --> F4["Employment status"]
    B --> G["Medicine / Problem aggregation<br/>(Count + order_by)"]
    D1 & D2 & D3 & D4 & F1 & F2 & F3 & F4 & G --> H["JSON-serialized context"]
    H --> I["analysis.html + Plotly.js"]
    I --> J["Interactive charts rendered in browser"]
```

---

## Project Structure

```
MultiRx-JSTU/
├── manage.py
├── requirements.txt
├── Dockerfile
├── entrypoint.sh
├── render.yaml
├── LICENSE
├── data/
│   └── Medicines.csv                # Master medicine catalogue seed data
├── multirx/                         # Django project package
│   ├── settings.py
│   ├── urls.py                      # Root URL routing
│   ├── asgi.py / wsgi.py
├── app/                             # Main Django app
│   ├── models.py                    # Doctor, Patient, Prescription, Problem,
│   │                                 # Examination, Report, ReportImage, Medicine,
│   │                                 # MedicineMaster, ClinicalResearchData
│   ├── views.py                     # All business logic / request handlers
│   ├── forms.py                     # PatientForm, DoctorRegistrationForm, etc.
│   ├── backends.py                  # Custom auth backend for Doctor login
│   ├── admin.py
│   ├── management/commands/
│   │   └── import_medicines.py      # Bulk-imports data/Medicines.csv → MedicineMaster
│   ├── templatetags/
│   │   └── custom_filters.py        # e.g. duration_bn (Bangla duration formatting)
│   ├── migrations/
│   ├── static/app/
│   │   ├── images/                  # Logo, hero images
│   │   └── fonts/                   # NotoSansBengali, TiroBangla (for PDF)
│   └── templates/app/
│       ├── base.html                # Shared layout, navbar, footer, dev modal
│       ├── home.html
│       ├── login.html / register.html
│       ├── profile.html / profile_pic_change.html
│       ├── prescribe.html           # New prescription form
│       ├── prescription_pdf.html    # WeasyPrint PDF template
│       ├── research_data.html       # CKD registry form
│       ├── search.html              # Patient search + filters
│       ├── patient_profile.html     # Full patient history
│       ├── analysis.html            # Plotly analytics dashboard
│       └── confirm_delete.html
└── media/                           # User-uploaded content (runtime)
    ├── profile_pics/
    └── report_images/
```

---

## Installation & Setup

### Local Setup (Python/venv)

```bash
# 1. Clone the repository
git clone https://github.com/Himel-Sarder/MultiRx-JSTU.git
cd MultiRx-JSTU

# 2. Create & activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply database migrations
python manage.py migrate

# 5. (Optional) seed the medicine catalogue used for autocomplete
python manage.py import_medicines

# 6. Create a superuser (Doctor account, doctor_id must start with "HF")
python manage.py createsuperuser

# 7. Run the development server
python manage.py runserver
```

The app will be available at **http://127.0.0.1:8000/**.

### Docker Setup

```bash
docker build -t multirx .
docker run -p 8000:8000 --env-file .env multirx
```

The provided `entrypoint.sh` automatically runs migrations, refreshes the medicine catalogue, then
starts Gunicorn on container boot.

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key | `django-insecure-...` |
| `DEBUG` | Toggle debug mode | `True` / `False` |
| `DATABASE_URL` | Full DB connection string (via `dj-database-url`) | `postgres://user:pass@host:5432/dbname` |
| `PORT` | Port Gunicorn binds to (used by `entrypoint.sh`) | `8000` |

If `DATABASE_URL` isn't set, the app falls back to a local `sqlite:///db.sqlite3` file.

---

## 🗺 URL / Route Map

| Path | View | Purpose |
|---|---|---|
| `/` | `home_view` | Landing / dashboard |
| `/login/`, `/register/`, `/logout/` | auth views | Doctor authentication |
| `/profile/` | `profile_view` | Doctor profile |
| `/profile/picture/change/`, `/profile/picture/update/` | profile picture views | Avatar management |
| `/prescribe/` | `prescribe_view` | Create a new prescription (new patient) |
| `/prescribe/<patient_id>/` | `prescribe_with_patient` | New prescription for existing patient |
| `/prescription/<id>/pdf/` | `prescription_pdf` | Generate/download PDF |
| `/prescription/<id>/research-data/` | `research_data_view` | CKD registry form |
| `/search/` | `search_view` | Patient search + filters |
| `/search/export/` | `export_excel` | Export results to Excel |
| `/patient/<id>/` | `patient_profile_view` | Full patient history |
| `/patient/<id>/delete/` | `delete_patient` | Delete a patient record |
| `/analysis/` | `analysis_view` | Analytics dashboard |
| `/autocomplete/problem/`, `/report/`, `/medicine/`, `/examination/` | autocomplete APIs | AJAX suggestions |
| `/api/medicines/` | `medicine_autocomplete` | Medicine search API |
| `/admin/` | Django admin | Backend administration |

---

## Deployment

MultiRx ships ready for containerized deployment:

- **`Dockerfile`** — Python 3.11 base image with all native dependencies WeasyPrint needs (Cairo, Pango,
  GDK-Pixbuf, etc.), installs requirements, collects static files, and runs `entrypoint.sh`.
- **`entrypoint.sh`** — runs migrations → refreshes the medicine catalogue → starts
  `gunicorn multirx.wsgi:application`.
- **`render.yaml`** — Render.com blueprint for one-click deploy with a managed PostgreSQL database and
  auto-generated `SECRET_KEY`.
- **WhiteNoise** serves static assets directly from the Django app in production.

---

## Screens & Modules Overview

- **Home** — Landing dashboard for logged-in doctors.
- **Prescribe** — Structured form to capture patient details, problems, examinations, reports (with
  image upload), and medicines with strength/frequency/remark/duration.
- **Research Data** — A secondary, PDF-excluded form capturing CKD-specific clinical registry fields
  (comorbidities, labs, KRT modality, medications, socio-economic data) with auto-calculated BMI.
- **Prescription PDF** — A hospital-letterhead-styled, Bangla-font-capable, print-ready A4 PDF generated
  with WeasyPrint.
- **Search** — Advanced patient search with research-data-aware filters and Excel export.
- **Patient Profile** — Full prescription history and timeline for a single patient.
- **Analysis** — Plotly-powered dashboard: demographics, medicine/problem frequency, monthly trends,
  comorbidity prevalence, smoking status, KRT modality, and employment status — filterable by year/month.

---

## Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## Contact

**Himel Sarder**
Dept. of CSE, JSTU · Session 2021–22
info.himelcse@gmail.com

**Supervised by:** Dr. Mahmudul Alam, Assistant Professor, JSTU
mahmudul@jstu.ac.bd
