'use client';

import { useState, useCallback, useEffect, useRef } from 'react';

interface ClassificationResult {
  category: string;
  confidence: number;
  suggested_response: string;
  processed_text?: string;
  ai_used?: boolean; // true = gerado pela IA, false = template de fallback
}

interface GmailMessage {
  id: string;
  threadId: string;
  snippet: string;
  subject: string;
  from: string;
  date: string;
  /** Epoch ms no Gmail (preferir para exibir horário correto) */
  internalDate?: number | null;
  already_sent?: boolean;
  record_id?: number;
  status?: string;
  category?: string | null;
  confidence?: number | null;
  suggested_response?: string | null;
}

interface SentRecord {
  id: number;
  gmail_message_id: string;
  subject: string;
  sender: string;
  snippet: string | null;
  received_at: string | null;
  status: string;
  category?: string | null;
  suggested_response?: string | null;
}

interface Pagination {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/** Fuso usado pelo job, filtros e exibição (alinhado ao backend) */
const APP_TIMEZONE = 'America/Sao_Paulo';

function formatDateTimePtBrSP(isoOrMs: string | number | null | undefined): string {
  if (isoOrMs == null || isoOrMs === '') return '';
  const d =
    typeof isoOrMs === 'number' ? new Date(isoOrMs) : new Date(isoOrMs);
  if (Number.isNaN(d.getTime()))
    return typeof isoOrMs === 'string' ? isoOrMs : '';
  return d.toLocaleString('pt-BR', {
    timeZone: APP_TIMEZONE,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatGmailRowDate(msg: GmailMessage): string {
  if (msg.internalDate != null && msg.internalDate !== undefined)
    return formatDateTimePtBrSP(Number(msg.internalDate));
  if (msg.date) {
    const parsed = new Date(msg.date);
    if (!Number.isNaN(parsed.getTime())) return formatDateTimePtBrSP(parsed.getTime());
  }
  return msg.date || '';
}

/** URL do vídeo de demonstração (trocar pelo oficial quando estiver pronto) */
//const DEMO_VIDEO_URL = "https://res.cloudinary.com/ti-tinho/video/upload/v1773939753/chat_attachments/oz5jm2pgqitemfpbb60w.mp4";
const DEMO_VIDEO_URL = '';

type TabId = 'gmail' | 'manual';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabId>('gmail');

  // Manual: arquivo/texto
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClassificationResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [toEmail, setToEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [sendSingleLoading, setSendSingleLoading] = useState(false);
  const [sendSingleSuccess, setSendSingleSuccess] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // Gmail
  const [gmailAuth, setGmailAuth] = useState<{
    email: string;
    name?: string;
    can_send?: boolean;
  } | null>(null);
  const [gmailLoading, setGmailLoading] = useState(true);
  const [gmailConnecting, setGmailConnecting] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [emails, setEmails] = useState<GmailMessage[]>([]);
  const [emailsLoading, setEmailsLoading] = useState(false);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [classifyLoading, setClassifyLoading] = useState(false);

  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState<{
    sent: number;
    skipped: number;
    errors: { gmail_id: string; error: string }[];
  } | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);

  // Sub-tab Gmail: pendentes vs enviados
  const [gmailSubTab, setGmailSubTab] = useState<'pending' | 'sent'>('pending');
  const [sentEmails, setSentEmails] = useState<SentRecord[]>([]);
  const [sentLoading, setSentLoading] = useState(false);
  const [sentPage, setSentPage] = useState(1);
  const [sentPerPage, setSentPerPage] = useState(10);
  const [sentPagination, setSentPagination] = useState<Pagination | null>(null);
  const [sentDateFrom, setSentDateFrom] = useState('');
  const [sentDateTo, setSentDateTo] = useState('');
  const [expandedSentId, setExpandedSentId] = useState<number | null>(null);

  const pendingListDatesInitialized = useRef(false);

  const [jobConfigOpen, setJobConfigOpen] = useState(false);
  const [jobConfig, setJobConfig] = useState<{
    enabled: boolean;
    cron_expression: string;
    date_from: string | null;
    date_to: string | null;
    only_productive: boolean;
    last_run_at: string | null;
  } | null>(null);
  const [jobRunLoading, setJobRunLoading] = useState(false);
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const resultCardRef = useRef<HTMLDivElement>(null);

  const resetManualForm = useCallback(() => {
    setFile(null);
    setText('');
    setResult(null);
    setToEmail('');
    setSubject('');
    setRecipientName('');
    setSendSingleSuccess(false);
    setError(null);
    setResultModalOpen(false);
  }, []);

  useEffect(() => {
    if (result) {
      setResultModalOpen(true);
    }
  }, [result]);

  useEffect(() => {
    if (result && activeTab === 'manual' && resultCardRef.current) {
      resultCardRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    }
  }, [result, activeTab]);

  useEffect(() => {
    fetch(`${API_URL}/api/auth/gmail/status`)
      .then(r => r.json())
      .then(data => {
        if (data.authenticated) {
          setGmailAuth({
            email: data.email,
            name: data.name,
            can_send: data.can_send,
          });
        } else {
          setGmailAuth(null);
        }
      })
      .catch(() => setGmailAuth(null))
      .finally(() => setGmailLoading(false));
  }, []);

  useEffect(() => {
    if (!gmailAuth) {
      pendingListDatesInitialized.current = false;
      return;
    }
    if (pendingListDatesInitialized.current) return;
    const today = new Date().toLocaleDateString('en-CA', {
      timeZone: APP_TIMEZONE,
    });
    setDateFrom(today);
    setDateTo(today);
    pendingListDatesInitialized.current = true;
  }, [gmailAuth]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const success = params.get('gmail_success');
    const err = params.get('gmail_error');
    const email = params.get('email');
    if (success) {
      setError(null);
      window.history.replaceState({}, '', window.location.pathname);
      fetch(`${API_URL}/api/auth/gmail/status`)
        .then(r => r.json())
        .then(data => {
          if (data.authenticated) {
            setGmailAuth({
              email: data.email || email,
              name: data.name,
              can_send: data.can_send,
            });
          }
        });
    }
    if (err) {
      setError(decodeURIComponent(err));
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const handleConnectGmail = () => {
    setGmailConnecting(true);
    setError(null);
    fetch(`${API_URL}/api/auth/gmail/url`)
      .then(r => r.json())
      .then(data => {
        window.location.href = data.auth_url;
      })
      .catch(err => {
        setError(err.message || 'Erro ao obter URL de autenticação');
        setGmailConnecting(false);
      });
  };

  const handleDisconnectGmail = async () => {
    try {
      await fetch(`${API_URL}/api/auth/gmail/revoke`, { method: 'POST' });
      setGmailAuth(null);
      setEmails([]);
      setSelectedEmailId(null);
      setResult(null);
      setSelectedIds(new Set());
    } catch {
      setError('Erro ao desconectar');
    }
  };

  const fetchEmails = useCallback(() => {
    if (!gmailAuth) return;
    setEmailsLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('per_page', String(perPage));
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    fetch(`${API_URL}/api/emails?${params}`)
      .then(r => {
        if (!r.ok) throw new Error('Erro ao buscar emails');
        return r.json();
      })
      .then(data => {
        setEmails(data.emails || []);
        setPagination(data.pagination || null);
      })
      .catch(err => setError(err.message))
      .finally(() => setEmailsLoading(false));
  }, [gmailAuth, page, perPage, dateFrom, dateTo]);

  const fetchSentEmails = useCallback(() => {
    if (!gmailAuth) return;
    setSentLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set('page', String(sentPage));
    params.set('per_page', String(sentPerPage));
    params.set('status', 'sent');
    if (sentDateFrom) params.set('date_from', sentDateFrom);
    if (sentDateTo) params.set('date_to', sentDateTo);
    fetch(`${API_URL}/api/emails/records?${params}`)
      .then(r => {
        if (!r.ok) throw new Error('Erro ao buscar enviados');
        return r.json();
      })
      .then(data => {
        setSentEmails(data.emails || []);
        setSentPagination(data.pagination || null);
      })
      .catch(err => setError(err.message))
      .finally(() => setSentLoading(false));
  }, [gmailAuth, sentPage, sentPerPage, sentDateFrom, sentDateTo]);

  useEffect(() => {
    if (gmailAuth && activeTab === 'gmail') fetchEmails();
  }, [gmailAuth, activeTab, fetchEmails]);

  useEffect(() => {
    if (gmailAuth && activeTab === 'gmail' && gmailSubTab === 'sent') fetchSentEmails();
  }, [gmailAuth, activeTab, gmailSubTab, fetchSentEmails]);

  const handleClassifyGmailEmail = async (messageId: string) => {
    setClassifyLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/emails/${messageId}/classify`, {
        method: 'POST',
      });
      if (!res.ok)
        throw new Error((await res.json()).detail || 'Erro ao classificar');
      const data: ClassificationResult = await res.json();
      setResult(data);
      setSelectedEmailId(messageId);
      fetchEmails();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao classificar');
    } finally {
      setClassifyLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const canSend = emails.filter(e => !e.already_sent);
    if (selectedIds.size >= canSend.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(canSend.map(e => e.id)));
  };

  const handleSendSelected = async () => {
    if (selectedIds.size === 0) {
      setError('Selecione pelo menos um email para enviar.');
      return;
    }
    setSendLoading(true);
    setError(null);
    setSendResult(null);
    try {
      const res = await fetch(`${API_URL}/api/emails/send-batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_ids: Array.from(selectedIds) }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erro ao enviar');
      setSendResult(data);
      setSelectedIds(new Set());
      fetchEmails();
      fetchSentEmails();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar');
    } finally {
      setSendLoading(false);
    }
  };

  const fetchJobConfig = useCallback(() => {
    fetch(`${API_URL}/api/jobs/config`)
      .then(r => r.json())
      .then(setJobConfig)
      .catch(() => setJobConfig(null));
  }, []);

  useEffect(() => {
    if (jobConfigOpen) fetchJobConfig();
  }, [jobConfigOpen, fetchJobConfig]);

  const handleRunJob = async () => {
    setJobRunLoading(true);
    setError(null);
    try {
      const body: {
        date_from?: string;
        date_to?: string;
        only_productive?: boolean;
      } = {};
      if (dateFrom) body.date_from = dateFrom;
      if (dateTo) body.date_to = dateTo;
      body.only_productive = jobConfig?.only_productive ?? false;
      const res = await fetch(`${API_URL}/api/jobs/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok)
        throw new Error(data.detail || data.error || 'Erro ao executar job');
      setError(null);
      setJobConfigOpen(false);
      fetchEmails();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao executar job');
    } finally {
      setJobRunLoading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      const ext = droppedFile.name.toLowerCase().split('.').pop();
      if (ext === 'txt' || ext === 'pdf') {
        setFile(droppedFile);
        setText('');
      } else {
        setError('Formato não suportado. Use .txt ou .pdf');
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      const ext = selectedFile.name.toLowerCase().split('.').pop();
      if (ext === 'txt' || ext === 'pdf') {
        setFile(selectedFile);
        setText('');
        setError(null);
      } else {
        setError('Formato não suportado. Use .txt ou .pdf');
      }
    }
  };

  const handleSubmitManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!file && !text.trim()) {
      setError('Envie um arquivo ou insira o texto do email');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      if (file) formData.append('file', file);
      if (text.trim()) formData.append('text', text.trim());
      if (recipientName.trim())
        formData.append('recipient_name', recipientName.trim());
      const response = await fetch(`${API_URL}/api/classify`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Erro ${response.status}`);
      }
      const data: ClassificationResult = await response.json();
      setResult(data);
      setSendSingleSuccess(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao processar');
    } finally {
      setLoading(false);
    }
  };

  const handleSendSingle = async () => {
    if (!result) return;
    const email = toEmail.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      setError('Informe um email de destinatário válido.');
      return;
    }
    setSendSingleLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/send-single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_email: email,
          subject: subject.trim() || 'Resposta',
          body: result.suggested_response,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erro ao enviar');
      setSendSingleSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar');
    } finally {
      setSendSingleLoading(false);
    }
  };

  const canSendCount = emails.filter(e => !e.already_sent).length;
  const isProdutivo = result?.category === 'Produtivo';

  return (
    <div className='min-h-screen flex flex-col'>
      <header className='border-b border-[var(--card-border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-20'>
        <div className='max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4'>
          <div className='flex items-center justify-between gap-4'>
            <div className='flex items-center gap-2 sm:gap-3 min-w-0'>
              <div className='w-9 h-9 sm:w-10 sm:h-10 shrink-0 rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 flex items-center justify-center'>
                <svg
                  className='w-5 h-5 sm:w-6 sm:h-6 text-white'
                  fill='none'
                  stroke='currentColor'
                  viewBox='0 0 24 24'
                >
                  <path
                    strokeLinecap='round'
                    strokeLinejoin='round'
                    strokeWidth={2}
                    d='M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'
                  />
                </svg>
              </div>
              <div className='min-w-0'>
                <h1 className='text-base sm:text-xl font-semibold tracking-tight truncate'>
                  Email Classifier
                </h1>
                <p className='text-xs sm:text-sm text-slate-400 hidden sm:block'>
                  Classificação inteligente com IA
                </p>
              </div>
            </div>

            <div className='hidden md:flex items-center gap-2'>
              {gmailLoading ? (
                <div
                  className='flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-600 bg-slate-800/30 animate-pulse'
                  aria-busy='true'
                  aria-live='polite'
                >
                  <span
                    className='inline-block w-5 h-5 rounded-full border-2 border-slate-500 border-t-cyan-400 animate-spin'
                    role='status'
                    aria-hidden
                  />
                  <span className='text-sm text-slate-400'>
                    Verificando Gmail...
                  </span>
                </div>
              ) : gmailAuth ? (
                <div className='flex items-center gap-2'>
                  <div
                    className='flex items-center gap-1.5 min-w-0'
                    title={gmailAuth.email}
                  >
                    <span className='text-xs text-slate-500 shrink-0'>
                      Conectado como
                    </span>
                    <span
                      className='text-sm text-slate-300 font-medium truncate max-w-[200px]'
                      title={gmailAuth.email}
                    >
                      {gmailAuth.name || gmailAuth.email}
                    </span>
                  </div>
                  <button
                    type='button'
                    onClick={() => setJobConfigOpen(true)}
                    className='px-3 py-1.5 rounded-lg text-sm border border-slate-600 hover:bg-slate-800/50 transition-colors'
                  >
                    Job Diário
                  </button>
                  <button
                    type='button'
                    onClick={handleDisconnectGmail}
                    className='px-3 py-1.5 rounded-lg text-sm border border-slate-600 hover:bg-slate-800/50 transition-colors'
                  >
                    Desconectar
                  </button>
                </div>
              ) : (
                <button
                  type='button'
                  onClick={handleConnectGmail}
                  disabled={gmailConnecting}
                  className='flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-slate-600 font-medium transition-all disabled:opacity-70 disabled:cursor-not-allowed'
                >
                  {gmailConnecting ? (
                    <>
                      <span
                        className='inline-block w-5 h-5 rounded-full border-2 border-slate-500 border-t-cyan-400 animate-spin'
                        role='status'
                        aria-hidden
                      />
                      Conectando...
                    </>
                  ) : (
                    <>
                      <svg className='w-5 h-5' viewBox='0 0 24 24'>
                        <path
                          fill='currentColor'
                          d='M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L12 9.128l8.073-5.635C21.69 2.28 24 3.434 24 5.457z'
                        />
                      </svg>
                      Conectar Gmail
                    </>
                  )}
                </button>
              )}
            </div>

            <div className='flex md:hidden items-center gap-2'>
              {gmailLoading ? (
                <span className='text-xs text-slate-500 flex items-center gap-1.5'>
                  <span
                    className='inline-block w-3 h-3 rounded-full border-2 border-slate-500 border-t-cyan-400 animate-spin'
                    aria-hidden
                  />
                  Verificando...
                </span>
              ) : (
                gmailAuth && (
                  <span
                    className='text-xs text-slate-500 truncate max-w-[120px]'
                    title={gmailAuth.email}
                  >
                    {gmailAuth.name || gmailAuth.email}
                  </span>
                )
              )}
              <button
                type='button'
                onClick={() => setMenuOpen(o => !o)}
                className='p-2 rounded-lg border border-slate-600 hover:bg-slate-800/50 transition-colors'
                aria-label='Menu'
              >
                <svg
                  className='w-6 h-6'
                  fill='none'
                  stroke='currentColor'
                  viewBox='0 0 24 24'
                >
                  {menuOpen ? (
                    <path
                      strokeLinecap='round'
                      strokeLinejoin='round'
                      strokeWidth={2}
                      d='M6 18L18 6M6 6l12 12'
                    />
                  ) : (
                    <path
                      strokeLinecap='round'
                      strokeLinejoin='round'
                      strokeWidth={2}
                      d='M4 6h16M4 12h16M4 18h16'
                    />
                  )}
                </svg>
              </button>
            </div>
          </div>
        </div>

        {menuOpen && (
          <>
            <div
              className='md:hidden fixed inset-0 bg-black/40 z-10'
              onClick={() => setMenuOpen(false)}
              aria-hidden
            />
            <div className='md:hidden absolute left-0 right-0 top-full border-b border-[var(--card-border)] bg-[var(--card)] shadow-xl z-20 animate-fade-in'>
              <div className='px-4 py-4 space-y-2'>
                {gmailLoading ? (
                  <div className='flex items-center justify-center gap-2 py-4 text-slate-400'>
                    <span
                      className='inline-block w-5 h-5 rounded-full border-2 border-slate-500 border-t-cyan-400 animate-spin'
                      aria-hidden
                    />
                    <span>Verificando conexão Gmail...</span>
                  </div>
                ) : gmailAuth ? (
                  <div className='space-y-2'>
                    <div className='px-2 py-1 rounded-lg bg-slate-800/50'>
                      <p className='text-xs text-slate-500'>Conectado como</p>
                      <p
                        className='text-sm font-medium text-slate-200 truncate'
                        title={gmailAuth.email}
                      >
                        {gmailAuth.name || gmailAuth.email}
                      </p>
                      <p
                        className='text-xs text-slate-500 truncate'
                        title={gmailAuth.email}
                      >
                        {gmailAuth.email}
                      </p>
                    </div>
                    <button
                      type='button'
                      onClick={() => {
                        setJobConfigOpen(true);
                        setMenuOpen(false);
                      }}
                      className='w-full px-4 py-3 rounded-xl border border-slate-600 hover:bg-slate-800/50 text-left font-medium transition-colors'
                    >
                      Job Diário
                    </button>
                    <button
                      type='button'
                      onClick={() => {
                        handleDisconnectGmail();
                        setMenuOpen(false);
                      }}
                      className='w-full px-4 py-3 rounded-xl border border-slate-600 hover:bg-slate-800/50 text-left font-medium transition-colors'
                    >
                      Desconectar Gmail
                    </button>
                  </div>
                ) : (
                  <button
                    type='button'
                    onClick={() => {
                      handleConnectGmail();
                      setMenuOpen(false);
                    }}
                    disabled={gmailConnecting}
                    className='w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-slate-600 font-medium transition-colors disabled:opacity-70 disabled:cursor-not-allowed'
                  >
                    {gmailConnecting ? (
                      <>
                        <span
                          className='inline-block w-5 h-5 rounded-full border-2 border-slate-500 border-t-cyan-400 animate-spin'
                          aria-hidden
                        />
                        Conectando...
                      </>
                    ) : (
                      <>
                        <svg className='w-5 h-5' viewBox='0 0 24 24'>
                          <path
                            fill='currentColor'
                            d='M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 0 1 0 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L12 9.128l8.073-5.635C21.69 2.28 24 3.434 24 5.457z'
                          />
                        </svg>
                        Conectar Gmail
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          </>
        )}
      </header>

      <main className='flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12'>
        <div className='space-y-8'>
          <section className='text-center space-y-2'>
            <h2 className='text-2xl sm:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent'>
              Automatize sua caixa de entrada
            </h2>
            <p className='text-slate-400 max-w-xl mx-auto'>
              Gerencie emails do Gmail em lote ou classifique arquivos e envie
              respostas individualmente.
            </p>
          </section>

          {/* Vídeo de demonstração (só renderiza quando DEMO_VIDEO_URL estiver definida) */}
          {DEMO_VIDEO_URL && (
            <section className='rounded-2xl border border-[var(--card-border)] bg-[var(--card)] overflow-hidden'>
              <h3 className='text-lg font-semibold text-slate-300 px-4 py-3 border-b border-slate-700'>
                Vídeo de demonstração
              </h3>
              <div className='aspect-video bg-slate-900'>
                <video
                  src={DEMO_VIDEO_URL}
                  controls
                  className='w-full h-full object-contain'
                  playsInline
                >
                  Seu navegador não suporta vídeos.
                </video>
              </div>
              <p className='text-xs text-slate-500 px-4 py-2 border-t border-slate-700/50'>
                Vídeo de exemplo. O oficial será incluído em breve.
              </p>
            </section>
          )}

          {/* Tabs */}
          <div className='flex gap-1 p-1 rounded-xl bg-slate-800/50 border border-slate-700'>
            <button
              type='button'
              onClick={() => {
                setActiveTab('gmail');
                setError(null);
              }}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'gmail'
                  ? 'bg-cyan-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
              }`}
            >
              Caixa de entrada (Gmail)
            </button>
            <button
              type='button'
              onClick={() => {
                setActiveTab('manual');
                setError(null);
              }}
              className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'manual'
                  ? 'bg-cyan-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
              }`}
            >
              Classificar arquivo
            </button>
          </div>

          {error && (
            <div
              className='p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 animate-fade-in'
              role='alert'
            >
              {error}
            </div>
          )}

          {/* Tab: Gmail */}
          {activeTab === 'gmail' && (
            <section className='space-y-4 animate-fade-in'>
              {gmailLoading ? (
                <div className='rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-12 text-center'>
                  <div className='flex flex-col items-center gap-4'>
                    <span
                      className='inline-block w-10 h-10 rounded-full border-4 border-slate-600 border-t-cyan-400 animate-spin'
                      role='status'
                      aria-label='Carregando'
                    />
                    <p className='text-slate-400'>
                      Verificando conexão com Gmail...
                    </p>
                    <p className='text-xs text-slate-500'>
                      Aguarde enquanto verificamos seu status de autenticação.
                    </p>
                  </div>
                </div>
              ) : !gmailAuth ? (
                <div className='rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-12 text-center'>
                  <p className='text-slate-400 mb-6'>
                    Conecte seu Gmail para listar emails, classificar e enviar
                    respostas em lote.
                  </p>
                  <button
                    type='button'
                    onClick={handleConnectGmail}
                    disabled={gmailConnecting}
                    className='px-6 py-3 rounded-xl bg-cyan-600 hover:bg-cyan-700 font-medium transition-colors disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2 mx-auto'
                  >
                    {gmailConnecting ? (
                      <>
                        <span
                          className='inline-block w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin'
                          aria-hidden
                        />
                        Conectando...
                      </>
                    ) : (
                      'Conectar Gmail'
                    )}
                  </button>
                </div>
              ) : (
                <>
                  {gmailAuth.can_send === false && (
                    <div className='p-4 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-300 text-sm'>
                      <strong>Envio desabilitado.</strong> Desconecte e conecte
                      novamente para autorizar o envio. Configure gmail.send e
                      gmail.compose no Google Cloud.
                    </div>
                  )}

                  <div className='flex flex-wrap items-center justify-between gap-4'>
                    <h3 className='text-lg font-semibold text-slate-300'>
                      Emails do Gmail
                    </h3>
                    <div className='flex gap-1 p-1 rounded-lg bg-slate-800/50 border border-slate-700'>
                      <button
                        type='button'
                        onClick={() => {
                          setGmailSubTab('pending');
                          setError(null);
                        }}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                          gmailSubTab === 'pending'
                            ? 'bg-cyan-600 text-white'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                        }`}
                      >
                        A responder
                      </button>
                      <button
                        type='button'
                        onClick={() => {
                          setGmailSubTab('sent');
                          setError(null);
                          fetchSentEmails();
                        }}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                          gmailSubTab === 'sent'
                            ? 'bg-emerald-600 text-white'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
                        }`}
                      >
                        Enviados
                      </button>
                    </div>
                  </div>

                  {gmailSubTab === 'pending' && (
                    <div className='flex flex-wrap items-center justify-end gap-3'>
                      <div className='flex items-center gap-2'>
                        <label className='text-sm text-slate-500'>De</label>
                        <input
                          type='date'
                          value={dateFrom}
                          onChange={e => {
                            setDateFrom(e.target.value);
                            setPage(1);
                          }}
                          className='px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm'
                        />
                      </div>
                      <div className='flex items-center gap-2'>
                        <label className='text-sm text-slate-500'>Até</label>
                        <input
                          type='date'
                          value={dateTo}
                          onChange={e => {
                            setDateTo(e.target.value);
                            setPage(1);
                          }}
                          className='px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm'
                        />
                      </div>
                      <button
                        type='button'
                        onClick={fetchEmails}
                        disabled={emailsLoading}
                        className='px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-sm font-medium transition-colors'
                      >
                        {emailsLoading ? 'Carregando...' : 'Buscar'}
                      </button>
                    </div>
                  )}

                  {gmailSubTab === 'sent' && (
                    <div className='flex flex-wrap items-center justify-end gap-3'>
                      <div className='flex items-center gap-2'>
                        <label className='text-sm text-slate-500'>De</label>
                        <input
                          type='date'
                          value={sentDateFrom}
                          onChange={e => {
                            setSentDateFrom(e.target.value);
                            setSentPage(1);
                          }}
                          className='px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm'
                        />
                      </div>
                      <div className='flex items-center gap-2'>
                        <label className='text-sm text-slate-500'>Até</label>
                        <input
                          type='date'
                          value={sentDateTo}
                          onChange={e => {
                            setSentDateTo(e.target.value);
                            setSentPage(1);
                          }}
                          className='px-3 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm'
                        />
                      </div>
                      <button
                        type='button'
                        onClick={fetchSentEmails}
                        disabled={sentLoading}
                        className='px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-sm font-medium transition-colors'
                      >
                        {sentLoading ? 'Carregando...' : 'Buscar'}
                      </button>
                    </div>
                  )}

                  {gmailSubTab === 'pending' && selectedIds.size > 0 && (
                    <div className='flex items-center justify-between p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30'>
                      <span className='text-sm text-slate-300'>
                        {selectedIds.size} email(s) selecionado(s)
                      </span>
                      <button
                        type='button'
                        onClick={handleSendSelected}
                        disabled={sendLoading || gmailAuth.can_send === false}
                        title={
                          gmailAuth.can_send === false
                            ? 'Reconecte o Gmail para habilitar envio'
                            : undefined
                        }
                        className='px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors'
                      >
                        {sendLoading
                          ? 'Enviando...'
                          : gmailAuth.can_send === false
                            ? 'Reconecte para enviar'
                            : 'Enviar respostas'}
                      </button>
                    </div>
                  )}

                  {gmailSubTab === 'pending' && sendResult && (
                    <div
                      className={`p-4 rounded-xl border text-sm animate-fade-in ${sendResult.errors?.length ? 'bg-amber-500/10 border-amber-500/30' : 'bg-emerald-500/10 border-emerald-500/30'}`}
                    >
                      <div className='text-slate-300'>
                        Enviados: {sendResult.sent} | Ignorados:{' '}
                        {sendResult.skipped}
                        {sendResult.errors?.length > 0 && (
                          <span className='text-amber-400 ml-2'>
                            | Erros: {sendResult.errors.length}
                          </span>
                        )}
                      </div>
                      {sendResult.errors?.length > 0 && (
                        <div className='mt-3 space-y-1'>
                          {sendResult.errors.map(
                            (
                              err: { gmail_id?: string; error: string },
                              i: number,
                            ) => (
                              <div key={i} className='text-amber-400 text-xs'>
                                {err.error}
                                {(err.error
                                  .toLowerCase()
                                  .includes('permission') ||
                                  err.error.toLowerCase().includes('scope') ||
                                  err.error
                                    .toLowerCase()
                                    .includes('insufficient')) && (
                                  <p className='mt-1 text-cyan-400'>
                                    Desconecte o Gmail e conecte novamente.
                                  </p>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  <div className='rounded-2xl border border-[var(--card-border)] bg-[var(--card)] overflow-hidden'>
                    {gmailSubTab === 'pending' ? (
                      <>
                        {emailsLoading ? (
                          <div className='p-8 text-center text-slate-500'>
                            Carregando emails...
                          </div>
                        ) : emails.length === 0 ? (
                          <div className='p-8 text-center text-slate-500'>
                            Nenhum email para responder.
                          </div>
                        ) : (
                          <>
                            <div className='flex items-center gap-3 px-4 py-3 border-b border-slate-700 bg-slate-800/30'>
                              <input
                                type='checkbox'
                                checked={
                                  canSendCount > 0 &&
                                  selectedIds.size === canSendCount
                                }
                                onChange={toggleSelectAll}
                                className='rounded border-slate-600'
                              />
                              <span className='text-sm text-slate-400'>
                                Selecionar todos ({canSendCount} disponíveis)
                              </span>
                            </div>
                            <ul className='divide-y divide-slate-700 max-h-[400px] overflow-y-auto'>
                              {emails.map(msg => (
                                <li
                                  key={msg.id}
                                  className='hover:bg-slate-800/30 transition-colors'
                                >
                                  <div className='flex items-start gap-3 px-4 py-3'>
                                    <input
                                      type='checkbox'
                                      checked={selectedIds.has(msg.id)}
                                      onChange={() => toggleSelect(msg.id)}
                                      className='mt-1 rounded border-slate-600'
                                    />
                                    <button
                                      type='button'
                                      onClick={() =>
                                        handleClassifyGmailEmail(msg.id)
                                      }
                                      disabled={classifyLoading}
                                      className='flex-1 text-left min-w-0 disabled:opacity-50'
                                    >
                                      <div className='flex items-start justify-between gap-2'>
                                        <div className='min-w-0 flex-1'>
                                          <div className='flex items-center gap-2 flex-wrap'>
                                            <p className='font-medium text-slate-200 truncate'>
                                              {msg.subject}
                                            </p>
                                            {msg.category && (
                                              <span
                                                className={`text-xs px-2 py-0.5 rounded ${msg.category === 'Produtivo' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}
                                              >
                                                {msg.category}
                                              </span>
                                            )}
                                          </div>
                                          <p className='text-sm text-slate-500 truncate'>
                                            {msg.from}
                                          </p>
                                          <p className='text-xs text-slate-600 mt-0.5 line-clamp-2'>
                                            {msg.snippet}
                                          </p>
                                        </div>
                                        <span
                                          className='text-xs text-slate-500 shrink-0'
                                          title='Horário em America/Sao_Paulo'
                                        >
                                          {formatGmailRowDate(msg)}
                                        </span>
                                      </div>
                                    </button>
                                  </div>
                                </li>
                              ))}
                            </ul>
                          </>
                        )}
                        {pagination && (
                          <div className='flex flex-wrap items-center justify-between gap-4 px-4 py-3 border-t border-slate-700 bg-slate-800/30'>
                            <div className='flex items-center gap-4'>
                              <span className='text-sm text-slate-400'>
                                {pagination.total} email
                                {pagination.total !== 1 ? 's' : ''} · Página{' '}
                                {pagination.page} de {pagination.total_pages}
                              </span>
                              <div className='flex items-center gap-2'>
                                <label
                                  htmlFor='per-page'
                                  className='text-xs text-slate-500'
                                >
                                  Por página
                                </label>
                                <select
                                  id='per-page'
                                  value={perPage}
                                  onChange={e => {
                                    setPerPage(Number(e.target.value));
                                    setPage(1);
                                  }}
                                  className='px-2 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-cyan-500/50'
                                >
                                  <option value={10}>10</option>
                                  <option value={25}>25</option>
                                  <option value={50}>50</option>
                                </select>
                              </div>
                            </div>
                            <nav
                              className='flex items-center gap-1'
                              aria-label='Navegação de páginas'
                            >
                              <button
                                type='button'
                                onClick={() => setPage(1)}
                                disabled={page <= 1}
                                title='Primeira página'
                                aria-label='Primeira página'
                                className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors'
                              >
                                <svg
                                  className='w-4 h-4 text-slate-400'
                                  fill='none'
                                  stroke='currentColor'
                                  viewBox='0 0 24 24'
                                >
                                  <path
                                    strokeLinecap='round'
                                    strokeLinejoin='round'
                                    strokeWidth={2}
                                    d='M11 19l-7-7 7-7m8 14l-7-7 7-7'
                                  />
                                </svg>
                              </button>
                              <button
                                type='button'
                                onClick={() => setPage(p => Math.max(1, p - 1))}
                                disabled={page <= 1}
                                title='Página anterior'
                                aria-label='Página anterior'
                                className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors'
                              >
                                <svg
                                  className='w-4 h-4 text-slate-400'
                                  fill='none'
                                  stroke='currentColor'
                                  viewBox='0 0 24 24'
                                >
                                  <path
                                    strokeLinecap='round'
                                    strokeLinejoin='round'
                                    strokeWidth={2}
                                    d='M15 19l-7-7 7-7'
                                  />
                                </svg>
                              </button>
                              <span className='px-3 py-1.5 text-sm font-medium text-slate-300 min-w-[4rem] text-center'>
                                {pagination.page} / {pagination.total_pages}
                              </span>
                              <button
                                type='button'
                                onClick={() =>
                                  setPage(p =>
                                    Math.min(pagination.total_pages, p + 1),
                                  )
                                }
                                disabled={page >= pagination.total_pages}
                                title='Próxima página'
                                aria-label='Próxima página'
                                className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors'
                              >
                                <svg
                                  className='w-4 h-4 text-slate-400'
                                  fill='none'
                                  stroke='currentColor'
                                  viewBox='0 0 24 24'
                                >
                                  <path
                                    strokeLinecap='round'
                                    strokeLinejoin='round'
                                    strokeWidth={2}
                                    d='M9 5l7 7-7 7'
                                  />
                                </svg>
                              </button>
                              <button
                                type='button'
                                onClick={() => setPage(pagination.total_pages)}
                                disabled={page >= pagination.total_pages}
                                title='Última página'
                                aria-label='Última página'
                                className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent transition-colors'
                              >
                                <svg
                                  className='w-4 h-4 text-slate-400'
                                  fill='none'
                                  stroke='currentColor'
                                  viewBox='0 0 24 24'
                                >
                                  <path
                                    strokeLinecap='round'
                                    strokeLinejoin='round'
                                    strokeWidth={2}
                                    d='M13 5l7 7-7 7M5 5l7 7-7 7'
                                  />
                                </svg>
                              </button>
                            </nav>
                          </div>
                        )}
                      </>
                    ) : (
                      <>
                        {sentLoading ? (
                          <div className='p-8 text-center text-slate-500'>
                            Carregando enviados...
                          </div>
                        ) : sentEmails.length === 0 ? (
                          <div className='p-8 text-center text-slate-500'>
                            Nenhuma resposta enviada ainda.
                          </div>
                        ) : (
                          <>
                            <div className='px-4 py-3 border-b border-slate-700 bg-emerald-500/10'>
                              <span className='text-sm text-emerald-400 font-medium'>
                                Respostas enviadas com sucesso
                              </span>
                            </div>
                            <ul className='divide-y divide-slate-700 max-h-[400px] overflow-y-auto'>
                              {sentEmails.map(rec => (
                                <li
                                  key={rec.id}
                                  className='hover:bg-slate-800/30 transition-colors'
                                >
                                  <div className='px-4 py-3'>
                                    <button
                                      type='button'
                                      onClick={() =>
                                        setExpandedSentId(
                                          expandedSentId === rec.id
                                            ? null
                                            : rec.id,
                                        )
                                      }
                                      className='w-full text-left'
                                    >
                                      <div className='flex items-start justify-between gap-2'>
                                        <div className='min-w-0 flex-1'>
                                          <div className='flex items-center gap-2 flex-wrap'>
                                            <p className='font-medium text-slate-200 truncate'>
                                              {rec.subject}
                                            </p>
                                            <span className='text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 shrink-0'>
                                              Enviado
                                            </span>
                                            {rec.category && (
                                              <span
                                                className={`text-xs px-2 py-0.5 rounded ${rec.category === 'Produtivo' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}
                                              >
                                                {rec.category}
                                              </span>
                                            )}
                                          </div>
                                          <p className='text-sm text-slate-500 truncate'>
                                            {rec.sender}
                                          </p>
                                          {rec.snippet && (
                                            <p className='text-xs text-slate-600 mt-0.5 line-clamp-2'>
                                              {rec.snippet}
                                            </p>
                                          )}
                                        </div>
                                        <span
                                          className='text-xs text-slate-500 shrink-0'
                                          title='Horário em America/Sao_Paulo'
                                        >
                                          {formatDateTimePtBrSP(rec.received_at)}
                                        </span>
                                      </div>
                                      {expandedSentId === rec.id &&
                                        rec.suggested_response && (
                                          <div
                                            className='mt-3 p-3 rounded-lg bg-slate-800/50 border border-slate-600 text-sm text-slate-300 whitespace-pre-wrap'
                                            onClick={e => e.stopPropagation()}
                                          >
                                            <p className='text-xs text-slate-500 mb-2 font-medium'>
                                              Resposta enviada:
                                            </p>
                                            {rec.suggested_response}
                                          </div>
                                        )}
                                    </button>
                                  </div>
                                </li>
                              ))}
                            </ul>
                            {sentPagination && (
                              <div className='flex flex-wrap items-center justify-between gap-4 px-4 py-3 border-t border-slate-700 bg-slate-800/30'>
                                <div className='flex items-center gap-4'>
                                  <span className='text-sm text-slate-400'>
                                    {sentPagination.total} enviado
                                    {sentPagination.total !== 1 ? 's' : ''} ·
                                    Página {sentPagination.page} de{' '}
                                    {sentPagination.total_pages}
                                  </span>
                                  <div className='flex items-center gap-2'>
                                    <label
                                      htmlFor='sent-per-page'
                                      className='text-xs text-slate-500'
                                    >
                                      Por página
                                    </label>
                                    <select
                                      id='sent-per-page'
                                      value={sentPerPage}
                                      onChange={e => {
                                        setSentPerPage(Number(e.target.value));
                                        setSentPage(1);
                                      }}
                                      className='px-2 py-1.5 rounded-lg bg-slate-800/50 border border-slate-600 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-cyan-500/50'
                                    >
                                      <option value={10}>10</option>
                                      <option value={25}>25</option>
                                      <option value={50}>50</option>
                                    </select>
                                  </div>
                                </div>
                                <nav
                                  className='flex items-center gap-1'
                                  aria-label='Navegação enviados'
                                >
                                  <button
                                    type='button'
                                    onClick={() => setSentPage(1)}
                                    disabled={sentPage <= 1}
                                    className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 disabled:opacity-40 disabled:cursor-not-allowed'
                                  >
                                    <svg
                                      className='w-4 h-4 text-slate-400'
                                      fill='none'
                                      stroke='currentColor'
                                      viewBox='0 0 24 24'
                                    >
                                      <path
                                        strokeLinecap='round'
                                        strokeLinejoin='round'
                                        strokeWidth={2}
                                        d='M11 19l-7-7 7-7m8 14l-7-7 7-7'
                                      />
                                    </svg>
                                  </button>
                                  <button
                                    type='button'
                                    onClick={() =>
                                      setSentPage(p => Math.max(1, p - 1))
                                    }
                                    disabled={sentPage <= 1}
                                    className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 disabled:opacity-40 disabled:cursor-not-allowed'
                                  >
                                    <svg
                                      className='w-4 h-4 text-slate-400'
                                      fill='none'
                                      stroke='currentColor'
                                      viewBox='0 0 24 24'
                                    >
                                      <path
                                        strokeLinecap='round'
                                        strokeLinejoin='round'
                                        strokeWidth={2}
                                        d='M15 19l-7-7 7-7'
                                      />
                                    </svg>
                                  </button>
                                  <span className='px-3 py-1.5 text-sm font-medium text-slate-300 min-w-[4rem] text-center'>
                                    {sentPage} / {sentPagination.total_pages}
                                  </span>
                                  <button
                                    type='button'
                                    onClick={() =>
                                      setSentPage(p =>
                                        Math.min(
                                          sentPagination.total_pages,
                                          p + 1,
                                        ),
                                      )
                                    }
                                    disabled={
                                      sentPage >= sentPagination.total_pages
                                    }
                                    className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 disabled:opacity-40 disabled:cursor-not-allowed'
                                  >
                                    <svg
                                      className='w-4 h-4 text-slate-400'
                                      fill='none'
                                      stroke='currentColor'
                                      viewBox='0 0 24 24'
                                    >
                                      <path
                                        strokeLinecap='round'
                                        strokeLinejoin='round'
                                        strokeWidth={2}
                                        d='M9 5l7 7-7 7'
                                      />
                                    </svg>
                                  </button>
                                  <button
                                    type='button'
                                    onClick={() =>
                                      setSentPage(sentPagination.total_pages)
                                    }
                                    disabled={
                                      sentPage >= sentPagination.total_pages
                                    }
                                    className='p-2 rounded-lg border border-slate-600 hover:bg-slate-700/50 disabled:opacity-40 disabled:cursor-not-allowed'
                                  >
                                    <svg
                                      className='w-4 h-4 text-slate-400'
                                      fill='none'
                                      stroke='currentColor'
                                      viewBox='0 0 24 24'
                                    >
                                      <path
                                        strokeLinecap='round'
                                        strokeLinejoin='round'
                                        strokeWidth={2}
                                        d='M13 5l7 7-7 7M5 5l7 7-7 7'
                                      />
                                    </svg>
                                  </button>
                                </nav>
                              </div>
                            )}
                          </>
                        )}
                      </>
                    )}
                  </div>
                  <p className='text-sm text-slate-500'>
                    {gmailSubTab === 'pending'
                      ? 'Clique em um email para classificar. Selecione e envie as respostas em lote.'
                      : 'Clique em um item para ver a resposta enviada.'}
                  </p>
                </>
              )}
            </section>
          )}

          {/* Tab: Classificar arquivo */}
          {activeTab === 'manual' && (
            <section className='space-y-6 animate-fade-in'>
              <div className='rounded-2xl border border-[var(--card-border)] bg-[var(--card)] p-6'>
                <h3 className='text-lg font-semibold text-slate-300 mb-4'>
                  Classificar e sugerir resposta
                </h3>
                <p className='text-sm text-slate-400 mb-6'>
                  Envie um arquivo .txt ou .pdf, ou cole o texto do email. A IA
                  irá classificar e gerar uma resposta sugerida. Depois, informe
                  para qual email enviar a resposta (cliente, fornecedor, etc.).
                </p>

                <form onSubmit={handleSubmitManual} className='space-y-6'>
                  <div className='grid gap-6 sm:grid-cols-2'>
                    <div
                      onDragEnter={handleDrag}
                      onDragLeave={handleDrag}
                      onDragOver={handleDrag}
                      onDrop={handleDrop}
                      className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 ${dragActive ? 'border-cyan-500 bg-cyan-500/10' : 'border-slate-600 hover:border-slate-500 bg-slate-800/30'}`}
                    >
                      <input
                        type='file'
                        id='file-upload'
                        accept='.txt,.pdf'
                        onChange={handleFileChange}
                        className='absolute inset-0 w-full h-full opacity-0 cursor-pointer'
                      />
                      <div className='p-8 text-center pointer-events-none'>
                        <div className='w-14 h-14 mx-auto mb-4 rounded-xl bg-slate-700/50 flex items-center justify-center'>
                          <svg
                            className='w-7 h-7 text-slate-400'
                            fill='none'
                            stroke='currentColor'
                            viewBox='0 0 24 24'
                          >
                            <path
                              strokeLinecap='round'
                              strokeLinejoin='round'
                              strokeWidth={2}
                              d='M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12'
                            />
                          </svg>
                        </div>
                        <p className='text-slate-300 font-medium'>
                          {file ? file.name : 'Arraste ou clique'}
                        </p>
                        <p className='text-sm text-slate-500 mt-1'>
                          .txt ou .pdf
                        </p>
                      </div>
                    </div>

                    <div className='space-y-2'>
                      <label
                        htmlFor='text-input'
                        className='block text-sm font-medium text-slate-400'
                      >
                        Ou cole o texto
                      </label>
                      <div className='flex gap-4 flex-wrap'>
                        <div className='flex-1 min-w-[200px]'>
                          <textarea
                            id='text-input'
                            value={text}
                            onChange={e => {
                              setText(e.target.value);
                              if (file) setFile(null);
                            }}
                            placeholder='Cole aqui o conteúdo do email...'
                            rows={6}
                            className='w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 resize-none transition-all'
                          />
                        </div>
                        <div className='w-full sm:w-48'>
                          <label
                            htmlFor='recipient-name'
                            className='block text-sm font-medium text-slate-400 mb-1'
                          >
                            Nome do destinatário (opcional)
                          </label>
                          <input
                            id='recipient-name'
                            type='text'
                            value={recipientName}
                            onChange={e => setRecipientName(e.target.value)}
                            placeholder='Ex: João Silva'
                            className='w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-slate-600 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500'
                          />
                          <p className='text-xs text-slate-500 mt-1'>
                            Para personalizar a saudação
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className='flex flex-wrap gap-4'>
                    <button
                      type='submit'
                      disabled={loading}
                      className='px-8 py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-teal-600 hover:from-cyan-600 hover:to-teal-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-all shadow-lg shadow-cyan-500/20'
                    >
                      {loading ? (
                        <span className='flex items-center gap-2'>
                          <svg
                            className='animate-spin h-5 w-5'
                            xmlns='http://www.w3.org/2000/svg'
                            fill='none'
                            viewBox='0 0 24 24'
                          >
                            <circle
                              className='opacity-25'
                              cx='12'
                              cy='12'
                              r='10'
                              stroke='currentColor'
                              strokeWidth='4'
                            />
                            <path
                              className='opacity-75'
                              fill='currentColor'
                              d='M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z'
                            />
                          </svg>
                          Processando...
                        </span>
                      ) : (
                        'Classificar e sugerir resposta'
                      )}
                    </button>
                    <button
                      type='button'
                      onClick={resetManualForm}
                      className='px-6 py-3 rounded-xl border border-slate-600 hover:bg-slate-800/50 font-medium transition-all'
                    >
                      Limpar
                    </button>
                  </div>
                </form>
              </div>

              {result && (
                <div
                  ref={resultCardRef}
                  className='rounded-2xl border border-cyan-500/20 bg-[var(--card)] p-6 space-y-6 animate-fade-in shadow-lg shadow-cyan-500/5'
                >
                  <div className='flex items-center gap-2'>
                    <div className='w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center'>
                      <svg
                        className='w-4 h-4 text-cyan-400'
                        fill='none'
                        stroke='currentColor'
                        viewBox='0 0 24 24'
                      >
                        <path
                          strokeLinecap='round'
                          strokeLinejoin='round'
                          strokeWidth={2}
                          d='M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
                        />
                      </svg>
                    </div>
                    <h3 className='text-lg font-semibold text-slate-300'>
                      Resultado da análise
                    </h3>
                  </div>

                  <div className='flex items-center gap-3 flex-wrap'>
                    <span
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm ${isProdutivo ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}
                    >
                      {isProdutivo ? (
                        <>
                          <span className='w-2 h-2 rounded-full bg-emerald-400' />
                          Produtivo
                        </>
                      ) : (
                        <>
                          <span className='w-2 h-2 rounded-full bg-amber-400' />
                          Improdutivo
                        </>
                      )}
                    </span>
                    <span className='text-slate-500 text-sm'>
                      {Math.round(result.confidence * 100)}% confiança
                    </span>
                    {result.ai_used === false && (
                      <span
                        className='text-amber-400/90 text-xs px-2 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30'
                        title='IA indisponível - resposta de template'
                      >
                        Template
                      </span>
                    )}
                  </div>

                  <div>
                    <p className='text-sm font-medium text-slate-500 mb-3'>
                      Resposta sugerida{' '}
                      {result.ai_used !== false ? '(IA)' : '(template)'}
                    </p>
                    <div className='p-4 rounded-xl bg-slate-800/50 border border-slate-700'>
                      <p className='text-slate-300 whitespace-pre-wrap leading-relaxed'>
                        {result.suggested_response}
                      </p>
                    </div>
                    <button
                      type='button'
                      onClick={() =>
                        navigator.clipboard.writeText(result.suggested_response)
                      }
                      className='mt-3 text-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-2 transition-colors'
                    >
                      <svg
                        className='w-4 h-4'
                        fill='none'
                        stroke='currentColor'
                        viewBox='0 0 24 24'
                      >
                        <path
                          strokeLinecap='round'
                          strokeLinejoin='round'
                          strokeWidth={2}
                          d='M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z'
                        />
                      </svg>
                      Copiar resposta
                    </button>
                  </div>

                  {/* Enviar para destinatário */}
                  <div className='pt-6 border-t border-slate-700'>
                    <h4 className='text-base font-semibold text-slate-300 mb-4'>
                      Enviar resposta sugerida
                    </h4>
                    <p className='text-sm text-slate-500 mb-4'>
                      A resposta gerada pela IA será enviada para o email que
                      você informar abaixo. Use quando quiser responder a alguém
                      específico (ex.: cliente, fornecedor). Requer Gmail
                      conectado.
                    </p>
                    {!gmailAuth ? (
                      <p className='text-amber-400 text-sm'>
                        Conecte o Gmail no header para habilitar o envio.
                      </p>
                    ) : gmailAuth.can_send === false ? (
                      <p className='text-amber-400 text-sm'>
                        Reconecte o Gmail para autorizar o envio.
                      </p>
                    ) : (
                      <div className='space-y-4'>
                        <div>
                          <label
                            htmlFor='to-email'
                            className='block text-sm font-medium text-slate-400 mb-1'
                          >
                            Para quem enviar a resposta? *
                          </label>
                          <input
                            id='to-email'
                            type='email'
                            value={toEmail}
                            onChange={e => setToEmail(e.target.value)}
                            placeholder='email@quem-recebera-a-resposta.com'
                            className='w-full px-4 py-2.5 rounded-xl bg-slate-800/50 border border-slate-600 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500'
                          />
                        </div>
                        <div>
                          <label
                            htmlFor='subject'
                            className='block text-sm font-medium text-slate-400 mb-1'
                          >
                            Assunto (opcional)
                          </label>
                          <input
                            id='subject'
                            type='text'
                            value={subject}
                            onChange={e => setSubject(e.target.value)}
                            placeholder='Re: Resposta'
                            className='w-full px-4 py-2.5 rounded-xl bg-slate-800/50 border border-slate-600 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500'
                          />
                        </div>
                        <button
                          type='button'
                          onClick={handleSendSingle}
                          disabled={sendSingleLoading || !toEmail.trim()}
                          className='px-6 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors'
                        >
                          {sendSingleLoading
                            ? 'Enviando...'
                            : sendSingleSuccess
                              ? 'Enviado!'
                              : 'Enviar para destinatário'}
                        </button>
                        {sendSingleSuccess && (
                          <p className='text-emerald-400 text-sm'>
                            Email enviado com sucesso.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </main>

      {/* Modal: Resultado da classificação */}
      {resultModalOpen && result && (
        <>
          <div
            className='fixed inset-0 bg-black/70 backdrop-blur-sm z-40 animate-fade-in'
            onClick={() => setResultModalOpen(false)}
            aria-hidden
          />
          <div
            className='fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg max-h-[90vh] overflow-hidden z-50 animate-fade-in flex flex-col'
            onClick={e => e.stopPropagation()}
          >
            <div
              className='rounded-2xl border border-cyan-500/30 bg-[var(--card)] shadow-2xl shadow-cyan-500/10 overflow-hidden flex flex-col max-h-[90vh]'
              onClick={e => e.stopPropagation()}
            >
              <div className='px-6 py-4 border-b border-slate-700 bg-gradient-to-r from-cyan-500/10 to-teal-500/10'>
                <div className='flex items-center justify-between'>
                  <div className='flex items-center gap-2'>
                    <div className='w-10 h-10 rounded-xl bg-cyan-500/20 flex items-center justify-center'>
                      <svg
                        className='w-6 h-6 text-cyan-400'
                        fill='none'
                        stroke='currentColor'
                        viewBox='0 0 24 24'
                      >
                        <path
                          strokeLinecap='round'
                          strokeLinejoin='round'
                          strokeWidth={2}
                          d='M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z'
                        />
                      </svg>
                    </div>
                    <div>
                      <h3 className='text-lg font-semibold text-slate-200'>
                        Análise concluída!
                      </h3>
                      <p className='text-sm text-slate-500'>
                        Sua classificação e resposta sugerida estão prontas
                      </p>
                    </div>
                  </div>
                  <button
                    type='button'
                    onClick={() => setResultModalOpen(false)}
                    className='p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-slate-200 transition-colors'
                    aria-label='Fechar'
                  >
                    <svg
                      className='w-5 h-5'
                      fill='none'
                      stroke='currentColor'
                      viewBox='0 0 24 24'
                    >
                      <path
                        strokeLinecap='round'
                        strokeLinejoin='round'
                        strokeWidth={2}
                        d='M6 18L18 6M6 6l12 12'
                      />
                    </svg>
                  </button>
                </div>
              </div>
              <div className='flex-1 overflow-y-auto p-6 space-y-5'>
                <div className='flex items-center gap-3 flex-wrap'>
                  <span
                    className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm ${isProdutivo ? 'bg-emerald-500/20 text-emerald-400 ring-1 ring-emerald-500/30' : 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-500/30'}`}
                  >
                    {isProdutivo ? (
                      <>
                        <span className='w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse' />
                        Produtivo
                      </>
                    ) : (
                      <>
                        <span className='w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse' />
                        Improdutivo
                      </>
                    )}
                  </span>
                  <span className='text-slate-500 text-sm'>
                    {Math.round(result.confidence * 100)}% de confiança
                  </span>
                  {result.ai_used === false && (
                    <span className='text-amber-400/90 text-xs px-2 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30'>
                      Template (IA indisponível)
                    </span>
                  )}
                </div>
                <div>
                  <p className='text-sm font-medium text-slate-400 mb-2'>
                    Resposta sugerida{' '}
                    {result.ai_used !== false ? 'pela IA' : '(template)'}
                  </p>
                  <div className='p-4 rounded-xl bg-slate-800/80 border border-slate-600/80'>
                    <p className='text-slate-200 whitespace-pre-wrap leading-relaxed text-[15px]'>
                      {result.suggested_response}
                    </p>
                  </div>
                  <button
                    type='button'
                    onClick={() =>
                      navigator.clipboard.writeText(result.suggested_response)
                    }
                    className='mt-3 flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 transition-colors font-medium'
                  >
                    <svg
                      className='w-4 h-4'
                      fill='none'
                      stroke='currentColor'
                      viewBox='0 0 24 24'
                    >
                      <path
                        strokeLinecap='round'
                        strokeLinejoin='round'
                        strokeWidth={2}
                        d='M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z'
                      />
                    </svg>
                    Copiar resposta
                  </button>
                </div>
              </div>
              <div className='px-6 py-4 border-t border-slate-700 bg-slate-800/30'>
                <button
                  type='button'
                  onClick={() => setResultModalOpen(false)}
                  className='w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-700 font-medium transition-colors'
                >
                  Entendi
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {jobConfigOpen && (
        <>
          <div
            className='fixed inset-0 bg-black/60 z-40'
            onClick={() => setJobConfigOpen(false)}
            aria-hidden
          />
          <div className='fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[var(--card)] border border-[var(--card-border)] rounded-2xl shadow-xl z-50 p-6 animate-fade-in'>
            <h3 className='text-lg font-semibold text-slate-200 mb-4'>
              Job Diário
            </h3>
            <p className='text-sm text-slate-400 mb-4'>
              Execute automaticamente a classificação e envio de emails no
              período configurado.
            </p>
            {jobConfig && (
              <div className='space-y-4 text-sm'>
                <div className='flex items-center gap-2'>
                  <input
                    type='checkbox'
                    id='job-enabled'
                    checked={jobConfig.enabled}
                    onChange={async e => {
                      const v = e.target.checked;
                      setJobConfig(c => c && { ...c, enabled: v });
                      await fetch(`${API_URL}/api/jobs/config`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enabled: v }),
                      });
                    }}
                  />
                  <label htmlFor='job-enabled'>Ativo</label>
                </div>
                <div className='flex items-center gap-2'>
                  <input
                    type='checkbox'
                    id='job-only-productive'
                    checked={jobConfig.only_productive}
                    onChange={async e => {
                      const v = e.target.checked;
                      setJobConfig(c => c && { ...c, only_productive: v });
                      await fetch(`${API_URL}/api/jobs/config`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ only_productive: v }),
                      });
                    }}
                  />
                  <label htmlFor='job-only-productive'>
                    Enviar apenas emails produtivos
                  </label>
                </div>
                {jobConfig.last_run_at && (
                  <p className='text-slate-500'>
                    Última execução:{' '}
                    {new Date(jobConfig.last_run_at).toLocaleString('pt-BR')}
                  </p>
                )}
              </div>
            )}
            <div className='flex gap-3 mt-6'>
              <button
                type='button'
                onClick={handleRunJob}
                disabled={jobRunLoading}
                className='flex-1 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 font-medium transition-colors'
              >
                {jobRunLoading ? 'Executando...' : 'Executar agora'}
              </button>
              <button
                type='button'
                onClick={() => setJobConfigOpen(false)}
                className='px-4 py-2 rounded-xl border border-slate-600 hover:bg-slate-800/50'
              >
                Fechar
              </button>
            </div>
          </div>
        </>
      )}

      <footer className='border-t border-[var(--card-border)] py-6 mt-auto'>
        <div className='max-w-4xl mx-auto px-6 text-center text-sm text-slate-500'>
          Classificação em Produtivo ou Improdutivo • Powered by NLP + IA •
          PostgreSQL + Job Diário
        </div>
      </footer>
    </div>
  );
}
