"use client";

import { useState, useCallback, useEffect } from "react";

interface ClassificationResult {
  category: string;
  confidence: number;
  suggested_response: string;
  processed_text?: string;
}

interface GmailMessage {
  id: string;
  threadId: string;
  snippet: string;
  subject: string;
  from: string;
  date: string;
  labelIds: string[];
}

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  // Gmail
  const [gmailAuth, setGmailAuth] = useState<{ email: string; name?: string } | null>(null);
  const [gmailLoading, setGmailLoading] = useState(true);
  const [menuOpen, setMenuOpen] = useState(false);
  const [emails, setEmails] = useState<GmailMessage[]>([]);
  const [emailsLoading, setEmailsLoading] = useState(false);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);

  const resetForm = useCallback(() => {
    setFile(null);
    setText("");
    setResult(null);
    setError(null);
  }, []);

  // Verificar status do Gmail ao carregar
  useEffect(() => {
    fetch(`${API_URL}/api/auth/gmail/status`)
      .then((r) => r.json())
      .then((data) => {
        if (data.authenticated) {
          setGmailAuth({ email: data.email, name: data.name });
        } else {
          setGmailAuth(null);
        }
      })
      .catch(() => setGmailAuth(null))
      .finally(() => setGmailLoading(false));
  }, []);

  // Tratar retorno do OAuth (gmail_success ou gmail_error na URL)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const success = params.get("gmail_success");
    const err = params.get("gmail_error");
    const email = params.get("email");
    if (success) {
      setGmailAuth({ email: email || "" });
      setError(null);
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (err) {
      setError(decodeURIComponent(err));
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const handleConnectGmail = () => {
    fetch(`${API_URL}/api/auth/gmail/url`)
      .then((r) => r.json())
      .then((data) => {
        window.location.href = data.auth_url;
      })
      .catch((err) => setError(err.message || "Erro ao obter URL de autenticação"));
  };

  const handleDisconnectGmail = async () => {
    try {
      await fetch(`${API_URL}/api/auth/gmail/revoke`, { method: "POST" });
      setGmailAuth(null);
      setEmails([]);
      setSelectedEmailId(null);
      setResult(null);
    } catch {
      setError("Erro ao desconectar");
    }
  };

  const fetchEmails = useCallback(() => {
    if (!gmailAuth) return;
    setEmailsLoading(true);
    fetch(`${API_URL}/api/emails?max_results=20`)
      .then((r) => {
        if (!r.ok) throw new Error("Erro ao buscar emails");
        return r.json();
      })
      .then((data) => setEmails(data.emails || []))
      .catch((err) => setError(err.message))
      .finally(() => setEmailsLoading(false));
  }, [gmailAuth]);

  useEffect(() => {
    if (gmailAuth) fetchEmails();
  }, [gmailAuth, fetchEmails]);

  const handleClassifyGmailEmail = async (messageId: string) => {
    setClassifyLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/emails/${messageId}/classify`, {
        method: "POST",
      });
      if (!res.ok) throw new Error((await res.json()).detail || "Erro ao classificar");
      const data: ClassificationResult = await res.json();
      setResult(data);
      setSelectedEmailId(messageId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao classificar");
    } finally {
      setClassifyLoading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      const ext = droppedFile.name.toLowerCase().split(".").pop();
      if (ext === "txt" || ext === "pdf") {
        setFile(droppedFile);
        setText("");
      } else {
        setError("Formato não suportado. Use .txt ou .pdf");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      const ext = selectedFile.name.toLowerCase().split(".").pop();
      if (ext === "txt" || ext === "pdf") {
        setFile(selectedFile);
        setText("");
        setError(null);
      } else {
        setError("Formato não suportado. Use .txt ou .pdf");
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!file && !text.trim()) {
      setError("Envie um arquivo ou insira o texto do email");
      return;
    }

    setLoading(true);

    try {
      const formData = new FormData();
      if (file) {
        formData.append("file", file);
      }
      if (text.trim()) {
        formData.append("text", text.trim());
      }

      const response = await fetch(`${API_URL}/api/classify`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Erro ${response.status}`);
      }

      const data: ClassificationResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao processar. Verifique se o backend está rodando."
      );
    } finally {
      setLoading(false);
    }
  };

  const isProdutivo = result?.category === "Produtivo";

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[var(--card-border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div className="w-9 h-9 sm:w-10 sm:h-10 shrink-0 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center">
                <svg
                  className="w-5 h-5 sm:w-6 sm:h-6 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <div className="min-w-0">
                <h1 className="text-base sm:text-xl font-semibold tracking-tight truncate">
                  Email Classifier
                </h1>
                <p className="text-xs sm:text-sm text-slate-400 hidden sm:block">
                  Classificação inteligente com IA
                </p>
              </div>
            </div>

            {/* Desktop: Gmail actions */}
            <div className="hidden md:flex items-center gap-2">
              {!gmailLoading && (
                gmailAuth ? (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-400 truncate max-w-[140px]">
                      {gmailAuth.email}
                    </span>
                    <button
                      type="button"
                      onClick={handleDisconnectGmail}
                      className="px-3 py-1.5 rounded-lg text-sm border border-slate-600 hover:bg-slate-800/50 transition-colors"
                    >
                      Desconectar
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleConnectGmail}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-slate-600 font-medium transition-all"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path fill="currentColor" d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L12 9.128l8.073-5.635C21.69 2.28 24 3.434 24 5.457z"/>
                    </svg>
                    Conectar Gmail
                  </button>
                )
              )}
            </div>

            {/* Mobile: Hamburger */}
            <div className="flex md:hidden items-center gap-2">
              {!gmailLoading && gmailAuth && (
                <span className="text-xs text-slate-500 truncate max-w-[80px]">
                  {gmailAuth.email}
                </span>
              )}
              <button
                type="button"
                onClick={() => setMenuOpen((o) => !o)}
                className="p-2 rounded-lg border border-slate-600 hover:bg-slate-800/50 transition-colors"
                aria-label="Menu"
              >
                <svg
                  className="w-6 h-6"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  {menuOpen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  )}
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {menuOpen && (
          <>
            <div
              className="md:hidden fixed inset-0 bg-black/40 z-10"
              onClick={() => setMenuOpen(false)}
              aria-hidden
            />
            <div className="md:hidden absolute left-0 right-0 top-full border-b border-[var(--card-border)] bg-[var(--card)] shadow-xl z-20 animate-fade-in">
              <div className="px-4 py-4 space-y-2">
                {gmailLoading ? (
                  <p className="text-sm text-slate-500 py-2">Carregando...</p>
                ) : (
                  gmailAuth ? (
                    <div className="space-y-2">
                      <p className="text-sm text-slate-400 truncate px-2">
                        {gmailAuth.email}
                      </p>
                      <button
                        type="button"
                        onClick={() => {
                          handleDisconnectGmail();
                          setMenuOpen(false);
                        }}
                        className="w-full px-4 py-3 rounded-xl border border-slate-600 hover:bg-slate-800/50 text-left font-medium transition-colors"
                      >
                        Desconectar Gmail
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        handleConnectGmail();
                        setMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-slate-600 font-medium transition-colors"
                    >
                      <svg className="w-5 h-5" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L12 9.128l8.073-5.635C21.69 2.28 24 3.434 24 5.457z"/>
                      </svg>
                      Conectar Gmail
                    </button>
                  )
                )}
              </div>
            </div>
          </>
        )}
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <div className="space-y-8">
          {/* Intro */}
          <section className="text-center space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
              Automatize sua caixa de entrada
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Conecte seu Gmail para ler emails automaticamente, ou envie um arquivo .txt/.pdf
              ou cole o texto. Nossa IA irá classificar e sugerir respostas.
            </p>
          </section>

          {/* Gmail - Lista de emails */}
          {gmailAuth && (
            <section className="space-y-4 animate-fade-in">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-300">
                  Emails do Gmail
                </h3>
                <button
                  type="button"
                  onClick={fetchEmails}
                  disabled={emailsLoading}
                  className="text-sm text-cyan-400 hover:text-cyan-300 disabled:opacity-50"
                >
                  {emailsLoading ? "Carregando..." : "Atualizar"}
                </button>
              </div>
              <div className="rounded-2xl border border-[var(--card-border)] bg-[var(--card)] overflow-hidden max-h-[320px] overflow-y-auto">
                {emailsLoading ? (
                  <div className="p-8 text-center text-slate-500">
                    Carregando emails...
                  </div>
                ) : emails.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">
                    Nenhum email encontrado.
                  </div>
                ) : (
                  <ul className="divide-y divide-slate-700">
                    {emails.map((msg) => (
                      <li key={msg.id} className="hover:bg-slate-800/30 transition-colors">
                        <button
                          type="button"
                          onClick={() => handleClassifyGmailEmail(msg.id)}
                          disabled={classifyLoading}
                          className="w-full text-left px-4 py-3 block disabled:opacity-50"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <p className="font-medium text-slate-200 truncate">
                                {msg.subject}
                              </p>
                              <p className="text-sm text-slate-500 truncate">
                                {msg.from}
                              </p>
                              <p className="text-xs text-slate-600 mt-0.5 line-clamp-2">
                                {msg.snippet}
                              </p>
                            </div>
                            <span className="text-xs text-slate-500 shrink-0">
                              {msg.date}
                            </span>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="text-sm text-slate-500">
                Clique em um email para classificar com IA e obter sugestão de resposta.
              </p>
            </section>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-6 sm:grid-cols-2">
              {/* Upload Area */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 ${
                  dragActive
                    ? "border-cyan-500 bg-cyan-500/10"
                    : "border-slate-600 hover:border-slate-500 bg-slate-800/30"
                }`}
              >
                <input
                  type="file"
                  id="file-upload"
                  accept=".txt,.pdf"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <div className="p-8 text-center pointer-events-none">
                  <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-slate-700/50 flex items-center justify-center">
                    <svg
                      className="w-7 h-7 text-slate-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      />
                    </svg>
                  </div>
                  <p className="text-slate-300 font-medium">
                    {file ? file.name : "Arraste ou clique para enviar"}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    .txt ou .pdf
                  </p>
                </div>
              </div>

              {/* Text Input */}
              <div className="space-y-2">
                <label
                  htmlFor="text-input"
                  className="block text-sm font-medium text-slate-400"
                >
                  Ou cole o texto do email
                </label>
                <textarea
                  id="text-input"
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    if (file) setFile(null);
                  }}
                  placeholder="Cole aqui o conteúdo do email..."
                  rows={6}
                  className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 resize-none transition-all"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-4">
              <button
                type="submit"
                disabled={loading}
                className="px-8 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-600 hover:from-cyan-600 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all shadow-lg shadow-cyan-500/20"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="animate-spin h-5 w-5"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Processando...
                  </span>
                ) : (
                  "Classificar e sugerir resposta"
                )}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className="px-6 py-3 rounded-xl border border-slate-600 hover:bg-slate-800/50 font-medium transition-all"
              >
                Limpar
              </button>
            </div>
          </form>

          {/* Error */}
          {error && (
            <div
              className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 animate-fade-in"
              role="alert"
            >
              {error}
            </div>
          )}

          {/* Results */}
          {result && (
            <section className="space-y-6 animate-fade-in">
              <h3 className="text-lg font-semibold text-slate-300">
                Resultado da análise
              </h3>

              <div className="grid gap-6 sm:grid-cols-2">
                {/* Category Card */}
                <div className="rounded-2xl bg-[var(--card)] border border-[var(--card-border)] p-6">
                  <p className="text-sm font-medium text-slate-500 mb-2">
                    Categoria
                  </p>
                  <div className="flex items-center gap-3">
                    <span
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl font-semibold ${
                        isProdutivo
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-amber-500/20 text-amber-400"
                      }`}
                    >
                      {isProdutivo ? (
                        <>
                          <span className="w-2 h-2 rounded-full bg-emerald-400" />
                          Produtivo
                        </>
                      ) : (
                        <>
                          <span className="w-2 h-2 rounded-full bg-amber-400" />
                          Improdutivo
                        </>
                      )}
                    </span>
                    <span className="text-slate-500 text-sm">
                      {Math.round(result.confidence * 100)}% confiança
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-3">
                    {isProdutivo
                      ? "Este email requer uma ação ou resposta específica."
                      : "Este email não necessita de ação imediata."}
                  </p>
                </div>

                {/* Response Card */}
                <div className="rounded-2xl bg-[var(--card)] border border-[var(--card-border)] p-6 sm:col-span-2">
                  <p className="text-sm font-medium text-slate-500 mb-3">
                    Resposta sugerida
                  </p>
                  <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
                    <p className="text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {result.suggested_response}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      navigator.clipboard.writeText(result.suggested_response)
                    }
                    className="mt-3 text-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-2 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    Copiar resposta
                  </button>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--card-border)] py-6 mt-auto">
        <div className="max-w-4xl mx-auto px-6 text-center text-sm text-slate-500">
          Classificação em Produtivo (requer ação) ou Improdutivo (não requer
          ação) • Powered by NLP + IA
        </div>
      </footer>
    </div>
  );
}
