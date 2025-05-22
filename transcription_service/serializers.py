from rest_framework import serializers
from .models import Recording, Transcription

class RecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recording
        fields = ['id', 'title', 'file', 'created_at', 'device_id']
        read_only_fields = ['id', 'created_at']

class TranscriptionSerializer(serializers.ModelSerializer):
    recording_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Transcription
        fields = ['id', 'recording_id', 'text', 'created_at', 'model_used', 'email_sent']
        read_only_fields = ['id', 'text', 'created_at', 'email_sent']
    
    def create(self, validated_data):
        recording_id = validated_data.pop('recording_id')
        recording = Recording.objects.get(id=recording_id)
        transcription = Transcription.objects.create(recording=recording, **validated_data)
        return transcription
