import React, { createContext, useContext, useState } from "react";

interface LearnerContextValue {
  learnerId: string;
  setLearnerId: (id: string) => void;
  lastTopic: string;
  setLastTopic: (topic: string) => void;
}

const LearnerContext = createContext<LearnerContextValue | null>(null);

export function LearnerProvider({ children }: { children: React.ReactNode }) {
  const [learnerId, setLearnerId] = useState(localStorage.getItem("mentra_learner_id") ?? "u_amy");
  // Whatever topic was last generated on the main Learn page — Protégé Mode defaults to it
  // instead of a hardcoded topic, falling back to "derivatives" only for a first-ever visit.
  const [lastTopic, setLastTopic] = useState(localStorage.getItem("mentra_last_topic") ?? "derivatives");

  const update = (id: string) => {
    localStorage.setItem("mentra_learner_id", id);
    setLearnerId(id);
  };

  const updateTopic = (topic: string) => {
    localStorage.setItem("mentra_last_topic", topic);
    setLastTopic(topic);
  };

  return (
    <LearnerContext.Provider value={{ learnerId, setLearnerId: update, lastTopic, setLastTopic: updateTopic }}>
      {children}
    </LearnerContext.Provider>
  );
}

export function useLearner() {
  const ctx = useContext(LearnerContext);
  if (!ctx) throw new Error("useLearner must be used within LearnerProvider");
  return ctx;
}
