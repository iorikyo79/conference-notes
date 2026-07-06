// NoteEditor - 마크다운 에디터 + 미리보기 + 스크립트 정리 + 이미지 업로드
import React, { useState, useEffect } from 'react';
import { useNote } from '../contexts/NoteContext';
import { useApp } from '../contexts/AppContext';
import { apiClient } from '../services/api';
import type { Attachment } from '../types/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export const NoteEditor: React.FC = () => {
  const { currentNote, updateNoteContent, saveStatus, notes, setCurrentNote } = useNote();
  const { activeConferenceId } = useApp();

  const [showScriptModal, setShowScriptModal] = useState(false);
  const [scriptInput, setScriptInput] = useState('');
  const [organizing, setOrganizing] = useState(false);
  const [organizedResult, setOrganizedResult] = useState<string | null>(null);
  const [organizeError, setOrganizeError] = useState<string | null>(null);

  // 이미지 업로드 상태
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showAttachments, setShowAttachments] = useState(false);

  // 노트가 변경되면 첨부파일 로드
  useEffect(() => {
    if (currentNote) {
      loadAttachments();
    } else {
      setAttachments([]);
    }
  }, [currentNote?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadAttachments = async () => {
    if (!currentNote?.session_id) return;
    try {
      const all = await apiClient.getAttachments(currentNote.session_id);
      setAttachments(all);
    } catch {
      setAttachments([]);
    }
  };

  const handleImageUpload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !currentNote) return;
    setUploading(true);
    setUploadError(null);
    try {
      for (const file of Array.from(files)) {
        await apiClient.uploadAttachment(
          file,
          currentNote.session_id,
          activeConferenceId || undefined
        );
      }
      await loadAttachments();
      setShowAttachments(true);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '업로드 실패');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteAttachment = async (id: string) => {
    try {
      await apiClient.deleteAttachment(id);
      setAttachments((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // ignore
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (!currentNote) return;
    updateNoteContent(currentNote.id, e.target.value);
  };

  const insertMarkdown = (prefix: string, suffix: string = '') => {
    if (!currentNote) return;
    const textarea = document.getElementById('note-textarea') as HTMLTextAreaElement;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = currentNote.content.substring(start, end);
    const newContent =
      currentNote.content.substring(0, start) +
      prefix + selected + suffix +
      currentNote.content.substring(end);
    updateNoteContent(currentNote.id, newContent);
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = start + prefix.length;
      textarea.selectionEnd = end + prefix.length;
    }, 0);
  };

  const handleOrganize = async () => {
    if (!currentNote || !scriptInput.trim()) return;
    setOrganizing(true);
    setOrganizeError(null);
    try {
      const result = await apiClient.organizeScript(currentNote.id, scriptInput);
      setOrganizedResult(result.organized_content);
    } catch (err) {
      setOrganizeError(err instanceof Error ? err.message : '스크립트 정리 실패');
    } finally {
      setOrganizing(false);
    }
  };

  const applyOrganized = () => {
    if (!currentNote || !organizedResult) return;
    updateNoteContent(currentNote.id, organizedResult);
    setShowScriptModal(false);
    setScriptInput('');
    setOrganizedResult(null);
  };

  const appendOrganized = () => {
    if (!currentNote || !organizedResult) return;
    const separator = currentNote.content ? '\n\n---\n\n' : '';
    updateNoteContent(currentNote.id, currentNote.content + separator + organizedResult);
    setShowScriptModal(false);
    setScriptInput('');
    setOrganizedResult(null);
  };

  const closeScriptModal = () => {
    setShowScriptModal(false);
    setScriptInput('');
    setOrganizedResult(null);
    setOrganizeError(null);
  };

  const renderToolbar = () => (
    <div className="editor-toolbar">
      <button onClick={() => insertMarkdown('# ')}>H1</button>
      <button onClick={() => insertMarkdown('## ')}>H2</button>
      <button onClick={() => insertMarkdown('### ')}>H3</button>
      <button onClick={() => insertMarkdown('**', '**')}>B</button>
      <button onClick={() => insertMarkdown('*', '*')}>I</button>
      <button onClick={() => insertMarkdown('- ')}>목록</button>
      <button onClick={() => insertMarkdown('> ')}>인용</button>
      <button onClick={() => insertMarkdown('```\n', '\n```')}>코드</button>
      {currentNote && (
        <>
          <button
            onClick={() => setShowScriptModal(true)}
            style={{
              marginLeft: '0.5rem',
              background: '#e8e8f0',
              color: '#4a4af0',
              fontWeight: 600,
              padding: '0.3rem 0.7rem',
              borderRadius: '4px',
              border: '1px solid #4a4af0',
            }}
          >
            ✨ 스크립트 정리
          </button>
          <label
            style={{
              marginLeft: '0.25rem',
              background: '#e8f5e9',
              color: '#28a745',
              fontWeight: 600,
              padding: '0.3rem 0.7rem',
              borderRadius: '4px',
              border: '1px solid #28a745',
              cursor: 'pointer',
              fontSize: '0.85rem',
            }}
          >
            {uploading ? '⏳ 업로드 중...' : '📎 슬라이드 업로드'}
            <input
              type="file"
              multiple
              accept="image/*,application/pdf"
              style={{ display: 'none' }}
              onChange={(e) => {
                handleImageUpload(e.target.files);
                e.target.value = '';
              }}
              disabled={uploading}
            />
          </label>
          {attachments.length > 0 && (
            <button
              onClick={() => setShowAttachments(!showAttachments)}
              style={{
                marginLeft: '0.25rem',
                background: showAttachments ? '#fff3e0' : 'transparent',
                color: '#e6a700',
                fontWeight: 600,
                padding: '0.3rem 0.7rem',
                borderRadius: '4px',
                border: '1px solid #e6a700',
                cursor: 'pointer',
                fontSize: '0.85rem',
              }}
            >
              📋 자료 ({attachments.length})
            </button>
          )}
        </>
      )}
      <span
        className={`save-indicator ${saveStatus}`}
        style={{ marginLeft: 'auto' }}
      >
        {saveStatus === 'saving' ? '저장 중...' :
         saveStatus === 'saved' ? '저장됨' :
         saveStatus === 'error' ? '오류' : ''}
      </span>
    </div>
  );

  if (!currentNote) {
    return (
      <>
        {renderToolbar()}
        <div className="editor-content">
          <textarea
            id="note-textarea"
            className="editor-textarea"
            placeholder="메모를 작성하세요... (마크다운 지원)"
            value=""
            onChange={() => {}}
          />
          <div className="editor-preview">
            <p style={{ color: '#999' }}>미리보기</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      {renderToolbar()}

      {uploadError && (
        <div style={{ padding: '0.5rem 1rem', background: '#ffebee', color: '#dc3545', fontSize: '0.85rem' }}>
          {uploadError}
        </div>
      )}

      {/* 첨부파일 목록 (토글) */}
      {showAttachments && attachments.length > 0 && (
        <div style={{
          padding: '0.75rem 1rem',
          borderBottom: '1px solid #eee',
          background: '#fafafa',
          maxHeight: '200px',
          overflowY: 'auto',
        }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#666', marginBottom: '0.5rem' }}>
            📋 첨부된 발표 자료
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {attachments.map((att) => (
              <div
                key={att.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.3rem 0.6rem',
                  background: 'white',
                  border: '1px solid #e0e0e0',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                }}
              >
                <span>{att.file_type === 'pdf' ? '📄' : '🖼️'}</span>
                <span
                  style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                  title={att.filename}
                >
                  {att.filename}
                </span>
                <span className={`status-badge ${att.extraction_status}`} style={{ fontSize: '0.7rem' }}>
                  {att.extraction_status === 'completed' ? '✓' :
                   att.extraction_status === 'processing' ? '⏳' :
                   att.extraction_status === 'pending' ? '○' : '✗'}
                </span>
                <button
                  onClick={() => handleDeleteAttachment(att.id)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#dc3545',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    padding: '0',
                    marginLeft: '0.2rem',
                  }}
                  title="삭제"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {notes.length > 1 && (
        <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid #eee', display: 'flex', gap: '0.5rem', overflowX: 'auto' }}>
          {notes.map((n) => (
            <button
              key={n.id}
              onClick={() => setCurrentNote(n)}
              style={{
                padding: '0.3rem 0.6rem',
                border: '1px solid #ddd',
                borderRadius: '6px',
                background: n.id === currentNote.id ? '#4a4af0' : 'white',
                color: n.id === currentNote.id ? 'white' : '#666',
                cursor: 'pointer',
                fontSize: '0.8rem',
                whiteSpace: 'nowrap',
              }}
            >
              {n.content.split('\n')[0].substring(0, 30) || '빈 노트'}
            </button>
          ))}
        </div>
      )}

      <div className="editor-content">
        <textarea
          id="note-textarea"
          className="editor-textarea"
          placeholder="메모를 작성하세요... (마크다운 지원)"
          value={currentNote.content}
          onChange={handleChange}
        />
        <div className="editor-preview">
          {currentNote.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {currentNote.content}
            </ReactMarkdown>
          ) : (
            <p style={{ color: '#999' }}>미리보기가 여기에 표시됩니다.</p>
          )}
        </div>
      </div>

      {/* 스크립트 정리 모달 */}
      {showScriptModal && (
        <div className="modal-overlay" onClick={closeScriptModal}>
          <div
            className="modal"
            style={{ width: '700px', maxWidth: '95%' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>✨ 발표 스크립트 자동 정리</h3>

            {!organizedResult ? (
              <>
                <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '0.75rem' }}>
                  발표 스크립트, 필사본, 또는 긴 메모를 붙여넣으면
                  LLM이 구조화된 마크다운 노트로 정리합니다.
                </p>
                <div className="form-group">
                  <textarea
                    value={scriptInput}
                    onChange={(e) => setScriptInput(e.target.value)}
                    placeholder={
                      "여기에 발표 스크립트를 붙여넣으세요...\n\n" +
                      "예시:\n" +
                      "안녕하세요, 오늘은 Multimodal Large Language Models in Medicine에 대해 말씀드리겠습니다..."
                    }
                    style={{
                      width: '100%',
                      minHeight: '300px',
                      fontFamily: 'monospace',
                      fontSize: '0.85rem',
                      resize: 'vertical',
                    }}
                    autoFocus
                  />
                </div>
                {organizeError && (
                  <div style={{ color: '#dc3545', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    {organizeError}
                  </div>
                )}
                <div className="modal-actions">
                  <button className="btn btn-secondary" onClick={closeScriptModal}>
                    취소
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleOrganize}
                    disabled={!scriptInput.trim() || organizing}
                  >
                    {organizing ? '정리 중...' : '✨ 정리하기'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p style={{ fontSize: '0.85rem', color: '#28a745', marginBottom: '0.75rem' }}>
                  정리가 완료되었습니다. 미리보기를 확인 후 적용하세요.
                </p>
                <div
                  style={{
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    padding: '1rem',
                    maxHeight: '400px',
                    overflowY: 'auto',
                    background: '#fafafa',
                    fontSize: '0.85rem',
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {organizedResult}
                  </ReactMarkdown>
                </div>
                <div className="modal-actions">
                  <button className="btn btn-secondary" onClick={() => setOrganizedResult(null)}>
                    다시 정리
                  </button>
                  <button className="btn btn-secondary" onClick={appendOrganized}>
                    기존 노트 뒤에 추가
                  </button>
                  <button className="btn btn-primary" onClick={applyOrganized}>
                    노트 덮어쓰기
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
};
