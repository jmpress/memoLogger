from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Recording, Transcription

@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at', 'device_id')
    search_fields = ('title', 'device_id')
    list_filter = ('created_at',)
    date_hierarchy = 'created_at'

@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'recording', 'created_at', 'model_used', 'email_sent')
    search_fields = ('text',)
    list_filter = ('created_at', 'model_used', 'email_sent')
    date_hierarchy = 'created_at'
