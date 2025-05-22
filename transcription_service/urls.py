# transcription_service/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecordingViewSet, TranscriptionViewSet

router = DefaultRouter()
router.register(r'recordings', RecordingViewSet)  # Make sure this line exists
router.register(r'transcriptions', TranscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
