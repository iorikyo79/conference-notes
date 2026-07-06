// SessionSelector - 날짜별 세션 목록 표시
import React, { useState } from 'react';
import type { Conference, Session } from '../types/api';
import { apiClient } from '../services/api';

interface SessionSelectorProps {
  conference: Conference;
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onAddSession: () => void;
  onSessionDeleted?: () => void;
}

export const SessionSelector: React.FC<SessionSelectorProps> = ({
  conference,
  activeSessionId,
  onSelectSession,
  onSessionDeleted,
}) => {
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedDay, setSelectedDay] = useState<string>('');
  const [newSession, setNewSession] = useState({
    title: '',
    speaker: '',
    start_time: '',
    end_time: '',
  });
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleAddSession = async () => {
    if (!selectedDay || !newSession.title) return;
    try {
      await apiClient.addSession(conference.id, selectedDay, {
        title: newSession.title,
        speaker: newSession.speaker || undefined,
        start_time: newSession.start_time || undefined,
        end_time: newSession.end_time || undefined,
      });
      setNewSession({ title: '', speaker: '', start_time: '', end_time: '' });
      setShowAddForm(false);
      // 페이지 새로고침을 위해 부모에서 reload 필요
      window.location.reload();
    } catch {
      // error
    }
  };

  const handleDeleteSession = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await apiClient.deleteSession(conference.id, deleteTarget.id);
      setDeleteTarget(null);
      if (onSessionDeleted) {
        onSessionDeleted();
      } else {
        window.location.reload();
      }
    } catch {
      // error
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="day-tabs">
      {conference.days.map((day) => (
        <div key={day.date} className="day-section">
          <h4>{day.label}</h4>
          {day.sessions.length === 0 ? (
            <p style={{ fontSize: '0.8rem', color: '#999', padding: '0.5rem 0' }}>
              세션이 없습니다.
            </p>
          ) : (
            day.sessions.map((session: Session) => (
              <div
                key={session.id}
                className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="session-item-content">
                  <span className="session-title">{session.title}</span>
                  {session.start_time && (
                    <span className="session-time">
                      {session.start_time}
                      {session.end_time ? ` ~ ${session.end_time}` : ''}
                    </span>
                  )}
                  {session.speaker && (
                    <span className="session-speaker"> | {session.speaker}</span>
                  )}
                </div>
                <button
                  className="session-delete-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(session);
                  }}
                  title="세션 삭제"
                >
                  ✕
                </button>
              </div>
            ))
          )}
          <button
            className="add-session-btn"
            onClick={() => {
              setSelectedDay(day.date);
              setShowAddForm(true);
            }}
          >
            + 세션 추가
          </button>
        </div>
      ))}

      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>새 세션 추가</h3>
            <div className="form-group">
              <label>세션명 *</label>
              <input
                type="text"
                value={newSession.title}
                onChange={(e) => setNewSession({ ...newSession, title: e.target.value })}
                placeholder="예: 개회식 및 기조연설"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>연자</label>
              <input
                type="text"
                value={newSession.speaker}
                onChange={(e) => setNewSession({ ...newSession, speaker: e.target.value })}
                placeholder="예: 홍길동 교수"
              />
            </div>
            <div className="form-group">
              <label>시간</label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  value={newSession.start_time}
                  onChange={(e) => setNewSession({ ...newSession, start_time: e.target.value })}
                  placeholder="09:00"
                  style={{ width: '80px' }}
                />
                <span style={{ lineHeight: '2rem' }}>~</span>
                <input
                  type="text"
                  value={newSession.end_time}
                  onChange={(e) => setNewSession({ ...newSession, end_time: e.target.value })}
                  placeholder="10:00"
                  style={{ width: '80px' }}
                />
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowAddForm(false)}>
                취소
              </button>
              <button className="btn btn-primary" onClick={handleAddSession}>
                추가
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <div className="modal-overlay" onClick={() => !deleting && setDeleteTarget(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>세션 삭제</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
              다음 세션을 삭제하시겠습니까?
              <br />
              <strong style={{ color: '#1a1a2e' }}>{deleteTarget.title}</strong>
              {deleteTarget.speaker && ` | ${deleteTarget.speaker}`}
              {deleteTarget.start_time && (
                <span style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.8rem' }}>
                  {deleteTarget.start_time}
                  {deleteTarget.end_time ? ` ~ ${deleteTarget.end_time}` : ''}
                </span>
              )}
            </p>
            <p style={{ fontSize: '0.8rem', color: '#e74c3c', marginBottom: '1rem' }}>
              ⚠ 이 세션에 작성된 노트도 함께 삭제됩니다.
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
                onClick={handleDeleteSession}
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
