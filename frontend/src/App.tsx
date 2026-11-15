import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  ArrowUp,
  Check,
  ChevronDown,
  CircleHelp,
  Leaf,
  MapPin,
  Menu,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Sprout,
  Mic,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";

type RecognitionResult = { transcript: string };
type RecognitionEvent = Event & { resultIndex: number; results: ArrayLike<ArrayLike<RecognitionResult> & { isFinal: boolean }> };
type RecognitionLike = {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void;
};
type RecognitionConstructor = new () => RecognitionLike;
type SpeechWindow = Window & { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor };

type Municipality = { ponto_id: string; nome: string; ibge: number | null };
type Source = { id: string; tema: string; rotulo: string; texto_simples: string; origem?: string; lacuna: boolean };
type Chip = { rotulo: string; texto: string };
type ConversationResponse = {
  resposta: string;
  estado: Record<string, unknown>;
  acao: "responder" | "perguntar" | "confirmar" | "recusar";
  chips: Chip[];
  entendido?: string | null;
  fontes: Source[];
  assistente?: string;
};
type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  understood?: string | null;
  sources?: Source[];
};
type PendingReply = { text: string; displayText: string };

const SUGGESTIONS = [
  { icon: Sprout, text: "Quero conversar sobre o que plantar" },
  { icon: Leaf, text: "Quando a vegetação costuma sofrer por aqui?" },
  { icon: MapPin, text: "O que os dados mostram sobre a chuva daqui?" },
];

function labelForPoint(point: Municipality) {
  const uf = point.ponto_id.split("_").at(-1)?.toUpperCase() ?? "";
  return point.nome.endsWith(`(${uf})`) ? point.nome : `${point.nome} · ${uf}`;
}

function cityName(point: Municipality) {
  return point.nome.replace(/\s*\([A-Z]{2}\)$/, "");
}

function normalizeSearch(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("pt-BR");
}

function mergeSpeechText(previous: string, next: string) {
  const clean = (value: string) => value.replace(/\s+/g, " ").trim();
  const a = clean(previous), b = clean(next);
  if (!a) return b;
  if (!b) return a;
  const lowerA = a.toLocaleLowerCase("pt-BR"), lowerB = b.toLocaleLowerCase("pt-BR");
  if (lowerA === lowerB || lowerA.endsWith(lowerB)) return a;
  if (lowerB.startsWith(lowerA)) return b;
  const aWords = lowerA.split(" "), bWords = lowerB.split(" ");
  let overlap = Math.min(aWords.length, bWords.length);
  while (overlap > 0 && aWords.slice(-overlap).join(" ") !== bWords.slice(0, overlap).join(" ")) overlap--;
  return clean(`${a} ${bWords.slice(overlap).join(" ")}`);
}

function mergeRecognitionResults(results: string[]) {
  const clean = results.map((text) => text.replace(/\s+/g, " ").trim()).filter(Boolean);
  const keep = clean.filter((text, index) => !clean.slice(index + 1).some((later) => later.toLocaleLowerCase("pt-BR").startsWith(text.toLocaleLowerCase("pt-BR"))));
  return keep.reduce((combined, text) => mergeSpeechText(combined, text), "");
}

function shortSpeechParts(text: string) {
  const sentences = text.replace(/\s+/g, " ").match(/[^.!?;:]+[.!?;:]?/g)?.map((part) => part.trim()).filter(Boolean) ?? [text];
  const parts: string[] = [];
  let current = "";
  for (const sentence of sentences) {
    if (current && `${current} ${sentence}`.length > 170) {
      parts.push(current);
      current = sentence;
    } else current = `${current} ${sentence}`.trim();
  }
  if (current) parts.push(current);
  return parts;
}

function usefulUnderstanding(value?: string | null, question = "") {
  if (!value) return null;
  const clean = value.replace(/^\s*entendi\s*:\s*/i, "").trim();
  if (!clean) return null;
  const norm = (text: string) => normalizeSearch(text).replace(/[.,!?;:]/g, " ").replace(/\s+/g, " ").trim();
  const understood = norm(clean), asked = norm(question);
  if (!understood || understood === asked || asked.includes(understood) || understood.includes(asked)) return null;
  return clean;
}

