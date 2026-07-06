// API 클라이언트 서비스
import type {
  Conference,
  Note,
  NoteCreate,
  NoteUpdate,
  Attachment,
  BatchUploadResponse,
  ReportResponse,
  ReportRequest,
  HealthResponse,
  Session,
  CaptionStatus,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class APIClient {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: response.statusText,
        }));

        if (typeof error.detail === 'object') {
          throw new Error(JSON.stringify(error.detail));
        } else {
          throw new Error(error.detail || 'API 요청 실패');
        }
      }

      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('알 수 없는 오류가 발생했습니다.');
    }
  }

  private async requestFormData<T>(
    endpoint: string,
    formData: FormData
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({
          detail: response.statusText,
        }));

        if (typeof error.detail === 'object') {
          throw new Error(JSON.stringify(error.detail));
        } else {
          throw new Error(error.detail || 'API 요청 실패');
        }
      }

      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('알 수 없는 오류가 발생했습니다.');
    }
  }

  // Health
  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/health');
  }

  // Conferences
  async getConferences(): Promise<Conference[]> {
    const data = await this.request<{ conferences: Conference[]; count: number }>(
      '/api/conferences/'
    );
    return data.conferences;
  }

  async getConference(id: string): Promise<Conference> {
    return this.request<Conference>(`/api/conferences/${id}`);
  }

  async createConference(data: {
    id: string;
    name: string;
    location?: string;
    start_date: string;
    end_date: string;
  }): Promise<Conference> {
    return this.request<Conference>('/api/conferences/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async addSession(
    conferenceId: string,
    dayDate: string,
    session: Omit<Session, 'id' | 'day_date'>
  ): Promise<Session> {
    return this.request<Session>(
      `/api/conferences/${conferenceId}/days/${dayDate}/sessions`,
      {
        method: 'POST',
        body: JSON.stringify(session),
      }
    );
  }

  async deleteSession(
    conferenceId: string,
    sessionId: string
  ): Promise<{ message: string; session_title: string; deleted: boolean }> {
    return this.request<{ message: string; session_title: string; deleted: boolean }>(
      `/api/conferences/${conferenceId}/sessions/${sessionId}`,
      {
        method: 'DELETE',
      }
    );
  }

  // Notes
  async getNotes(sessionId: string): Promise<Note[]> {
    const data = await this.request<{ notes: Note[]; count: number }>(
      `/api/notes/?session_id=${sessionId}`
    );
    return data.notes;
  }

  async getNotesByConference(conferenceId: string): Promise<Note[]> {
    // note: uses the session_id query param approach; for conference-wide we get all
    // and filter client-side, or use a dedicated endpoint later
    const data = await this.request<{ notes: Note[]; count: number }>(
      `/api/notes/`
    );
    return data.notes.filter((n) => n.conference_id === conferenceId);
  }

  async createNote(request: NoteCreate): Promise<Note> {
    return this.request<Note>('/api/notes/', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async updateNote(id: string, request: NoteUpdate): Promise<Note> {
    return this.request<Note>(`/api/notes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(request),
    });
  }

  async deleteNote(id: string): Promise<void> {
    await this.request<{ message: string }>(`/api/notes/${id}`, {
      method: 'DELETE',
    });
  }

  async deleteEmptyNotes(conferenceId?: string, sessionId?: string): Promise<{ deleted_count: number }> {
    const params = new URLSearchParams();
    if (conferenceId) params.append('conference_id', conferenceId);
    if (sessionId) params.append('session_id', sessionId);
    const query = params.toString() ? `?${params.toString()}` : '';
    return this.request<{ deleted_count: number; deleted_ids: string[] }>(
      `/api/notes/empty/bulk${query}`,
      { method: 'DELETE' }
    );
  }

  // Organize script via LLM
  async organizeScript(
    noteId: string,
    rawText: string
  ): Promise<{ organized_content: string; keywords: string[]; model_used: boolean }> {
    return this.request<{ organized_content: string; keywords: string[]; model_used: boolean }>(
      `/api/notes/${noteId}/organize`,
      {
        method: 'POST',
        body: JSON.stringify({ raw_text: rawText }),
      }
    );
  }

  // Attachments
  async getAttachments(sessionId?: string): Promise<Attachment[]> {
    const params = sessionId ? `?session_id=${sessionId}` : '';
    const data = await this.request<{ attachments: Attachment[]; count: number }>(
      `/api/attachments/${params}`
    );
    return data.attachments;
  }

  async getAttachmentText(id: string): Promise<{ extracted_text: string; extraction_status: string }> {
    return this.request<{ attachment_id: string; extracted_text: string; extraction_status: string }>(
      `/api/attachments/${id}/text`
    );
  }

  async uploadAttachment(file: File, sessionId?: string, conferenceId?: string): Promise<Attachment> {
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('session_id', sessionId);
    if (conferenceId) formData.append('conference_id', conferenceId);
    return this.requestFormData<Attachment>('/api/attachments/upload', formData);
  }

  async uploadBatch(files: File[], conferenceId: string): Promise<BatchUploadResponse> {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    formData.append('conference_id', conferenceId);
    return this.requestFormData<BatchUploadResponse>('/api/attachments/upload-batch', formData);
  }

  async reassignAttachmentSession(
    attachmentId: string,
    sessionId: string | null
  ): Promise<Attachment> {
    return this.request<Attachment>(
      `/api/attachments/${attachmentId}/session`,
      {
        method: 'PATCH',
        body: JSON.stringify({ session_id: sessionId ?? 'null' }),
      }
    );
  }

  async updateCaption(attachmentId: string, caption: string): Promise<Attachment> {
    return this.request<Attachment>(
      `/api/attachments/${attachmentId}/caption`,
      {
        method: 'PATCH',
        body: JSON.stringify({ caption }),
      }
    );
  }

  async generateCaption(attachmentId: string): Promise<{ message: string }> {
    return this.request<{ message: string }>(`/api/attachments/${attachmentId}/caption`, {
      method: 'POST',
    });
  }

  async generateSessionCaptions(
    sessionId: string,
    conferenceId?: string
  ): Promise<{ message: string; total: number }> {
    const formData = new FormData();
    if (conferenceId) formData.append('conference_id', conferenceId);
    return this.requestFormData<{ message: string; total: number }>(
      `/api/attachments/sessions/${sessionId}/captions`,
      formData
    );
  }

  async getCaptionStatus(conferenceId: string): Promise<CaptionStatus> {
    return this.request<CaptionStatus>(
      `/api/attachments/caption-status?conference_id=${conferenceId}`
    );
  }

  async deleteAttachment(id: string): Promise<void> {
    await this.request<{ message: string }>(`/api/attachments/${id}`, {
      method: 'DELETE',
    });
  }

  // Reports
  async generateReport(request: ReportRequest): Promise<ReportResponse> {
    return this.request<ReportResponse>('/api/reports/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getReport(conferenceId: string): Promise<ReportResponse> {
    return this.request<ReportResponse>(`/api/reports/${conferenceId}`);
  }

  getAttachmentFileUrl(attachmentId: string): string {
    return `${this.baseURL}/api/attachments/${attachmentId}/file`;
  }

  async exportReportHtml(conferenceId: string): Promise<Blob> {
    const url = `${this.baseURL}/api/reports/${conferenceId}/export?format=html`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('HTML 리포트 내보내기 실패');
    }
    return await response.blob();
  }
}

export const apiClient = new APIClient();
