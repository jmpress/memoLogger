from django.shortcuts import render

# Create your views here.
import whisper
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.core.mail import send_mail
import os
import re
import threading
import pytz
from django.utils import timezone
from datetime import datetime

from .models import Recording, Transcription
from .serializers import RecordingSerializer, TranscriptionSerializer

# Whisper model loading - load once at startup
model = None

def home(request):
    """Home page view"""
    context = {
        'page_title': 'Voice Memo Transcription Service'
    }
    return render(request, 'transcriptionservice/index.html', context)

def get_whisper_model(model_size='base'):
    global model
    if model is None:
        model = whisper.load_model(model_size)
    return model

def transcribe_recording_task(recording_id, model_size='base'):
    """Background task to transcribe a recording"""
    try:
        recording = Recording.objects.get(id=recording_id)
        
        # Get the full path to the recording file
        file_path = os.path.join(settings.MEDIA_ROOT, recording.file.name)
        physical_file_path = file_path
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Recording file not found: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size < 100:
            error_message = "Audio file is too small or empty"
            print(error_message)
            Transcription.objects.create(
                recording=recording,
                text=f"Transcription failed: {error_message}",
                model_used=model_size
            )
            return False
        
        # Extract the original filename for reference to original recording time
        original_filename = os.path.basename(recording.file.name)
        timestamp_match = re.search(r'recording_(\d{8}_\d{6})', original_filename)
        original_timestamp = timestamp_match.group(1)
        
        # Load Whisper model and transcribe
        model = get_whisper_model(model_size)
        result = model.transcribe(file_path)
        
        # Create transcription object
        formatted_text = f"{result['text']}"
        
        transcription = Transcription.objects.create(
            recording=recording,
            text=formatted_text,
            model_used=model_size
        )
        
        # Send email notification if EMAIL_RECIPIENT is configured
        email_sent = False
        if hasattr(settings, 'EMAIL_RECIPIENT') and settings.EMAIL_RECIPIENT:
            try:
                subject = f"{original_timestamp}"
                send_mail(
                    subject=subject,
                    message=formatted_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_RECIPIENT],
                    fail_silently=False,
                )
                email_sent = True
                transcription.email_sent = True
                transcription.save()
                print(f"Email sent successfully for transcription {transcription.id}")

                 # Check if we should delete data after email
                if getattr(settings, 'DELETE_AFTER_EMAIL', True):
                    # Get the directory paths for cleanup
                    file_dir = os.path.dirname(physical_file_path)
                    date_dir = os.path.dirname(file_dir)
                    month_dir = os.path.dirname(date_dir)
                    year_dir = os.path.dirname(month_dir)
                    
                    # Delete the file
                    if os.path.exists(physical_file_path):
                        os.remove(physical_file_path)
                        print(f"Deleted physical file: {physical_file_path}")
                    
                        # Try to clean up empty directories, starting from deepest
                        try:
                            # Only remove directories if they're empty
                            if os.path.exists(file_dir) and not os.listdir(file_dir):
                                os.rmdir(file_dir)
                                print(f"Removed empty directory: {file_dir}")
                                
                                if os.path.exists(date_dir) and not os.listdir(date_dir):
                                    os.rmdir(date_dir)
                                    print(f"Removed empty directory: {date_dir}")
                                    
                                    if os.path.exists(month_dir) and not os.listdir(month_dir):
                                        os.rmdir(month_dir)
                                        print(f"Removed empty directory: {month_dir}")
                                        
                                        if os.path.exists(year_dir) and not os.listdir(year_dir):
                                            os.rmdir(year_dir)
                                            print(f"Removed empty directory: {year_dir}")
                        except Exception as e:
                            print(f"Error cleaning up directories: {str(e)}")
                    
                    # Store IDs for logging before deletion
                    transcription_id = transcription.id
                    recording_id = recording.id
                    
                    # Delete transcription first (due to foreign key constraint)
                    transcription.delete()
                    print(f"Deleted transcription record: {transcription_id}")
                    
                    # Then delete recording
                    recording.delete()
                    print(f"Deleted recording record: {recording_id}")
                    
                    print("Data cleanup completed successfully after email delivery")
                else:
                    print("Email sent, but data retention is enabled (DELETE_AFTER_EMAIL=False)")    
            except Exception as e:
                print(f"Error during email sending or data cleanup: {str(e)}")
                # If email failed but transcription was created, update it
                if transcription.id:
                    transcription.text += f"\n\nNote: Email delivery failed: {str(e)}"
                    transcription.save()
            
        # If we're not configured to send email, just return success
        if not email_sent and not hasattr(settings, 'EMAIL_RECIPIENT'):
            print("Email recipient not configured, transcription saved but not emailed")
        
        return True
    
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        
        # Create a failed transcription record
        Transcription.objects.create(
            recording=recording,
            text=f"Transcription failed: {str(e)}",
            model_used=model_size
        )
        
        return False

class RecordingViewSet(viewsets.ModelViewSet):
    queryset = Recording.objects.all().order_by('-created_at')
    serializer_class = RecordingSerializer
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Set default title if not provided
        if not serializer.validated_data.get('title'):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            serializer.validated_data['title'] = f"Recording {timestamp}"
        
        # Save the recording
        recording = serializer.save()
        
        # Start transcription in background
        thread = threading.Thread(
            target=transcribe_recording_task,
            args=(recording.id,)
        )
        thread.daemon = True
        thread.start()
    
    @action(detail=True, methods=['post'])
    def transcribe(self, request, pk=None):
        recording = self.get_object()
        model_size = request.data.get('model_size', 'base')
        
        # Start transcription in background
        thread = threading.Thread(
            target=transcribe_recording_task,
            args=(recording.id, model_size)
        )
        thread.daemon = True
        thread.start()
        
        return Response({'status': 'Transcription started'})

class TranscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transcription.objects.all().order_by('-created_at')
    serializer_class = TranscriptionSerializer
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def send_email(self, request, pk=None):
        transcription = self.get_object()
        recording = transcription.recording
        
        if not hasattr(settings, 'EMAIL_RECIPIENT'):
            return Response(
                {'error': 'Email recipient not configured'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        timestamp = recording.created_at.strftime("%Y-%m-%d %H:%M:%S")
        subject = f"{original_timestamp}"
        
        send_mail(
            subject=subject,
            message=transcription.text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_RECIPIENT],
            fail_silently=False,
        )
        
        transcription.email_sent = True
        transcription.save()
        
        return Response({'status': 'Email sent'})
