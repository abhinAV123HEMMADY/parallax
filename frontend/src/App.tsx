import { useEffect, useRef, useState } from "react";
import { NavLink, Route, HashRouter as Router, Routes, useLocation } from "react-router-dom";
import { createUser, listUsers } from "./api/rest";
import { LearnerProvider, useLearner } from "./LearnerContext";
import { ThemeProvider, useTheme } from "./theme";
import { ChatIcon, CloseIcon, LearnIcon, MapIcon, MoonIcon, PeerIcon, SunIcon } from "./components/Icons";
import LearningPipeline from "./pages/LearningPipeline";
import MasteryMap from "./pages/MasteryMap";
import PeerFeed from "./pages/PeerFeed";
import ProtegeMode from "./pages/ProtegeMode";
import type { MentraUser } from "./types";

const NEW_PROFILE = "__new_profile__";

function NewProfileSheet({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (user: MentraUser) => void;
}) {
  const [name, setName] = useState("");
  const [grade, setGrade] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const nameRef = useRef<HTMLInputElement | null>(null);

  // autoFocus inside an animating fixed overlay makes the browser scroll the page behind
  // the dialog to the top — focus manually with preventScroll instead.
  useEffect(() => {
    nameRef.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    setFailed(false);
    try {
      onCreated(await createUser(name.trim(), grade.trim() || undefined));
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };

  return (
    <div className="scrim center" onClick={onClose}>
      <div
        className="sheet dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Create a new profile"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="row" style={{ justifyContent: "space-between", margin: "8px 0" }}>
          <div>
            <span className="eyebrow">New profile</span>
            <h3 style={{ margin: "4px 0 0" }}>Start from zero</h3>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>
        <p className="muted" style={{ marginTop: 0 }}>
          A fresh profile has no history — every mastery number it ever shows will come from
          what you actually do.
        </p>
        <div className="stack">
          <input
            ref={nameRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
          />
          <input
            value={grade}
            onChange={(e) => setGrade(e.target.value)}
            placeholder="Grade level (optional)"
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
          />
          <button disabled={busy || !name.trim()} onClick={submit}>
            {busy ? "Creating…" : "Create profile"}
          </button>
          {failed && <span className="faint">Couldn't create the profile — check the backend.</span>}
        </div>
      </div>
    </div>
  );
}

function LearnerSwitcher() {
  const { learnerId, setLearnerId } = useLearner();
  const [users, setUsers] = useState<MentraUser[]>([]);
  const [creating, setCreating] = useState(false);

  const refresh = () => listUsers().then(setUsers).catch(() => setUsers([]));
  useEffect(() => {
    refresh();
  }, []);

  const known = users.some((u) => u.id === learnerId);

  return (
    <>
      <select
        className="learner-select"
        value={learnerId}
        onChange={(e) => {
          if (e.target.value === NEW_PROFILE) setCreating(true);
          else setLearnerId(e.target.value);
        }}
        aria-label="Switch learner"
      >
        {!known && <option value={learnerId}>{learnerId.replace("u_", "@")}</option>}
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
          </option>
        ))}
        <option value={NEW_PROFILE}>＋ New profile…</option>
      </select>
      {creating && (
        <NewProfileSheet
          onClose={() => setCreating(false)}
          onCreated={(u) => {
            setLearnerId(u.id);
            setCreating(false);
            refresh();
          }}
        />
      )}
    </>
  );
}

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
        <Route path="/peer" element={<PeerFeed />} />
      </Routes>
    </div>
  );
}

const tabClass = ({ isActive }: { isActive: boolean }) => (isActive ? "tab active" : "tab");

const TABS = [
  { to: "/", end: true, label: "Learn", Icon: LearnIcon },
  { to: "/map", end: false, label: "Mastery", Icon: MapIcon },
  { to: "/protege", end: false, label: "Teach", Icon: ChatIcon },
  { to: "/peer", end: false, label: "Squads", Icon: PeerIcon },
];

export default function App() {
  return (
    <ThemeProvider>
      <LearnerProvider>
        <Router>
          <div className="app-shell">
            <header className="app-header">
              <div className="header-lead">
                <LearnerSwitcher />
              </div>
              <div className="brand">Mentra</div>
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
