// Home 페이지 - 학회 선택 및 생성
import React, { useState } from 'react';
import { useApp } from '../contexts/AppContext';

export const Home: React.FC = () => {
  const { conferences, activeConferenceId, setActiveConferenceId, navigateTo, loading, error, createConference } = useApp();

  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    location: '',
    start_date: '',
    end_date: '',
  });
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSelect = (id: string) => {
    setActiveConferenceId(id);
    navigateTo('session');
  };

  const handleCreate = async () => {
    if (!formData.id.trim() || !formData.name.trim() || !formData.start_date || !formData.end_date) {
      setFormError('ID, 학회명, 시작일, 종료일은 필수입니다.');
      return;
    }

    setCreating(true);
    setFormError(null);
    try {
      await createConference({
        id: formData.id.trim().toLowerCase().replace(/\s+/g, '-'),
        name: formData.name.trim(),
        location: formData.location.trim() || undefined,
        start_date: formData.start_date,
        end_date: formData.end_date,
      });
      setFormData({ id: '', name: '', location: '', start_date: '', end_date: '' });
      setShowForm(false);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : '생성 실패');
    } finally {
      setCreating(false);
    }
  };

  if (loading && conferences.length === 0) {
    return <div className="loading">학회 목록을 불러오는 중...</div>;
  }

  if (error) {
    return <div className="loading">오류: {error}</div>;
  }

  return (
    <div className="home-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>학회 목록</h2>
        <button
          className="btn btn-primary"
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? '취소' : '+ 새 학회'}
        </button>
      </div>

      {showForm && (
        <div style={{
          background: 'white',
          borderRadius: '12px',
          padding: '1.5rem',
          marginBottom: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        }}>
          <h3 style={{ marginBottom: '1rem', color: '#1a1a2e' }}>새 학회 등록</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#666', marginBottom: '0.25rem' }}>학회 ID *</label>
              <input
                type="text"
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                placeholder="예: ksiim-2027"
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#666', marginBottom: '0.25rem' }}>학회명 *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="예: 대한의학영상정보학회 2027"
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#666', marginBottom: '0.25rem' }}>시작일 *</label>
              <input
                type="date"
                value={formData.start_date}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#666', marginBottom: '0.25rem' }}>종료일 *</label>
              <input
                type="date"
                value={formData.end_date}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#666', marginBottom: '0.25rem' }}>장소 (선택)</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="예: 서울 양재 aT센터"
                style={{ width: '100%', padding: '0.5rem', border: '1px solid #ddd', borderRadius: '6px', fontSize: '0.9rem' }}
              />
            </div>
          </div>
          {formError && (
            <div style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '0.75rem' }}>{formError}</div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
            <button className="btn btn-secondary" onClick={() => setShowForm(false)}>취소</button>
            <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
              {creating ? '생성 중...' : '등록'}
            </button>
          </div>
        </div>
      )}

      {conferences.length === 0 ? (
        <p className="loading">등록된 학회가 없습니다. '+ 새 학회' 버튼으로 등록해주세요.</p>
      ) : (
        conferences.map((conf) => (
          <div
            key={conf.id}
            className={`conference-card ${activeConferenceId === conf.id ? 'active' : ''}`}
            onClick={() => handleSelect(conf.id)}
          >
            <h3>{conf.name}</h3>
            <p className="dates">
              {conf.start_date} ~ {conf.end_date}
              {conf.location ? ` | ${conf.location}` : ''}
            </p>
            <div className="days-summary">
              {conf.days.map((day) => (
                <span key={day.date} className="day-badge">
                  {day.label} ({day.sessions.length}개 세션)
                </span>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
};
