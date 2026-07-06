// 노트 상태 관리 및 자동 저장
import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import type { Note, SaveStatus } from '../types/api';
import { apiClient } from '../services/api';

interface NoteContextValue {
  // 현재 세션의 노트 목록
  notes: Note[];
  currentNote: Note | null;
  setCurrentNote: (note: Note | null) => void;

  // 저장 상태
  saveStatus: SaveStatus;

  // 노트 로드
  loadNotes: (sessionId: string) => Promise<void>;

  // 노트 생성
  createNote: (sessionId: string, conferenceId: string) => Promise<Note>;

  // 노트 내용 업데이트 (자동 저장)
  updateNoteContent: (id: string, content: string) => void;

  // 노트 삭제
  deleteNote: (id: string) => Promise<void>;

  // 빈 노트 일괄 삭제
  deleteEmptyNotes: (conferenceId?: string) => Promise<number>;

  // 에러
  error: string | null;
}

const NoteContext = createContext<NoteContextValue | null>(null);

const AUTOSAVE_DEBOUNCE_MS = 2000;

export const NoteProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [currentNote, setCurrentNote] = useState<Note | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  // debounce를 위한 timer ref
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 최신 content를 저장할 ref (클로저 문제 방지)
  const pendingContentRef = useRef<Map<string, string>>(new Map());

  const loadNotes = useCallback(async (sessionId: string) => {
    setError(null);
    try {
      const data = await apiClient.getNotes(sessionId);
      setNotes(data);
      // 세션 변경 시 항상 첫 번째 노트를 현재 노트로 설정
      setCurrentNote(data.length > 0 ? data[0] : null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '노트 로드 실패');
    }
  }, []);

  const createNote = useCallback(async (sessionId: string, conferenceId: string): Promise<Note> => {
    setError(null);
    try {
      const newNote = await apiClient.createNote({
        session_id: sessionId,
        conference_id: conferenceId,
        content: '',
      });
      setNotes((prev) => [newNote, ...prev]);
      setCurrentNote(newNote);
      return newNote;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '노트 생성 실패';
      setError(msg);
      throw new Error(msg);
    }
  }, []);

  const flushSave = useCallback(async (noteId: string) => {
    const content = pendingContentRef.current.get(noteId);
    if (content === undefined) return;

    setSaveStatus('saving');
    try {
      const updated = await apiClient.updateNote(noteId, { content });
      setNotes((prev) =>
        prev.map((n) => (n.id === noteId ? updated : n))
      );
      setCurrentNote((prev) => (prev && prev.id === noteId ? updated : prev));
      setSaveStatus('saved');
      pendingContentRef.current.delete(noteId);

      // 2초 후 idle로 변경
      setTimeout(() => {
        setSaveStatus((prev) => (prev === 'saved' ? 'idle' : prev));
      }, 2000);
    } catch (err) {
      setSaveStatus('error');
      setError(err instanceof Error ? err.message : '노트 저장 실패');
    }
  }, []);

  const updateNoteContent = useCallback(
    (noteId: string, content: string) => {
      // 현재 노트의 content를 즉시 업데이트 (UI 반응성)
      setCurrentNote((prev) =>
        prev && prev.id === noteId ? { ...prev, content } : prev
      );

      // 저장 대기열에 추가
      pendingContentRef.current.set(noteId, content);

      // 기존 타이머 클리어
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      // 새 타이머 설정
      setSaveStatus('idle');
      debounceTimerRef.current = setTimeout(() => {
        flushSave(noteId);
      }, AUTOSAVE_DEBOUNCE_MS);
    },
    [flushSave]
  );

  const deleteNote = useCallback(async (id: string) => {
    setError(null);
    try {
      await apiClient.deleteNote(id);
      setNotes((prev) => prev.filter((n) => n.id !== id));
      setCurrentNote((prev) => (prev && prev.id === id ? null : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : '노트 삭제 실패');
    }
  }, []);

  const deleteEmptyNotes = useCallback(async (conferenceId?: string): Promise<number> => {
    setError(null);
    try {
      const result = await apiClient.deleteEmptyNotes(conferenceId);
      // 현재 로드된 노트 중 삭제된 것들 제거
      if (result.deleted_count > 0) {
        setNotes((prev) => prev.filter((n) => n.content && n.content.trim()));
      }
      return result.deleted_count;
    } catch (err) {
      setError(err instanceof Error ? err.message : '빈 노트 삭제 실패');
      return 0;
    }
  }, []);

  const value: NoteContextValue = {
    notes,
    currentNote,
    setCurrentNote,
    saveStatus,
    loadNotes,
    createNote,
    updateNoteContent,
    deleteNote,
    deleteEmptyNotes,
    error,
  };

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
};

export const useNote = (): NoteContextValue => {
  const context = useContext(NoteContext);
  if (!context) {
    throw new Error('useNote must be used within NoteProvider');
  }
  return context;
};
