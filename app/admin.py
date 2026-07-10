from django.contrib import admin
from app.models import Doctor, Patient, Report, Problem, Examination, Medicine, ReportImage, ClinicalResearchData

# Register your models here.
admin.site.register(Doctor)
admin.site.register(Patient)
admin.site.register(Report)
admin.site.register(Problem)
admin.site.register(Examination)
admin.site.register(Medicine)
admin.site.register(ReportImage)
admin.site.register(ClinicalResearchData)
