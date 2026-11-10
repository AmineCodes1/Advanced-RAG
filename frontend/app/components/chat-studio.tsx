"use client";

import { FormEvent, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

type Source = { source_file?: string; page?: number | null; score?: number };
type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  warning?: string;
  unsupportedClaims?: string[];
};

type SsePayload = Record<string, unknown>;

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function parseSseBlock(block: string): { event: string; data: SsePayload } | null {
  const lines = block.split("\n");
  const event = lines.find((line) => line.startsWith("event: "))?.slice(7);
  const data = lines.find((line) => line.startsWith("data: "))?.slice(6);
  if (!event || !data) return null;
  try {
    return { event, data: JSON.parse(data) as SsePayload };
  } catch {
    return null;
  }
}

export default function ChatStudio() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState("Ready");
  const [isStreaming, setIsStreaming] = useState(false);

  async function sendQuestion(event: FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isStreaming) return;

    setQuestion("");
    setMessages((current) => [...current, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);
    setIsStreaming(true);
    setStatus("Searching sources...");

    try {
      const response = await fetch(`${backendUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });
      if (!response.ok || !response.body) throw new Error("The chat service is unavailable.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantContent = "";
      let assistantSources: Source[] = [];

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const parsed = parseSseBlock(block);
          if (!parsed) continue;
          if (parsed.event === "status") setStatus(String(parsed.data.node ?? "Working...") + "...");
          if (parsed.event === "token") {
            assistantContent += String(parsed.data.text ?? "");
            setMessages((current) => current.map((message, index) => index === current.length - 1 ? { ...message, content: assistantContent } : message));
          }
          if (parsed.event === "done") {
            assistantSources = Array.isArray(parsed.data.sources) ? parsed.data.sources as Source[] : [];
            const warning = parsed.data.timeout ? "The response timed out before completion." : undefined;
            const unsupportedClaims = Array.isArray(parsed.data.unsupported_claims)
              ? parsed.data.unsupported_claims.filter((claim): claim is string => typeof claim === "string")
              : [];
            const hallucinationWarning = parsed.data.hallucination_warning
              ? "Some parts of this answer are not clearly confirmed by the sources."
              : warning;
            setMessages((current) => current.map((message, index) => index === current.length - 1 ? {
              ...message,
              content: assistantContent || "No answer was generated.",
              sources: assistantSources,
              warning: hallucinationWarning,
              unsupportedClaims,
            } : message));
          }
          if (parsed.event === "error") throw new Error(String(parsed.data.message ?? "The request failed."));
        }
        if (done) break;
      }
      setStatus("Ready");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The request failed.";
      setMessages((current) => current.map((item, index) => index === current.length - 1 ? { ...item, content: message, warning: "Try again when the backend is available." } : item));
      setStatus("Connection error");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-8 sm:py-8">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-black/10 bg-[#fbfaf6]/90 shadow-[0_24px_80px_rgba(42,52,40,0.12)]">
        <header className="flex items-center justify-between border-b border-[#17483b]/10 px-6 py-5 sm:px-9">
          <div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-xl bg-[#17483b] text-[#f4df9b]">✦</span><div><p className="font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[0.2em] text-[#c56b3d]">Workspace</p><h1 className="text-lg font-semibold text-[#17352f]">GraphRAG Studio</h1></div></div>
          <span className="font-[family-name:var(--font-geist-mono)] text-xs text-[#416058]">{status}</span>
        </header>
        <section className="flex-1 space-y-6 overflow-y-auto px-6 py-8 sm:px-24 sm:py-12">
          {messages.length === 0 && <div className="mx-auto max-w-2xl py-16"><p className="font-[family-name:var(--font-geist-mono)] text-sm uppercase tracking-[0.2em] text-[#c56b3d]">Ask your library</p><h2 className="mt-4 text-4xl font-semibold leading-tight text-[#17352f] sm:text-6xl">Find the thread between your documents.</h2><p className="mt-5 max-w-lg text-[#416058]">Ask a question and watch the local retrieval pipeline ground its answer in your sources.</p></div>}
          {messages.map((message, index) => <article key={`${message.role}-${index}`} className={message.role === "user" ? "ml-auto max-w-xl" : "max-w-3xl"}><p className="mb-2 font-[family-name:var(--font-geist-mono)] text-[10px] uppercase tracking-[0.18em] text-[#c56b3d]">{message.role === "user" ? "You" : "Assistant"}</p><div className={message.role === "user" ? "rounded-2xl rounded-tr-sm bg-[#17483b] px-5 py-4 text-white" : "text-[#17352f]"}><div className="prose prose-sm max-w-none prose-headings:text-[#17352f] prose-a:text-[#c56b3d] prose-pre:bg-[#17352f]"><ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>{message.content || (isStreaming && index === messages.length - 1 ? "..." : "")}</ReactMarkdown></div>{message.warning && <p className="mt-4 border-l-2 border-[#c56b3d] pl-3 text-sm text-[#8d4b2c]">{message.warning}</p>}{message.unsupportedClaims && message.unsupportedClaims.length > 0 && <details className="mt-2 text-sm text-[#8d4b2c]"><summary className="cursor-pointer">View claims needing verification</summary><ul className="mt-2 list-disc pl-5">{message.unsupportedClaims.map((claim, claimIndex) => <li key={`${claim}-${claimIndex}`}>{claim}</li>)}</ul></details>}{message.sources && message.sources.length > 0 && <div className="mt-5 flex flex-wrap gap-2">{message.sources.map((source, sourceIndex) => <span key={`${source.source_file}-${sourceIndex}`} className="rounded-full border border-[#17483b]/15 px-3 py-1 text-xs text-[#416058]">{source.source_file ?? "Source"}{source.page ? ` · p. ${source.page}` : ""}</span>)}</div>}</div></article>)}
        </section>
        <form onSubmit={sendQuestion} className="border-t border-[#17483b]/10 p-4 sm:p-6"><div className="flex items-end gap-3 rounded-2xl border border-[#17483b]/15 bg-white px-4 py-3 shadow-sm"><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendQuestion(event); } }} placeholder="Ask about your documents..." rows={1} className="min-h-10 flex-1 resize-none bg-transparent py-2 text-sm text-[#17352f] outline-none placeholder:text-[#416058]/50" disabled={isStreaming} /><button type="submit" disabled={!question.trim() || isStreaming} aria-label="Send question" className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#c56b3d] text-white transition hover:bg-[#a8522d] disabled:cursor-not-allowed disabled:opacity-40">↑</button></div><p className="mt-2 px-1 text-[11px] text-[#416058]/70">Enter to send · Shift+Enter for a new line</p></form>
      </div>
    </main>
  );
}
