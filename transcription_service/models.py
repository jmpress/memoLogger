from django.db import models
import os
import uuid

def recording_file_path(instance, filename):
    # Generate a path for the recording file
    # Format: YYYY/MM/DD/filename_uuid.ext
    from datetime import datetime
    
    #ext = filename.split('.')[-1]
    #og_timestamp=filename.split('.')[0]
    #print(og_timestamp)
    #filename = f"{uuid.uuid4()}.{ext}"
    
    # Use current date instead of instance.created_at
    current_date = datetime.now()
    date_path = current_date.strftime("%Y/%m/%d")
    
    return os.path.join('recordings', date_path, filename)

class Recording(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=recording_file_path)
    created_at = models.DateTimeField(auto_now_add=True)
    device_id = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return self.title or f"Recording {self.id}"

class Transcription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField(Recording, on_delete=models.CASCADE, related_name='transcription')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    model_used = models.CharField(max_length=50, default='base')
    email_sent = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Transcription for {self.recording}"