function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <span className={`brand-mark${small ? " brand-mark-small" : ""}`} aria-hidden="true">
      <img src="/maira.jpeg" alt="" />
    </span>
  );
}

function SourceDisclosure({ sources }: { sources: Source[] }) {
  if (!sources?.length) return null;
  return (
    <details className="source-disclosure">
      <summary>
        <ShieldCheck size={16} strokeWidth={1.8} aria-hidden="true" />
        <span>De onde vieram estas informações</span>
        <ChevronDown className="source-chevron" size={15} aria-hidden="true" />
      </summary>
      <div className="source-list">
        {sources.map((source, index) => (
          <article className="source-item" key={`${source.id}-${index}`}>
            <div className="source-item-heading">
              <span>{source.rotulo || source.tema || `Informação ${index + 1}`}</span>
              {source.lacuna && <span className="source-gap">Sem dado</span>}
            </div>
            <p>{source.texto_simples}</p>
          </article>
        ))}
      </div>
    </details>
  );
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="message-row user-row">
        <div className="user-message">{message.text}</div>
      </div>
    );
  }

  return (
    <article className="message-row assistant-row" aria-label="Resposta de Maíra">
      <BrandMark small />
      <div className="assistant-message-content">
        <div className="message-byline">
          <strong>Maíra</strong>
          <span>assistente automática</span>
        </div>
        {message.understood && (
          <div className="understood-note"><Check size={14} aria-hidden="true" /> Entendi: {message.understood}</div>
        )}
        <div className="assistant-copy">{message.text}</div>
        {message.sources && <SourceDisclosure sources={message.sources} />}
        <p className="technical-reminder">Use esta conversa como apoio. Confirme cada situação com um técnico local.</p>
      </div>
    </article>
  );
}

