import { NavLink, Route, HashRouter as Router, Routes, useLocation } from "react-router-dom";
import { LearnerProvider } from "./LearnerContext";
import { ThemeProvider, useTheme } from "./theme";
import { ChatIcon, LearnIcon, MapIcon, MoonIcon, SunIcon } from "./components/Icons";
import LearningPipeline from "./pages/LearningPipeline";
import MasteryMap from "./pages/MasteryMap";
import NotesExport from "./pages/NotesExport";
import ProtegeMode from "./pages/ProtegeMode";

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button className="icon-btn" onClick={toggle} aria-label="Toggle color theme">
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <div className="page" key={location.pathname}>
      <Routes location={location}>
        <Route path="/" element={<LearningPipeline />} />
        <Route path="/map" element={<MasteryMap />} />
        <Route path="/protege" element={<ProtegeMode />} />
        {/* Not tabs — the Chrome extension opens these directly to hand off a PDF export. */}
        <Route path="/notes/export/topic/:topicId" element={<NotesExport />} />
        <Route path="/notes/export/:videoId" element={<NotesExport />} />
      </Routes>
    </div>
  );
}

const tabClass = ({ isActive }: { isActive: boolean }) => (isActive ? "tab active" : "tab");

const TABS = [
  { to: "/", end: true, label: "Learn", Icon: LearnIcon },
  { to: "/map", end: false, label: "Mastery", Icon: MapIcon },
  { to: "/protege", end: false, label: "Teach", Icon: ChatIcon },
];

export default function App() {
  return (
    <ThemeProvider>
      <LearnerProvider>
        <Router>
          <div className="app-shell">
            <header className="app-header">
              <div className="brand">Parallax</div>
              <div className="header-actions">
                <ThemeToggle />
              </div>
            </header>

            <main className="app-main">
              <AnimatedRoutes />
            </main>

            <nav className="tabbar">
              {TABS.map(({ to, end, label, Icon }) => (
                <NavLink key={to} to={to} end={end} className={tabClass}>
                  <span className="tab-icon">
                    <Icon size={19} />
                  </span>
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        </Router>
      </LearnerProvider>
    </ThemeProvider>
  );
}
