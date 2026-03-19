"use client";

import { useState, useCallback } from "react";

interface ClassificationResult {
  category: string;
  confidence: number;
  suggested_response: string;
  processed_text?: string;
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

  const resetForm = useCallback(() => {
    setFile(null);
    setText("");
    setResult(null);
    setError(null);
  }, []);

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
      <header className="border-b border-[var(--card-border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-white"
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
            <div>
              <h1 className="text-xl font-semibold tracking-tight">
                Email Classifier
              </h1>
              <p className="text-sm text-slate-400">
                Classificação inteligente com IA
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto px-6 py-12">
        <div className="space-y-8">
          {/* Intro */}
          <section className="text-center space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
              Automatize sua caixa de entrada
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Envie um email em formato .txt ou .pdf, ou cole o texto diretamente.
              Nossa IA irá classificar e sugerir uma resposta adequada.
            </p>
          </section>

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
