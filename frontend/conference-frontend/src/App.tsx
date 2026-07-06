import { AppProvider, NoteProvider, useApp } from './contexts';
import { Home, SessionView, Attachments, Report } from './pages';
import './App.css';

function AppContent() {
  const { currentPage, navigateTo, activeConferenceId } = useApp();

  const renderPage = () => {
    switch (currentPage) {
      case 'home':
        return <Home />;
      case 'session':
        return activeConferenceId ? <SessionView /> : <Home />;
      case 'attachments':
        return activeConferenceId ? <Attachments /> : <Home />;
      case 'report':
        return activeConferenceId ? <Report /> : <Home />;
      default:
        return <Home />;
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title" onClick={() => navigateTo('home')}>
          Conference Notes
        </h1>
        <nav className="app-nav">
          <button
            onClick={() => navigateTo('home')}
            className={currentPage === 'home' ? 'active' : ''}
          >
            홈
          </button>
          <button
            onClick={() => navigateTo('session')}
            className={currentPage === 'session' ? 'active' : ''}
            disabled={!activeConferenceId}
          >
            메모
          </button>
          <button
            onClick={() => navigateTo('attachments')}
            className={currentPage === 'attachments' ? 'active' : ''}
            disabled={!activeConferenceId}
          >
            자료
          </button>
          <button
            onClick={() => navigateTo('report')}
            className={currentPage === 'report' ? 'active' : ''}
            disabled={!activeConferenceId}
          >
            리포트
          </button>
        </nav>
      </header>
      <main className="app-main">
        {renderPage()}
      </main>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <NoteProvider>
        <AppContent />
      </NoteProvider>
    </AppProvider>
  );
}

export default App;
