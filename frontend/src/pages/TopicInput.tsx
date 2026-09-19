import { useRef, useState } from "react";
import { CameraIcon, SearchIcon } from "../components/Icons";

const TRENDING = ["Integration by Parts", "Covalent Bonds", "Macroeconomics", "Derivatives"];

export default function TopicInput({
  onSubmit,
  disabled,
}: {
  onSubmit: (topic: string, mode: "text" | "photo") => void;
  disabled: boolean;
}) {
  const [topic, setTopic] = useState("derivatives");
  const fileRef = useRef<HTMLInputElement | null>(null);

  const onPhotoPicked = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") onSubmit(reader.result, "photo");
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="animate-in">
      <h1 className="display">What are you struggling with today?</h1>

      <div className="search">
        <SearchIcon />
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Search topics, formulas, or concepts"
          disabled={disabled}
          onKeyDown={(e) => {
            if (e.key === "Enter" && topic.trim() && !disabled) onSubmit(topic.trim(), "text");
          }}
        />
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: "none" }}
          onChange={(e) => {
            onPhotoPicked(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <button
          className="icon-btn"
          disabled={disabled}
          onClick={() => fileRef.current?.click()}
          title="Snap your worked attempt — Mentra localizes the first wrong step"
          aria-label="Snap a problem"
        >
          <CameraIcon size={17} />
        </button>
      </div>

      <div className="chip-row" style={{ marginTop: 14 }}>
        <span className="faint" style={{ marginRight: 2 }}>
          Trending:
        </span>
        {TRENDING.map((t) => (
          <button
            key={t}
            className="chip"
            disabled={disabled}
            onClick={() => {
              setTopic(t);
              onSubmit(t, "text");
            }}
          >
            {t}
          </button>
        ))}
      </div>

      <button
        className="block"
        style={{ marginTop: 18 }}
        disabled={disabled || !topic.trim()}
        onClick={() => onSubmit(topic.trim(), "text")}
      >
        {disabled ? "Generating…" : "Start learning"}
      </button>

      <button
        className="ghost"
        disabled={disabled}
        onClick={() => onSubmit("sample handwritten work", "photo")}
        style={{ display: "block", margin: "6px auto 0", fontWeight: 500, fontSize: 12.5 }}
      >
        …or try a sample photo (∫ x·cos x dx with a sign slip)
      </button>
    </div>
  );
}
