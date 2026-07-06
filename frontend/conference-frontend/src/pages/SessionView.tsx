// SessionView 페이지 - 메인 메모 작성 화면
import React, { useState, useEffect, useRef } from 'react';
import { useApp } from '../contexts/AppContext';
import { useNote } from '../contexts/NoteContext';
import { NoteEditor } from '../components/NoteEditor';
import { SessionSelector } from '../components/SessionSelector';

export const SessionView: React.FC = () => {
  const { activeConference, activeSessionId, setActiveSessionId, refreshConference } = useApp();
  const { loadNotes, createNote, deleteEmptyNotes, notes } = useNote();
  const [showAddSession, setShowAddSession] = useState(false);
  const [cleaningUp, setCleaningUp] = useState(false);

  // 중복 노트 생성 방지: 세션별 로드 완료 및 생성 중 추적
  const loadedRef = useRef<Set<string>>(new Set());
  const creatingRef = useRef<Set<string>>(new Set());

  // 세션이 선택되면 노트 로드
  useEffect(() => {
    if (!activeSessionId) return;
    loadedRef.current.add(activeSessionId);
    loadNotes(activeSessionId);
  }, [activeSessionId, loadNotes]);

  // 노트가 없는 세션에 자동으로 노트 생성 (한 번만)
  useEffect(() => {
    if (
      activeSessionId &&
      activeConference &&
      notes.length === 0 &&
      loadedRef.current.has(activeSessionId) &&
      !creatingRef.current.has(activeSessionId)
    ) {
      creatingRef.current.add(activeSessionId);
      createNote(activeSessionId, activeConference.id).catch(() => {
        creatingRef.current.delete(activeSessionId);
      });
    }
  }, [activeSessionId, activeConference, notes.length, createNote]);

  // 첫 번째 세션 자동 선택
  useEffect(() => {
    if (!activeSessionId && activeConference) {
      for (const day of activeConference.days) {
        if (day.sessions.length > 0) {
          setActiveSessionId(day.sessions[0].id);
          break;
        }
      }
    }
  }, [activeConference, activeSessionId, setActiveSessionId]);

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
  };

  const handleNewNote = async () => {
    if (!activeSessionId || !activeConference) return;
    try {
      await createNote(activeSessionId, activeConference.id);
    } catch {
      // error handled in context
    }
  };

  const activeSession = React.useMemo(() => {
    if (!activeConference || !activeSessionId) return null;
    for (const day of activeConference.days) {
      const session = day.sessions.find((s) => s.id === activeSessionId);
      if (session) return session;
    }
    return null;
  }, [activeConference, activeSessionId]);

  const handleSessionDeleted = async () => {
    // 삭제 후 데이터 새로고침
    await refreshConference();
    // 활성 세션이 삭제되었을 수 있으므로 리셋
    setActiveSessionId(null);
  };

  const handleCleanupEmptyNotes = async () => {
    if (!activeConference) return;
    setCleaningUp(true);
    try {
      const count = await deleteEmptyNotes(activeConference.id);
      if (count > 0 && activeSessionId) {
        await loadNotes(activeSessionId);
      }
    } catch {
      // error handled in context
    } finally {
      setCleaningUp(false);
    }
  };

  return (
    <div className="session-view">
      <div className="session-sidebar">
        <div className="sidebar-header">
          <h3>세션 목록</h3>
          {activeConference && (
            <button
              className="btn-cleanup"
              onClick={handleCleanupEmptyNotes}
              disabled={cleaningUp}
              title="내용이 없는 빈 노트를 모두 삭제"
            >
              {cleaningUp ? '...' : '빈 노트 정리'}
            </button>
          )}
        </div>
        {activeConference ? (
          <SessionSelector
            conference={activeConference}
            activeSessionId={activeSessionId}
            onSelectSession={handleSelectSession}
            onAddSession={() => setShowAddSession(true)}
            onSessionDeleted={handleSessionDeleted}
          />
        ) : (
          <p className="loading">학회를 선택해주세요.</p>
        )}
      </div>
      <div className="editor-area">
        {activeSession ? (
          <>
            <div className="editor-header">
              <div>
                <span className="session-title">{activeSession.title}</span>
                {activeSession.speaker && (
                  <span className="session-meta"> | {activeSession.speaker}</span>
                )}
                {activeSession.start_time && (
                  <span className="session-meta">
                    {' '}| {activeSession.start_time}
                    {activeSession.end_time ? `~${activeSession.end_time}` : ''}
                  </span>
                )}
              </div>
              <button className="btn btn-secondary" onClick={handleNewNote}>
                + 새 노트
              </button>
            </div>
            <NoteEditor />
          </>
        ) : (
          <div className="no-session">
            좌측에서 세션을 선택하거나, 새 세션을 추가하세요.
          </div>
        )}
      </div>
    </div>
  );
};
