export type ThreatLevel = 'Low' | 'Medium' | 'High';

export interface BoundingBox {
  label: string;
  confidence: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ThreatEvent {
  _id: string;
  video_url: string;
  thumbnail_url?: string;
  timestamp: string;
  summary: string;
  threat_level: ThreatLevel;
  anomaly_score: number;
  detected_objects: BoundingBox[];
  escalation_steps: string;
  clip_path?: string;
  source_id?: string;
  audio_transcription?: string;
  owner_email?: string;
}

export interface UserProfile {
  _id: string;
  email: string;
  name: string;
  camera_name: string;
}

export interface StreamMessage {
  type: 'frame' | 'event';
  frame?: string;
  timestamp?: number;
  threat_level?: ThreatLevel;
  anomaly_score?: number;
  detections?: BoundingBox[];
  event_id?: string;
  summary?: string;
  video_url?: string;
  audio_transcription?: string;
  audio_level?: number;
}