function App() {
  const Recognition = typeof window !== "undefined" ? (window as SpeechWindow).SpeechRecognition ?? (window as SpeechWindow).webkitSpeechRecognition : undefined;
  const [speechSupported] = useState(Boolean(Recognition));
  const [listening, setListening] = useState(false);
  const [heardText, setHeardText] = useState("");
  const [voiceMode, setVoiceMode] = useState<"continuous" | "tap">("continuous");
  const [speaking, setSpeaking] = useState(false);
  const recognitionRef = useRef<RecognitionLike | null>(null);
  const recognitionActiveRef = useRef(false);
  const recognitionFinalRef = useRef("");
  const recognitionInterimRef = useRef("");
  const lastSpeechAtRef = useRef(0);
  const restartRecognitionRef = useRef(false);
  const speechStopRef = useRef(false);
  const speechRequestRef = useRef(false);
  const voiceSessionRef = useRef(false);
  const [municipalities, setMunicipalities] = useState<Municipality[]>([]);
  const [municipality, setMunicipality] = useState<Municipality | null>(null);
  const [query, setQuery] = useState("");
  const [isPickerOpen, setPickerOpen] = useState(false);
  const [pickerIndex, setPickerIndex] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chips, setChips] = useState<Chip[]>([]);
  const [conversationState, setConversationState] = useState<Record<string, unknown> | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [errorText, setErrorText] = useState("");
  const [retryRequest, setRetryRequest] = useState<PendingReply | null>(null);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const transcriptRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => {
    recognitionActiveRef.current = false;
    try { recognitionRef.current?.stop(); } catch { /* already stopped */ }
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/municipios").then(async (response) => {
        if (!response.ok) throw new Error("Não consegui carregar os municípios.");
        return response.json() as Promise<Municipality[]>;
      }),
      fetch("/saude").then((response) => response.ok),
    ])
      .then(([points, healthy]) => {
        if (!active) return;
        const sorted = points.slice().sort((a, b) => labelForPoint(a).localeCompare(labelForPoint(b), "pt-BR"));
        setMunicipalities(sorted);
        setApiReady(healthy);
      })
      .catch(() => {
        if (active) setApiReady(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (messages.length && transcriptRef.current) {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      transcriptRef.current.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: reducedMotion ? "auto" : "smooth" });
    }
  }, [messages, busy, chips]);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 4400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    function handleGlobalKeys(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setMessages([]);
        setChips([]);
        setConversationState(null);
        setDraft("");
        setErrorText("");
        setRetryRequest(null);
        composerRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleGlobalKeys);
    return () => window.removeEventListener("keydown", handleGlobalKeys);
  }, []);

  useEffect(() => {
    function dismissPicker(event: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(event.target as Node)) setPickerOpen(false);
    }
    document.addEventListener("mousedown", dismissPicker);
    return () => document.removeEventListener("mousedown", dismissPicker);
  }, []);

  useEffect(() => {
    if (!drawerOpen) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const closeButton = document.querySelector<HTMLButtonElement>(".sidebar-close");
    closeButton?.focus();
    function handleDrawerKeys(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setDrawerOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const drawer = document.querySelector<HTMLElement>(".sidebar-drawer.open");
      const focusable = drawer ? Array.from(drawer.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex="0"]')).filter((node) => node.offsetParent !== null) : [];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", handleDrawerKeys);
    return () => {
      window.removeEventListener("keydown", handleDrawerKeys);
      previousFocus?.focus();
    };
  }, [drawerOpen]);

  function stopRecognition() {
    recognitionActiveRef.current = false;
    restartRecognitionRef.current = false;
    setListening(false);
    try { recognitionRef.current?.stop(); } catch { /* browser may already have ended */ }
    recognitionRef.current = null;
  }

  function finishRecognition() {
    const spoken = mergeSpeechText(recognitionFinalRef.current, recognitionInterimRef.current);
    stopRecognition();
    setHeardText("");
    recognitionFinalRef.current = "";
    recognitionInterimRef.current = "";
    lastSpeechAtRef.current = 0;
    if (!spoken) {
      setStatusText("Não ouvi nada. Toque em Falar e tente de novo.");
      if (voiceMode === "continuous" && voiceSessionRef.current) window.setTimeout(openRecognition, 500);
      return;
    }
    void requestReply({ text: spoken, displayText: spoken }, true);
  }

  function openRecognition() {
    if (!Recognition || recognitionActiveRef.current || busy) return;
    recognitionActiveRef.current = true;
    restartRecognitionRef.current = true;
    voiceSessionRef.current = true;
    recognitionFinalRef.current = "";
    recognitionInterimRef.current = "";
    lastSpeechAtRef.current = 0;
    setHeardText("");
    setStatusText("Pode falar. Vou esperar um pouco de silêncio antes de enviar.");
    setListening(true);

    const start = () => {
      if (!recognitionActiveRef.current || !Recognition) return;
      const recognition = new Recognition();
      recognition.lang = "pt-BR";
      recognition.continuous = true;
      recognition.interimResults = true;
      recognitionRef.current = recognition;
      recognition.onresult = (event) => {
        const results = Array.from(event.results).map((result) => ({ text: result[0]?.transcript ?? "", final: result.isFinal }));
        const finals = mergeRecognitionResults(results.filter((result) => result.final).map((result) => result.text));
        const interim = mergeRecognitionResults(results.filter((result) => !result.final).map((result) => result.text));
        if (finals || interim) lastSpeechAtRef.current = Date.now();
        recognitionFinalRef.current = mergeSpeechText(recognitionFinalRef.current, finals);
        recognitionInterimRef.current = interim;
        setHeardText(mergeSpeechText(recognitionFinalRef.current, interim));
      };
      recognition.onerror = (event) => {
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          recognitionActiveRef.current = false;
          restartRecognitionRef.current = false;
          setListening(false);
          setStatusText("Permita o uso do microfone nas configurações do navegador.");
        }
      };
      recognition.onend = () => {
        if (!recognitionActiveRef.current) return;
        const last = lastSpeechAtRef.current;
        if (last && Date.now() - last >= 3500) {
          finishRecognition();
          return;
        }
        if (restartRecognitionRef.current) window.setTimeout(start, 180);
      };
      try { recognition.start(); } catch {
        recognitionRef.current = null;
        if (recognitionActiveRef.current) window.setTimeout(start, 250);
      }
    };
    start();
  }

  useEffect(() => {
    if (!listening) return;
    const timer = window.setInterval(() => {
      const last = lastSpeechAtRef.current;
      if (recognitionActiveRef.current && last && Date.now() - last >= 3500) finishRecognition();
    }, 250);
    return () => window.clearInterval(timer);
  }, [listening]);

  async function speakResponse(text: string) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    speechStopRef.current = false;
    setSpeaking(true);
    const voices = window.speechSynthesis.getVoices();
    const brazilian = voices.find((voice) => /^pt[-_]BR$/i.test(voice.lang) || /portugu[eê]s.*brasil|brazil/i.test(voice.name));
    try {
      for (const part of shortSpeechParts(text)) {
        if (speechStopRef.current) break;
        await new Promise<void>((resolve) => {
          let done = false;
          let quietPolls = 0;
          const finish = () => {
            if (done) return;
            done = true;
            clearInterval(poll);
            clearTimeout(watchdog);
            resolve();
          };
          const utterance = new SpeechSynthesisUtterance(part);
          utterance.lang = "pt-BR";
          if (brazilian) utterance.voice = brazilian;
          utterance.onend = finish;
          utterance.onerror = finish;
          const watchdog = window.setTimeout(finish, 5000 + part.length * 140);
          const poll = window.setInterval(() => {
            if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending) {
              quietPolls += 1;
              if (quietPolls >= 4) finish();
            } else quietPolls = 0;
          }, 300);
          window.speechSynthesis.speak(utterance);
        });
      }
    } finally {
      setSpeaking(false);
    }
  }

  function toggleVoice() {
    if (speaking || speechRequestRef.current) {
      speechStopRef.current = true;
      speechRequestRef.current = false;
      window.speechSynthesis?.cancel();
      setSpeaking(false);
      return;
    }
    if (listening) {
      finishRecognition();
      return;
    }
    if (!busy) { voiceSessionRef.current = true; openRecognition(); }
  }

  const visibleMunicipalities = municipalities
    .filter((point) => normalizeSearch(labelForPoint(point)).includes(normalizeSearch(query)))
    .slice(0, 12);

  function startNewConversation() {
    setMessages([]);
    setChips([]);
    setConversationState(null);
    setDraft("");
    setErrorText("");
    setRetryRequest(null);
    setDrawerOpen(false);
    composerRef.current?.focus();
  }

  function chooseMunicipality(point: Municipality) {
    const changed = municipality?.ponto_id !== point.ponto_id;
    setMunicipality(point);
    setQuery("");
    setPickerOpen(false);
    setDrawerOpen(false);
    if (changed && messages.length) {
      setMessages([]);
      setChips([]);
      setConversationState(null);
      setErrorText("");
      setRetryRequest(null);
      setNotice("Local atualizado. A conversa recomeçou para manter os dados do município certos.");
    }
  }

  async function requestReply(request: PendingReply, addUserMessage: boolean) {
    if (busy || !request.text.trim()) return;
    const cleanText = request.text.trim();
    if (addUserMessage) {
      const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", text: request.displayText };
      setMessages((current) => [...current, userMessage]);
    }
    setBusy(true);
    setErrorText("");
    setRetryRequest(null);
    setChips([]);
    setStatusText("Estou olhando os dados do seu local...");

    const milestones = [
      window.setTimeout(() => setStatusText("Estou olhando os dados do seu local..."), 1200),
      window.setTimeout(() => setStatusText("Conferindo o que isso muda no seu caso..."), 4500),
      window.setTimeout(() => setStatusText("Montando a resposta de um jeito simples..."), 8000),
    ];
    let responseTimer: number | undefined;
    let narrationTimer: number | undefined;

    try {
      const payload: { mensagem: string; estado: Record<string, unknown> | null; ponto_id?: string } = {
        mensagem: cleanText,
        estado: conversationState,
      };
      if (municipality) payload.ponto_id = municipality.ponto_id;
      const controller = new AbortController();
      responseTimer = window.setTimeout(() => controller.abort(), 100000);
      if (voiceSessionRef.current && "speechSynthesis" in window) {
        narrationTimer = window.setTimeout(() => {
          if (!voiceSessionRef.current) return;
          speechRequestRef.current = true;
          void speakResponse("Só um instante, estou olhando os dados.").finally(() => { speechRequestRef.current = false; });
        }, 3000);
      }
      const response = await fetch("/conversa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const retryAfter = response.headers.get("Retry-After");
        const detail = typeof body?.detail === "string" ? body.detail : "Não consegui responder agora. Tente novamente.";
        throw new Error(response.status === 429 && retryAfter ? `${detail} Você pode tentar de novo em ${retryAfter} segundos.` : detail);
      }

      const result = body as ConversationResponse;
      setConversationState(result.estado);
      setMessages((current) => [...current, {
        id: crypto.randomUUID(),
        role: "assistant",
        text: result.resposta,
        understood: usefulUnderstanding(result.entendido, cleanText),
        sources: result.fontes,
      }]);
      setChips(result.chips ?? []);
      if (voiceSessionRef.current) {
        speechRequestRef.current = true;
        await speakResponse(result.resposta);
        speechRequestRef.current = false;
        if (voiceMode === "continuous" && voiceSessionRef.current) window.setTimeout(openRecognition, 450);
      }
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "AbortError";
      setErrorText(timedOut ? "A resposta demorou. Tente de novo." : "Não consegui responder agora. Tente de novo.");
      setRetryRequest({ text: cleanText, displayText: request.displayText });
      if (voiceSessionRef.current && voiceMode === "continuous") window.setTimeout(openRecognition, 500);
    } finally {
      milestones.forEach(window.clearTimeout);
      if (responseTimer) window.clearTimeout(responseTimer);
      if (narrationTimer) window.clearTimeout(narrationTimer);
      speechRequestRef.current = false;
      setBusy(false);
      setStatusText("");
    }
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    if (composerRef.current) composerRef.current.style.height = "auto";
    void requestReply({ text, displayText: text }, true);
  }

  function useChip(chip: Chip) {
    void requestReply({ text: chip.texto, displayText: chip.rotulo }, true);
  }

  function handleComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function handlePickerKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setPickerOpen(true);
      setPickerIndex((index) => Math.min(index + 1, visibleMunicipalities.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setPickerIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && isPickerOpen && visibleMunicipalities[pickerIndex]) {
      event.preventDefault();
      chooseMunicipality(visibleMunicipalities[pickerIndex]);
    } else if (event.key === "Escape") {
      setPickerOpen(false);
    }
  }

  function pickerInput() {
    return (
      <div className="municipality-picker" ref={pickerRef}>
        <label className="field-label" htmlFor="municipality-search">Seu município <span>opcional</span></label>
        <div className="municipality-input-wrap">
          <Search size={17} aria-hidden="true" />
          <input
            id="municipality-search"
            type="text"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={isPickerOpen}
            aria-controls="municipality-options"
            aria-activedescendant={isPickerOpen && visibleMunicipalities[pickerIndex] ? `point-${visibleMunicipalities[pickerIndex].ponto_id}` : undefined}
            placeholder={municipality ? labelForPoint(municipality) : apiReady === false ? "Servidor indisponível" : "Buscar município"}
            value={query}
            disabled={apiReady === false}
            onFocus={() => { setPickerOpen(true); setPickerIndex(0); }}
            onChange={(event) => { setQuery(event.target.value); setPickerIndex(0); setPickerOpen(true); }}
            onKeyDown={handlePickerKey}
          />
          {municipality && <button type="button" className="clear-location" aria-label="Limpar município" onClick={() => { setMunicipality(null); setQuery(""); setPickerOpen(false); if (messages.length) startNewConversation(); }}><X size={14} /></button>}
        </div>
        {isPickerOpen && apiReady && (
          <div className="municipality-options" id="municipality-options" role="listbox" aria-label="Municípios disponíveis">
            {visibleMunicipalities.length ? visibleMunicipalities.map((point, index) => (
              <button
                type="button"
                role="option"
                aria-selected={municipality?.ponto_id === point.ponto_id}
                id={`point-${point.ponto_id}`}
                className={index === pickerIndex ? "municipality-option active" : "municipality-option"}
                key={point.ponto_id}
                onMouseEnter={() => setPickerIndex(index)}
                onClick={() => chooseMunicipality(point)}
              >
                <MapPin size={15} aria-hidden="true" />
                <span>{labelForPoint(point)}</span>
                {municipality?.ponto_id === point.ponto_id && <Check size={15} aria-hidden="true" />}
              </button>
            )) : <p className="no-municipalities">Nenhum município encontrado.</p>}
          </div>
        )}
        {municipality && <p className="field-help">Trocar o município inicia uma conversa nova.</p>}
        {apiReady === false && <p className="field-help field-error">Não foi possível conectar à API. Verifique se o servidor está ligado.</p>}
      </div>
    );
  }

  function sidebar() {
    return (
      <aside className="sidebar" aria-label="Configurações da conversa">
        <div className="sidebar-brand">
          <BrandMark />
          <div className="brand-copy"><strong>Maíra</strong><span>uma conversa do SULCO</span></div>
          <button type="button" className="icon-button sidebar-close" aria-label="Fechar menu" onClick={() => setDrawerOpen(false)}><X size={19} /></button>
        </div>

        <button type="button" className="new-chat-button" onClick={startNewConversation}>
          <Plus size={18} strokeWidth={2} aria-hidden="true" />
          <span>Nova conversa</span>
          <span className="new-chat-key" aria-hidden="true">⌘ / Ctrl K</span>
        </button>

        <div className="sidebar-divider" />

        <div className="sidebar-section-heading"><span>SEU LOCAL</span><span className="optional-dot">●</span></div>
        {pickerInput()}

        <div className="location-card">
          <div className="location-icon"><MapPin size={17} strokeWidth={1.8} aria-hidden="true" /></div>
          <div>
            <strong>{municipality ? cityName(municipality) : "Sem município"}</strong>
            <span>{municipality ? `Dados da região · ${municipality.ponto_id.split("_").at(-1)?.toUpperCase()}` : "Escolha um local para dar contexto"}</span>
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="sidebar-bottom-icon"><CircleHelp size={17} aria-hidden="true" /></div>
          <div>
            <strong>Como a Maíra funciona</strong>
            <p>Ela organiza informações disponíveis. Não substitui quem conhece sua terra.</p>
          </div>
        </div>
        <div className="sidebar-footer"><span className={`connection-dot ${apiReady === false ? "offline" : ""}`} />{apiReady === false ? "Sem conexão com os dados" : "Dados locais protegidos"}</div>
      </aside>
    );
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="app-shell">
      <div className={`drawer-scrim${drawerOpen ? " visible" : ""}`} onClick={() => setDrawerOpen(false)} aria-hidden="true" />
      <div className={`sidebar-drawer${drawerOpen ? " open" : ""}`} role={drawerOpen ? "dialog" : undefined} aria-modal={drawerOpen || undefined} aria-label={drawerOpen ? "Menu da conversa" : undefined}>{sidebar()}</div>
      <main className="chat-shell">
        <header className="topbar">
          <button type="button" className="icon-button menu-trigger" aria-label="Abrir menu" onClick={() => setDrawerOpen(true)}><Menu size={20} /></button>
          <div className="topbar-identity">
            <span className="topbar-mobile-mark"><BrandMark small /></span>
            <div><strong>Conversa sobre sua terra</strong><span>com Maíra, assistente automática</span></div>
          </div>
          <div className="topbar-actions">
            {municipality && <div className="active-location"><MapPin size={14} aria-hidden="true" />{cityName(municipality)}</div>}
            <button type="button" className="topbar-new-chat" onClick={startNewConversation} aria-label="Começar nova conversa"><Plus size={17} /><span>Nova conversa</span></button>
          </div>
        </header>

        <section className={`conversation-area${hasMessages ? " has-messages" : ""}`} aria-label="Conversa com Maíra">
          {!hasMessages ? (
            <div className="welcome-screen">
              <div className="welcome-mark"><BrandMark /></div>
              <p className="welcome-eyebrow">UMA LEITURA DO SEU TERRITÓRIO</p>
              <h1>O que você quer<br className="desktop-break" /> entender sobre a sua terra?</h1>
              <p className="welcome-description">Pergunte sobre chuva, vegetação, solo ou rotação de culturas. A Maíra ajuda a organizar os dados para conversar com um técnico.</p>
              <div className="welcome-suggestions" aria-label="Sugestões de perguntas">
                {SUGGESTIONS.map(({ icon: Icon, text }) => (
                  <button type="button" className="suggestion-card" key={text} onClick={() => { void requestReply({ text, displayText: text }, true); }}>
                    <span className="suggestion-icon"><Icon size={18} strokeWidth={1.8} aria-hidden="true" /></span>
                    <span>{text}</span>
                    <ArrowUp className="suggestion-arrow" size={16} aria-hidden="true" />
                  </button>
                ))}
              </div>
              {!municipality && <p className="welcome-location-hint"><MapPin size={15} aria-hidden="true" /> Se quiser, escolha o município no menu. Sem ele, a Maíra pode perguntar onde fica sua área.</p>}
            </div>
          ) : (
            <div className="transcript" ref={transcriptRef} role="log" aria-label="Mensagens da conversa" aria-live="polite" aria-relevant="additions text">
              <div className="transcript-inner">
                {messages.map((message) => <Message key={message.id} message={message} />)}
                {busy && (
                  <div className="message-row assistant-row loading-row" aria-busy="true">
                    <BrandMark small />
                    <div className="loading-content">
                      <div className="message-byline"><strong>Maíra</strong><span>assistente automática</span></div>
                      <div className="loading-indicator"><span /><span /><span /><p>{statusText}</p></div>
                    </div>
                  </div>
                )}
                {chips.length > 0 && !busy && (
                  <div className="followup-chips" aria-label="Respostas rápidas">
                    <span className="chips-prompt">Escolha uma opção ou escreva sua resposta</span>
                    <div className="chips-list">
                      {chips.map((chip, index) => <button type="button" key={`${chip.rotulo}-${index}`} onClick={() => useChip(chip)}>{chip.rotulo}<ArrowUp size={14} aria-hidden="true" /></button>)}
                    </div>
                  </div>
                )}
                <div className="transcript-end" />
              </div>
            </div>
          )}
        </section>

        <footer className={`composer-zone${hasMessages ? " composer-in-thread" : ""}`}>
          <div className="composer-wrap">
            {busy && <p className="composer-status" role="status">{statusText}</p>}
            {errorText && (
              <div className="send-error" role="alert">
                <span>{errorText}</span>
                {retryRequest && <button type="button" onClick={() => void requestReply(retryRequest, false)}><RotateCcw size={14} /> Tentar de novo</button>}
              </div>
            )}
            {listening && <div className="heard-preview" aria-live="polite"><strong>Estou ouvindo</strong><span>{heardText || "Pode falar..."}</span><button type="button" onClick={finishRecognition}>Terminei</button></div>}
            <form className="composer" onSubmit={submit}>
              {speechSupported && <button type="button" className={`voice-button${listening ? " is-listening" : ""}${speaking ? " is-speaking" : ""}`} onClick={toggleVoice} aria-label={speaking ? "Interromper leitura" : listening ? "Terminei de falar" : "Falar com Maíra"}>
                {speaking ? <VolumeX size={20} /> : listening ? <span className="voice-stop" /> : <Mic size={20} />}
                <span>{speaking ? "Parar" : listening ? "Terminei" : "Falar"}</span>
              </button>}
              <textarea
                ref={composerRef}
                aria-label="Escreva sua pergunta para Maíra"
                placeholder="Escreva sua pergunta…"
                value={draft}
                maxLength={2000}
                rows={1}
                disabled={apiReady === false}
                onChange={(event) => {
                  setDraft(event.target.value);
                  event.target.style.height = "auto";
                  event.target.style.height = `${Math.min(event.target.scrollHeight, 160)}px`;
                }}
                onKeyDown={handleComposerKey}
              />
              <button className="send-button" type="submit" disabled={!draft.trim() || busy || apiReady === false} aria-label="Enviar pergunta">
                {busy ? <span className="send-spinner" /> : <ArrowUp size={19} strokeWidth={2.3} />}
              </button>
            </form>
            <div className="composer-meta"><span>Enter envia · Shift + Enter quebra a linha</span><span>{draft.length > 1700 ? `${draft.length}/2000` : ""}</span></div>
            {speechSupported && <div className="voice-options">
              <label htmlFor="voice-mode">Conversa por voz</label>
              <select id="voice-mode" value={voiceMode} onChange={(event) => setVoiceMode(event.target.value as "continuous" | "tap")}>
                <option value="continuous">Contínua</option><option value="tap">Um toque por vez</option>
              </select>
              {speaking && <span><Volume2 size={14} /> Maíra está lendo a resposta</span>}
            </div>}
            <p className="composer-notice"><ShieldCheck size={13} aria-hidden="true" /> Maíra é automática, não é pessoa nem técnica. Não compartilhe dados pessoais.</p>
          </div>
        </footer>
      </main>

      {notice && <div className="toast-notice" role="status"><Check size={16} />{notice}</div>}
    </div>
  );
}

export default App;
