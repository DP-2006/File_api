from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import ScanJob, EngineResult, EngineStatus


class EngineResultInline(admin.TabularInline):
    model = EngineResult
    extra = 0
    readonly_fields = ('engine_name', 'score', 'threat', 'details',
                       'duration_ms', 'error', 'created_at')


@admin.register(ScanJob)
class ScanJobAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'final_score', 'severity', 'is_threat',
                    'status', 'completed_engines', 'total_engines',
                    'scanned_by', 'started_at')
    list_filter = ('severity', 'is_threat', 'status')
    search_fields = ('file_name', 'file_hash_sha256')
    readonly_fields = ('id', 'file_hash_sha256', 'started_at', 'finished_at',
                       'celery_task_id')
    inlines = [EngineResultInline]


@admin.register(EngineStatus)
class EngineStatusAdmin(admin.ModelAdmin):
    list_display = ('engine_name', 'is_active', 'version', 'last_check')