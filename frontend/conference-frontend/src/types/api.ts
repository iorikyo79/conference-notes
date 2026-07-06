// API 타입 정의

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

export interface Session {
  id: string;
  day_date: string;
  title: string;
  speaker?: string;
  start_time?: string;
  end_time?: string;
  room?: string;
  category?: string;
}

export interface ConferenceDay {
  date: string;
  label: string;
  sessions: Session[];
}

export interface Conference {
  id: string;
  name: string;
  location?: string;
  start_date: string;
  end_date: string;
  days: ConferenceDay[];
  created_at: string;
}

export interface Note {
  id: string;
  session_id: string;
  conference_id: string;
  content: string;
  tags: string[];
  created_at: string;
  updated_at?: string;
  is_starred: boolean;
}

export interface NoteCreate {
  session_id: string;
  conference_id: string;
  content?: string;
}

export interface NoteUpdate {
  content?: string;
  tags?: string[];
  is_starred?: boolean;
}

export interface Attachment {
  id: string;
  session_id?: string;
  conference_id?: string;
  filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  extracted_text?: string;
  extraction_status: 'pending' | 'processing' | 'completed' | 'failed';
  exif_datetime?: string;
  match_confidence?: string; // "exact" | "tolerance" | "manual" | "none"
  uploaded_at: string;
  ai_caption?: string;
  caption_status?: string; // "none" | "pending" | "completed" | "failed"
}

export interface BatchUploadResult {
  filename: string;
  attachment_id?: string;
  status: 'uploaded' | 'rejected';
  session_id?: string;
  session_title?: string;
  exif_datetime?: string;
  confidence: 'exact' | 'tolerance' | 'manual' | 'none';
  reason: string;
}

export interface BatchUploadResponse {
  results: BatchUploadResult[];
  summary: {
    total: number;
    uploaded: number;
    rejected: number;
    matched: number;
    unmatched: number;
  };
}

export interface SessionSummary {
  session_id: string;
  session_title: string;
  summary: string;
  keywords: string[];
}

export interface ReportResponse {
  conference_id: string;
  conference_name: string;
  report_type: string;
  summary: string;
  keywords: string[];
  session_summaries: SessionSummary[];
  generated_at: string;
  html_content?: string;
}

export interface CaptionStatus {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  none: number;
}

export interface ReportRequest {
  conference_id: string;
  session_ids?: string[];
  report_type?: string;
}

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export type PageName = 'home' | 'session' | 'attachments' | 'report';
