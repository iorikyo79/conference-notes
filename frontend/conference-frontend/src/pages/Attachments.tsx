// Attachments 페이지 - EXIF 기반 세션 자동 분류
import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useApp } from '../contexts/AppContext';
import { apiClient } from '../services/api';
import type { Attachment, BatchUploadResponse, Session, CaptionStatus } from '../types/api';

const CONFIDENCE_LABELS: Record<string, { text: string; className: string }> = {
  exact: { text: '정확', className: 'confidence-exact' },
  tolerance: { text: '유사', className: 'confidence-tolerance' },
  manual: { text: '수동', className: 'confidence-manual' },
  none: { text: '미분류', className: 'confidence-none' },
};

const CAPTION_LABELS: Record<string, { text: string; className: string }> = {
  completed: { text: '완료', className: 'caption-completed' },
  pending: { text: '생성중', className: 'caption-pending' },
  failed: { text: '실패', className: 'caption-failed' },
  none: { text: '미생성', className: 'caption-none' },
};

export const Attachments: React.FC = () => {
  const { activeConference, activeConferenceId } = useApp();
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [batchResults, setBatchResults] = useState<BatchUploadResponse | null>(null);
  const [draggedAttId, setDraggedAttId] = useState<string | null>(null);
  const [dragOverSession, setDragOverSession] = useState<string | null>(null);
  const [captionStatus, setCaptionStatus] = useState<CaptionStatus | null>(null);
  const [captionGenerating, setCaptionGenerating] = useState<string | null>(null);
  const [editingCaption, setEditingCaption] = useState<Attachment | null>(null);
  const [captionDraft, setCaptionDraft] = useState('');
  const [savingCaption, setSavingCaption] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Attachment | null>(null);
  const [deleting, setDeleting] = useState(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!activeConferenceId) return;
    loadAttachments();
    loadCaptionStatus();
  }, [activeConferenceId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const loadAttachments = async () => {
    setLoading(true);
    try {
      const data = await apiClient.getAttachments();
      // 현재 학회 것만 필터링
      const filtered = activeConferenceId
        ? data.filter((a) => a.conference_id === activeConferenceId)
        : data;
      setAttachments(filtered);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const loadCaptionStatus = useCallback(async () => {
    if (!activeConferenceId) return;
    try {
      const status = await apiClient.getCaptionStatus(activeConferenceId);
      setCaptionStatus(status);
    } catch {
      // silently fail
    }
  }, [activeConferenceId]);

  const pollCaptionStatus = useCallback(async () => {
    if (!activeConferenceId) return;
    try {
      const status = await apiClient.getCaptionStatus(activeConferenceId);
      setCaptionStatus(status);
      // Continue polling if there are still pending items
      if (status.pending > 0) {
        pollTimerRef.current = setTimeout(pollCaptionStatus, 3000);
      } else {
        // Polling complete - reload attachments to show updated captions
        await loadAttachments();
        setCaptionGenerating(null);
      }
    } catch {
      // silently fail - stop polling on error
      setCaptionGenerating(null);
    }
  }, [activeConferenceId]);

  const handleGenerateSessionCaptions = async (sessionId: string) => {
    if (!activeConferenceId || captionGenerating) return;
    setCaptionGenerating(sessionId);
    try {
      await apiClient.generateSessionCaptions(sessionId, activeConferenceId);
      // Start polling
      pollCaptionStatus();
    } catch {
      setCaptionGenerating(null);
    }
  };

  // 세션 lookup map
  const sessionMap = useMemo(() => {
    const map = new Map<string, Session>();
    if (activeConference) {
      for (const day of activeConference.days) {
        for (const session of day.sessions) {
          map.set(session.id, session);
        }
      }
    }
    return map;
  }, [activeConference]);

  // 첨부파일을 세션별로 그룹화
  const groupedAttachments = useMemo(() => {
    const groups: Record<string, Attachment[]> = {};
    for (const att of attachments) {
      const key = att.session_id || 'unassigned';
      if (!groups[key]) groups[key] = [];
      groups[key].push(att);
    }
    return groups;
  }, [attachments]);

  // 정렬된 세션 키 (시간순 + 미분류 마지막)
  const sortedSessionKeys = useMemo(() => {
    if (!activeConference) return ['unassigned'];
    const keys: { key: string; sortTime: string }[] = [];
    for (const day of activeConference.days) {
      for (const session of day.sessions) {
        if (groupedAttachments[session.id]) {
          keys.push({ key: session.id, sortTime: `${day.date}${session.start_time || '99'}` });
        }
      }
    }
    keys.sort((a, b) => a.sortTime.localeCompare(b.sortTime));
    const result = keys.map((k) => k.key);
    if (groupedAttachments['unassigned']) {
      result.push('unassigned');
    }
    return result;
  }, [activeConference, groupedAttachments]);

  const handleBatchUpload = async (files: File[]) => {
    if (!activeConferenceId || files.length === 0) return;
    setUploading(true);
    setBatchResults(null);
    try {
      const response = await apiClient.uploadBatch(files, activeConferenceId);
      setBatchResults(response);
      await loadAttachments();
    } catch {
      // error
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    handleBatchUpload(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    handleBatchUpload(Array.from(files));
    // reset input to allow re-selecting same files
    e.target.value = '';
  };

  const handleReassign = async (attachmentId: string, targetSessionKey: string) => {
    const sessionId = targetSessionKey === 'unassigned' ? null : targetSessionKey;
    try {
      await apiClient.reassignAttachmentSession(attachmentId, sessionId);
      await loadAttachments();
    } catch {
      // error
    }
  };

  const openCaptionEditor = (att: Attachment) => {
    setEditingCaption(att);
    setCaptionDraft(att.ai_caption || '');
  };

  const handleSaveCaption = async () => {
    if (!editingCaption) return;
    setSavingCaption(true);
    try {
      await apiClient.updateCaption(editingCaption.id, captionDraft);
      setEditingCaption(null);
      await loadAttachments();
    } catch {
      // error
    } finally {
      setSavingCaption(false);
    }
  };

  const handleDeleteAttachment = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient.deleteAttachment(deleteTarget.id);
      setDeleteTarget(null);
      await loadAttachments();
    } catch {
      // error
    } finally {
      setDeleting(false);
    }
  };

  const formatExifTime = (isoStr?: string) => {
    if (!isoStr) return null;
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('ko-KR', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return null;
    }
  };

  return (
    <div className="attachments-page">
      <h2>발표 자료</h2>

      {/* 업로드 존 */}
      <div
        className={`upload-zone ${dragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && document.getElementById('file-input-batch')?.click()}
      >
        {uploading ? (
          <>
            <p>분류 중...</p>
            <p className="hint">EXIF 시간을 읽어 세션에 자동 매칭</p>
          </>
        ) : (
          <>
            <p>이미지를 끌어다 놓거나 클릭하여 업로드</p>
            <p className="hint">촬영 시간(EXIF) 기준으로 발표 세션 자동 분류</p>
          </>
        )}
        <input
          id="file-input-batch"
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileSelect}
          accept=".png,.jpg,.jpeg,.gif,.bmp,.tiff,.pdf"
        />
      </div>

      {/* 분류 결과 패널 */}
      {batchResults && (
        <div className="batch-results">
          <div className="batch-results-header">
            <h3>분류 결과</h3>
            <button className="btn-close-results" onClick={() => setBatchResults(null)}>✕</button>
          </div>
          <div className="summary-stats">
            <span className="stat">총 {batchResults.summary.total}개</span>
            <span className="stat matched">매칭 {batchResults.summary.matched}개</span>
            <span className="stat unmatched">미분류 {batchResults.summary.unmatched}개</span>
            {batchResults.summary.rejected > 0 && (
              <span className="stat rejected">거부 {batchResults.summary.rejected}개</span>
            )}
          </div>
          <div className="batch-results-list">
            {batchResults.results.map((r, i) => (
              <div key={i} className="batch-result-item">
                <span className="filename">{r.filename}</span>
                {r.status === 'uploaded' ? (
                  <>
                    {r.session_title && (
                      <span className="matched-session">→ {r.session_title}</span>
                    )}
                    {r.exif_datetime && (
                      <span className="exif-time">{formatExifTime(r.exif_datetime)}</span>
                    )}
                    <span className={`confidence-badge ${CONFIDENCE_LABELS[r.confidence]?.className || ''}`}>
                      {CONFIDENCE_LABELS[r.confidence]?.text || r.confidence}
                    </span>
                  </>
                ) : (
                  <span className="rejected-reason">{r.reason}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 캡션 진행 상태 바 */}
      {captionStatus && captionStatus.total > 0 && (
        <div className="caption-status-bar">
          <span className="caption-status-label">
            캡션: {captionStatus.completed}/{captionStatus.total} 완료
          </span>
          <div className="caption-progress">
            <div
              className="caption-progress-fill"
              style={{
                width: `${captionStatus.total > 0 ? (captionStatus.completed / captionStatus.total) * 100 : 0}%`,
              }}
            />
          </div>
          {captionStatus.pending > 0 && (
            <span className="caption-progress-pending">생성중 {captionStatus.pending}개...</span>
          )}
          {captionStatus.failed > 0 && (
            <span className="caption-progress-failed">실패 {captionStatus.failed}개</span>
          )}
        </div>
      )}

      {/* 세션별 그룹 리스트 */}
      {loading ? (
        <div className="loading">불러오는 중...</div>
      ) : attachments.length === 0 ? (
        <p style={{ color: '#999', textAlign: 'center', padding: '2rem' }}>
          업로드된 파일이 없습니다.
        </p>
      ) : (
        <div className="session-grouped-list">
          {sortedSessionKeys.map((sessionKey) => {
            const session = sessionKey !== 'unassigned' ? sessionMap.get(sessionKey) : null;
            const atts = groupedAttachments[sessionKey] || [];
            return (
              <div
                key={sessionKey}
                className={`session-group ${dragOverSession === sessionKey ? 'drag-over' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDragOverSession(sessionKey); }}
                onDragLeave={() => setDragOverSession(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOverSession(null);
                  if (draggedAttId) {
                    handleReassign(draggedAttId, sessionKey);
                    setDraggedAttId(null);
                  }
                }}
              >
                <div className="session-group-header">
                  <span className="session-group-title">
                    {session ? session.title : '미분류'}
                  </span>
                  {session?.speaker && <span className="session-group-speaker"> | {session.speaker}</span>}
                  {session?.start_time && (
                    <span className="session-group-time"> {session.start_time}{session.end_time ? `~${session.end_time}` : ''}</span>
                  )}
                  <span className="session-group-count">{atts.length}개</span>
                  {sessionKey !== 'unassigned' && (
                    <button
                      className="btn-caption-generate"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleGenerateSessionCaptions(sessionKey);
                      }}
                      disabled={!!captionGenerating}
                    >
                      {captionGenerating === sessionKey ? '캡션 생성중...' : '캡션 생성'}
                    </button>
                  )}
                </div>
                <div className="session-group-items">
                  {atts.map((att) => {
                    const captionKey = att.caption_status || 'none';
                    const captionLabel = CAPTION_LABELS[captionKey] || CAPTION_LABELS.none;
                    return (
                    <div
                      key={att.id}
                      className={`attachment-card ${draggedAttId === att.id ? 'dragging' : ''}`}
                      draggable
                      onDragStart={() => setDraggedAttId(att.id)}
                      onDragEnd={() => setDraggedAttId(null)}
                    >
                      <div className="att-card-info">
                        <span className="att-filename">{att.filename}</span>
                        {att.ai_caption && (
                          <div className="caption-preview">
                            {att.ai_caption.length > 50
                              ? `${att.ai_caption.substring(0, 50)}...`
                              : att.ai_caption}
                          </div>
                        )}
                      </div>
                      <div className="att-meta">
                        <span className="att-size">{(att.file_size / 1024).toFixed(0)}KB</span>
                        {att.exif_datetime && (
                          <span className="att-exif">{formatExifTime(att.exif_datetime)}</span>
                        )}
                        <span className={`confidence-badge ${CONFIDENCE_LABELS[att.match_confidence || 'none']?.className || ''}`}>
                          {CONFIDENCE_LABELS[att.match_confidence || 'none']?.text || ''}
                        </span>
                        <span className={`status-badge ${att.extraction_status}`}>
                          {att.extraction_status === 'completed' ? '추출완료' :
                           att.extraction_status === 'processing' ? '처리중' :
                           att.extraction_status === 'pending' ? '대기' : '실패'}
                        </span>
                        <span className={`caption-badge ${captionLabel.className}`}>
                          {captionLabel.text}
                        </span>
                        <button
                          className="btn-edit-caption"
                          onClick={(e) => {
                            e.stopPropagation();
                            openCaptionEditor(att);
                          }}
                          title="캡션 편집"
                        >
                          ✏️
                        </button>
                        <button
                          className="btn-delete-attachment"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(att);
                          }}
                          title="삭제"
                        >
                          🗑
                        </button>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 캡션 편집 모달 */}
      {editingCaption && (
        <div className="modal-overlay" onClick={() => !savingCaption && setEditingCaption(null)}>
          <div className="caption-editor-modal" onClick={(e) => e.stopPropagation()}>
            <div className="caption-editor-header">
              <h3>캡션 편집</h3>
              <button
                className="btn-close-results"
                onClick={() => setEditingCaption(null)}
                disabled={savingCaption}
              >
                ✕
              </button>
            </div>
            <div className="caption-editor-body">
              {editingCaption.file_type === 'image' && (
                <div className="caption-editor-image">
                  <img
                    src={apiClient.getAttachmentFileUrl(editingCaption.id)}
                    alt={editingCaption.filename}
                  />
                </div>
              )}
              <div className="caption-editor-info">
                <span className="caption-editor-filename">{editingCaption.filename}</span>
                {editingCaption.exif_datetime && (
                  <span className="caption-editor-exif">
                    촬영: {formatExifTime(editingCaption.exif_datetime)}
                  </span>
                )}
              </div>
              <textarea
                className="caption-editor-textarea"
                value={captionDraft}
                onChange={(e) => setCaptionDraft(e.target.value)}
                placeholder="슬라이드 캡션을 입력하세요..."
                rows={4}
                autoFocus
                disabled={savingCaption}
              />
            </div>
            <div className="caption-editor-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setEditingCaption(null)}
                disabled={savingCaption}
              >
                취소
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveCaption}
                disabled={savingCaption}
              >
                {savingCaption ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 첨부파일 삭제 확인 모달 */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => !deleting && setDeleteTarget(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>첨부파일 삭제</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
              다음 파일을 삭제하시겠습니까?
              <br />
              <strong style={{ color: '#1a1a2e' }}>{deleteTarget.filename}</strong>
              {deleteTarget.exif_datetime && (
                <span style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                  촬영: {formatExifTime(deleteTarget.exif_datetime)}
                </span>
              )}
            </p>
            <p style={{ fontSize: '0.8rem', color: '#e74c3c', marginBottom: '1rem' }}>
              ⚠ 파일과 캡션이 영구적으로 삭제됩니다.
            </p>
            <div className="modal-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
              >
                취소
              </button>
              <button
                className="btn btn-danger"
                onClick={handleDeleteAttachment}
                disabled={deleting}
              >
                {deleting ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
